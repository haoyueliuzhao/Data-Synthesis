"""Read one registered durable prefix; keep original ordered replay bytecode.

Only ReplayCheckpoints.restore is routed to the read-only parent. Every new
checkpoint uses the original writer in the new stage directory. No saved tensor
is converted, reweighted, zero-filled or accepted using completion flags alone.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace


def checkpoint_storage(original_state, resume, destination, *, control, context_id, protocol_id):
    """Return a scoped storage class; never alter the frozen module's globals."""
    destination = Path(destination).resolve()
    source = Path(resume["checkpoint_directory"]).resolve()
    expected_cursor = resume["inherited_response_count"]
    expected_total = resume["total_response_count"]
    control.require(
        type(expected_cursor) is int
        and type(expected_total) is int
        and 0 <= expected_cursor <= expected_total
        and resume["remaining_response_count"] == expected_total - expected_cursor
        and source.name == f"response{expected_cursor:06d}"
        and source.parent != destination,
        "only the registered actual same-point complete response prefix may be inherited",
    )
    control.require(
        Path(resume["checkpoint"]["path"]) == source / "record.json"
        and Path(resume["state"]["path"]) == source / "state.pt"
        and not (source / "record.json").is_symlink()
        and not (source / "state.pt").is_symlink(),
        "registered response prefix paths changed",
    )
    restore_calls = 0

    class ReadOnlyParentPrefix(original_state.ReplayCheckpoints):
        def __init__(self, root, binding, theta):
            control.require(
                Path(root).resolve() == destination
                and binding == resume["binding"]
                and binding["execution_profile_id"] == context_id,
                "inherited prefix differs from current point/reward/order/backend binding",
            )
            super().__init__(root, binding, theta)

        def restore(self):
            nonlocal restore_calls
            control.require(restore_calls == 0, "one registered prefix restoration only")
            restore_calls += 1
            control.require(
                not list(destination.glob("response*")),
                "new replay directory already has responses; no automatic retry",
            )
            control.require(
                control.entry(source / "record.json") == resume["checkpoint"],
                "authorized parent checkpoint record changed",
            )
            # The unchanged reader verifies full binding equality, record hash,
            # actual state.pt SHA, loaded state digest, cursor/accounting, every
            # gradient shape/dtype/finite value and the restored runtime RNG.
            record, state = self.read(source)
            control.require(
                record["cursor"] == state["cursor"] == expected_cursor
                and record["response_prefix_complete"] is True
                and record["full_replay_complete"] is resume["full_replay_complete"]
                and type(record["full_replay_complete"]) is bool
                and (not record["full_replay_complete"] or expected_cursor == expected_total)
                and record["optimizer_steps_performed"] == 0
                and record["no_feedback_generation"] is True
                and record["state_sha256"] == resume["state"]["sha256"]
                and record["binding"]["response_count"] == expected_total
                and control.entry(source / "record.json") == resume["checkpoint"],
                "registered actual response prefix changed during restoration",
            )
            control.publish(
                destination.parent / "inherited_prefix/record.json",
                dict(
                    schema="v43_actual_parent_response_prefix_restored.v1",
                    at=control.now(),
                    protocol_id=protocol_id,
                    context_id=context_id,
                    parent_checkpoint=resume["checkpoint"],
                    parent_state=resume["state"],
                    inherited_response_count=expected_cursor,
                    total_response_count=expected_total,
                    next_response_ordinal=expected_cursor + 1,
                    remaining_response_count=expected_total - expected_cursor,
                    full_original_binding_verified=True,
                    actual_tensor_bytes_and_state_digest_verified=True,
                    actual_parameter_coordinates_verified=True,
                    restored_runtime_rng_verified=True,
                    parent_state_digest=record["state_digest"],
                    actual_rng_digest=state["rng_digest"],
                    parent_files_written=False,
                    checkpoint_only_automatic_recovery=True,
                    API_calls=0,
                    new_sampling_calls=0,
                    replayed_responses=0,
                ),
            )
            return state

    return SimpleNamespace(ReplayCheckpoints=ReadOnlyParentPrefix)


def execute_replay(
    directory,
    context,
    pre_state,
    point,
    cohort,
    rewards,
    driver,
    bundle,
    monitor,
    stop,
    *,
    resume,
    control,
    protocol_id,
    original_worker,
):
    """Use the original mathematical function with just a scoped restore reader."""
    if resume is None:
        return original_worker.execute_replay(
            directory, context, pre_state, point, cohort, rewards, driver, bundle, monitor, stop
        )
    control.require(
        context["due_outer"] is True
        and resume["binding"]["execution_profile_id"] == context["id"]
        and resume["total_response_count"] == point["positive_reward_response_count"],
        "durable prefix must retain the exact original context and complete cohort",
    )
    backend = bundle.replay
    storage = checkpoint_storage(
        backend.v32.state,
        resume,
        Path(directory) / "checkpoints",
        control=control,
        context_id=context["id"],
        protocol_id=protocol_id,
    )

    def bind_feedback(function, **bindings):
        control.require(
            function is backend.v32.feedback_gradient
            and bindings == {"BACKEND_VERSION": backend.BACKEND_VERSION},
            "only the unchanged registered R3 replay callable may use parent restoration",
        )
        return backend.optimized.bind_dependencies(function, state=storage, **bindings)

    class ScopedBackend:
        optimized = SimpleNamespace(bind_dependencies=bind_feedback)

        def __getattr__(self, name):
            return getattr(backend, name)

    routed = SimpleNamespace(**{**vars(bundle), "replay": ScopedBackend()})
    result = original_worker.execute_replay(
        directory, context, pre_state, point, cohort, rewards, driver, routed, monitor, stop
    )
    control.require(
        result["complete_replay"] is True
        and result["restored_completed_responses"] == resume["inherited_response_count"]
        and result["replayed_responses"] == resume["remaining_response_count"]
        and result["response_count"] == resume["total_response_count"],
        "continuation did not preserve the exact inherited and new response counts",
    )
    return dict(
        result,
        actual_new_response_calls=resume["remaining_response_count"],
        inherited_response_count=resume["inherited_response_count"],
        cumulative_complete_response_count=resume["total_response_count"],
        inherited_prefix=control.entry(Path(directory) / "inherited_prefix/record.json"),
        parent_checkpoint_written=False,
        original_ordered_replay_bytecode_unchanged=True,
    )
