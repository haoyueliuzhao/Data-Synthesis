"""CPU-only metadata recovery contracts; fake Tensor bytes are never opened."""

import copy
import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
inheritance = importlib.import_module("finqa_v38_inheritance")


def write_record(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {k: v for k, v in body.items() if k != "id"}
    value = {**body, "id": inheritance.digest(body)}
    path.write_text(json.dumps(value, ensure_ascii=False) + "\n")
    return value


def rewrite(path, **changes):
    return write_record(path, json.loads(path.read_text()) | changes)


def resources(stage):
    gib = inheritance.GIB
    rss = (160 if stage in inheritance.SHARDS else 192) * gib
    host = dict(
        passed=True,
        rss_pass=True,
        available_pass=True,
        rss_limit_bytes=rss,
        available_reserve_bytes=96 * gib,
        rss_bytes=gib,
        peak_rss_bytes=2 * gib,
        available_bytes=400 * gib,
    )
    row = dict(
        passed=True,
        allocated_pass=True,
        free_pass=True,
        deadline_pass=True,
        stop_requested=False,
        boundary=True,
        allocated_bytes=gib,
        reserved_bytes=2 * gib,
        peak_allocated_bytes=2 * gib,
        peak_reserved_bytes=3 * gib,
        free_bytes=70 * gib,
        total_bytes=80 * gib,
        limits=dict(allocated_memory_limit_bytes=76 * gib, free_memory_reserve_bytes=2 * gib),
        host=host,
    )
    return dict(
        all_gates_passed=True,
        limits_unchanged=True,
        maximum_allocated_bytes=76 * gib,
        minimum_device_free_bytes=2 * gib,
        peak_resets_before_model_load=1,
        peak_resets_after_model_loading_begins=0,
        helper_peak_reset_calls=0,
        observed_peak_allocated_bytes=2 * gib,
        observed_minimum_boundary_free_bytes=70 * gib,
        observations=[
            row | dict(label="after_model_load.after_cleanup"),
            row | dict(label="model_released.after_cleanup"),
        ],
        host=dict(
            all_passed=True,
            rss_limit_bytes=rss,
            available_reserve_bytes=96 * gib,
            max_observed_peak_rss_bytes=2 * gib,
            min_observed_available_bytes=400 * gib,
        ),
    )


def payload(directory, context_id, phase):
    root = directory / "payload"
    root.mkdir(parents=True, exist_ok=True)
    raw = b"fake Tensor: must never be opened by metadata inheritance"
    (root / "state.pt").write_bytes(raw)
    write_record(
        root / "record.json",
        dict(
            schema="v37_actual_stage_payload.v1",
            phase=phase,
            context_id=context_id,
            actual_tensors_saved=True,
            state_bytes=len(raw),
            state_sha256="1" * 64,
            state_digest="a" * 64,
        ),
    )
    return inheritance.entry(root / "record.json")


@pytest.fixture
def parent(tmp_path):
    parent = tmp_path / "production_resume_01"
    root = parent / "recovery_01"
    origin = parent / inheritance.FIRST_CONTEXT
    target = root / inheritance.FIRST_CONTEXT
    source = parent / "implementation"
    source.mkdir(parents=True)
    for name in inheritance.PARENT_FILES:
        (source / name).write_text("# Frozen CPU fixture source, never executed.\n")
    implementation = write_record(
        source / "record.json",
        dict(
            schema="v37_committed_production_implementation.v1",
            committed_files=list(inheritance.PARENT_FILES),
            sha256={name: inheritance.sha(source / name) for name in inheritance.PARENT_FILES},
        ),
    )
    protocol = write_record(
        parent / "protocol/record.json",
        dict(
            schema="v37_original_B_controlled_production_protocol.v1",
            initial_progress=copy.deepcopy(inheritance.EXPECTED_PROGRESS),
            first_gate=dict(seed=137, arm="C-only", step=1192, next_actual_sft_step=1193),
            implementation_id=implementation["id"],
            gpu_uuids={str(index): f"GPU-{index}" for index in (3, 4, 5, 7)},
            outer_compute_budget_seconds=86400,
            stage_limits_seconds=dict(distribution=7200),
            resource_wait_budget_seconds=86400,
        ),
    )
    tasks = [dict(index=i, task_id=f"task-{i:04d}") for i in range(744)]
    task_ids = [task["task_id"] for task in tasks]
    assignments = [dict(task_ids=task_ids[index::4]) for index in range(4)]
    write_record(
        origin / "task_plan/record.json",
        dict(
            tasks=tasks,
            task_ids=task_ids,
            assignments=assignments,
        ),
    )
    for index in range(744):
        folder = origin / "task_cache" / f"task{index:04d}"
        folder.mkdir(parents=True)
        (folder / "gradient.pt").write_bytes(b"not-a-Torch-payload")
        write_record(folder / "record.json", dict(task_id=task_ids[index]))
    checkpoint = tmp_path / "training_replication/seed137/arms/c_only/training/step1192_step"
    checkpoint.mkdir(parents=True)
    (checkpoint / "state.pt").write_bytes(b"not-a-Torch-checkpoint")
    write_record(
        checkpoint / "record.json",
        dict(
            seed=137,
            arm="C-only",
            step=1192,
            phase="step",
            state_sha256="2" * 64,
        ),
    )
    context = write_record(
        origin / "context/record.json",
        dict(
            schema="v37_actual_production_context.v1",
            run_root=str(origin),
            outer_root=str(origin),
            seed=137,
            arm="C-only",
            step=1192,
            due_outer=True,
            training_stop_step=1193,
            branch=dict(contribution_only=True, b_N=0.0),
            feedback=dict(
                mode="sealed_existing", denominator=700, expected_point_id="actual-point"
            ),
            sources=dict(worker=inheritance.file_ref(source / "finqa_v37_worker.py")),
            execution_binding=dict(
                protocol=inheritance.entry(parent / "protocol/record.json"),
                implementation_id=implementation["id"],
                training_stop_step=1193,
            ),
            checkpoint=dict(
                path=str(checkpoint),
                record=inheritance.entry(checkpoint / "record.json"),
                state=dict(path=str(checkpoint / "state.pt"), sha256="2" * 64),
            ),
            task_plan=inheritance.entry(origin / "task_plan/record.json"),
            task_cache_root=str(origin / "task_cache"),
        ),
    )
    launch = dict(pid=999999999, birth="fixture-not-a-process")
    write_record(parent / "launch_01/record.json", launch)
    queue = dict(
        phase="STOPPED_FAILURE_NO_RETRY",
        active_children=[],
        protocol_id=protocol["id"],
        pilot_accepted=False,
        accepted_new_optimizer_updates=0,
        accepted_new_outer_updates=0,
        global_external_resource_wait_seconds=0.0,
    )
    (parent / "queue").mkdir()
    (parent / "queue/status.json").write_text(json.dumps(queue))
    write_record(
        parent / "failure/record.json",
        dict(
            protocol_id=protocol["id"],
            at="2026-10-10T07:35:00+00:00",
        ),
    )
    row_counts = [1248, 1229, 1263, 1234]
    for stage in inheritance.INHERITED_STAGES:
        directory = origin / stage
        common = dict(protocol_id=protocol["id"], context_id=context["id"], stage=stage)
        write_record(
            directory / "launch/record.json",
            common
            | launch
            | dict(
                at="2026-10-10T00:00:00+00:00",
                gpu_index=3,
                gpu_uuid="GPU-3",
            ),
        )
        write_record(
            directory / "exit/record.json",
            common
            | dict(
                at="2026-10-10T07:30:00+00:00",
                returncode=0,
                stop_requested=False,
                elapsed_worker_wall_seconds=200.0,
            ),
        )
        result = common | dict(
            status="COMPLETE",
            model_released=True,
            model_optimizer_rng_buffers_unchanged=True,
            gpu_index=3,
            gpu_uuid="GPU-3",
            API_calls=0,
            new_sampling_calls=0,
            scoring_calls=0,
            optimizer_steps=0,
            replayed_responses=0,
            resources=resources(stage),
        )
        if stage in inheritance.SHARDS:
            index = inheritance.SHARDS.index(stage)
            result.update(
                task_ids=assignments[index]["task_ids"],
                task_count=186,
                class_task_calls=186,
                reused_task_ids=[],
                new_completed_rows=row_counts[index],
            )
        else:
            result.update(
                denominator=700,
                response_count=527,
                payload=payload(directory, context["id"], stage),
            )
        if stage == "virtual_point":
            result.update(
                feedback_mode="sealed_existing",
                point_id="actual-point",
                original_sealed_point_matched=True,
                new_feedback_episodes=0,
            )
        if stage == "replay_R3":
            final = directory / "checkpoints/response000527"
            final.mkdir(parents=True)
            (final / "state.pt").write_bytes(b"fake final accumulator")
            write_record(
                final / "record.json",
                dict(
                    cursor=527,
                    full_replay_complete=True,
                    response_prefix_complete=True,
                    no_feedback_generation=True,
                    optimizer_steps_performed=0,
                    binding=dict(denominator=700, response_count=527, point_id="actual-point"),
                ),
            )
            result.update(
                complete_replay=True,
                current_point_only=True,
                replayed_responses=527,
                restored_completed_responses=0,
                final_checkpoint=inheritance.entry(final / "record.json"),
            )
        write_record(directory / "result/record.json", result)
    failed_dir = origin / "distribution"
    common = dict(protocol_id=protocol["id"], context_id=context["id"], stage="distribution")
    write_record(failed_dir / "launch/record.json", common | launch)
    write_record(
        failed_dir / "failure/record.json",
        common
        | dict(
            error="GPU is not fully idle or UUID changed",
            resources=None,
            telemetry=None,
        ),
    )
    write_record(
        failed_dir / "exit/record.json",
        common
        | dict(
            returncode=1,
            at="2026-10-10T07:34:00+00:00",
            elapsed_worker_wall_seconds=142.372393,
        ),
    )
    write_record(
        parent / "actual_final_progress/record.json",
        dict(
            remaining_physical_updates=5810,
            remaining_outers=15,
            pending_sealed_feedback_episodes=2100,
            future_first_sampling_feedback_episodes=8400,
            future_first_sampling_outers=12,
            completed_physical_updates=5812,
            completed_outers=9,
            endpoint_scores_or_answers_read=False,
            pending_sealed_outers=[
                dict(seed=137, arm="C-only", step=1192),
                dict(seed=137, arm="Full", step=1192),
                dict(seed=251, arm="C-only", step=894),
            ],
        ),
    )
    (origin / "queue").mkdir()
    (origin / "queue/status.json").write_text(
        json.dumps(
            dict(
                context_id=context["id"],
                protocol_id=protocol["id"],
                completed_stages=list(inheritance.INHERITED_STAGES),
                compute_seconds=27045.04046258703,
            )
        )
    )
    return SimpleNamespace(
        root=root,
        parent=parent,
        origin=origin,
        target=target,
        context=context,
        protocol=protocol,
        checkpoint=checkpoint,
    )


def initialize(parent):
    value = inheritance.initialize_parent_recovery(parent.root, parent.parent)
    plan = dict(
        id="new-protocol",
        output_root=str(parent.root),
        inheritance=inheritance.entry(parent.root / "inheritance/record.json"),
    )
    return value, plan


def validator(calls):
    def check_result(protocol, stage, result, task_plan):
        assert result["protocol_id"] == protocol["id"]
        inheritance._check_resources(result["resources"], stage)
        calls.append((stage, protocol["id"]))

    return SimpleNamespace(check_result=check_result)


def test_metadata_inheritance_preserves_context_and_charges_prior_time_without_tensor_reads(
    parent, monkeypatch
):
    original = (parent.origin / "context/record.json").read_bytes()
    failure = (parent.parent / "failure/record.json").read_bytes()
    read_bytes = Path.read_bytes

    def metadata_only(path):
        assert path.suffix != ".pt", "inheritance tried to read a scientific Tensor"
        return read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", metadata_only)
    value, plan = initialize(parent)
    assert value["inherited_compute_seconds"] == 27300
    assert value["inherited_compute_seconds"] >= 27045.04046258703 + 142.372393
    assert (
        value["inherited_distribution_seconds"] == value["inherited_resource_wait_seconds"] == 143
    )
    assert value["remaining_scientific_budget"] == inheritance.EXPECTED_PROGRESS
    assert inheritance.resolve_origin_context(parent.target, plan) == parent.origin
    assert (
        inheritance.stage_directory(parent.target, plan, "replay_R3") == parent.origin / "replay_R3"
    )
    assert (
        inheritance.stage_directory(parent.target, plan, "distribution")
        == parent.target / "distribution"
    )
    assert (
        inheritance.checked(parent.target / "context/record.json")["schema"]
        == inheritance.ALIAS_SCHEMA
    )
    assert (parent.origin / "context/record.json").read_bytes() == original
    assert (parent.parent / "failure/record.json").read_bytes() == failure
    assert not (parent.target / "replay_R3").exists()
    assert value["task_cache_inventory"]["tensors"] == 744
    with pytest.raises(ValueError, match="already sealed"):
        initialize(parent)


def test_distribution_accepts_parent_protocol_but_train_requires_current_protocol(parent):
    _value, plan = initialize(parent)
    calls = []
    control = validator(calls)
    inheritance.require_upstream(parent.target, parent.context, plan, "distribution", control)
    assert calls == [(s, parent.protocol["id"]) for s in inheritance.INHERITED_STAGES]
    stage = parent.target / "distribution"
    ref = payload(stage, parent.context["id"], "distribution")
    common = dict(protocol_id=plan["id"], context_id=parent.context["id"], stage="distribution")
    write_record(
        stage / "result/record.json",
        common
        | dict(
            status="COMPLETE",
            model_released=True,
            resources=resources("distribution"),
            payload=ref,
        ),
    )
    write_record(stage / "exit/record.json", common | dict(returncode=0))
    inheritance.require_upstream(parent.target, parent.context, plan, "train", control)
    assert calls[-1] == ("distribution", plan["id"])
    rewrite(stage / "exit/record.json", protocol_id=parent.protocol["id"])
    with pytest.raises(ValueError, match="protocol/point"):
        inheritance.require_upstream(parent.target, parent.context, plan, "train", control)


def test_completed_inherited_replay_cannot_be_dispatched_again(parent):
    _value, plan = initialize(parent)
    with pytest.raises(ValueError, match="must not be rerun"):
        inheritance.require_upstream(
            parent.target, parent.context, plan, "replay_R3", validator([])
        )


@pytest.mark.parametrize(
    "mutation", ["failed_exit", "resource_observation", "wrong_point", "new_outer"]
)
def test_parent_failure_or_inconsistent_evidence_never_publishes_inheritance(parent, mutation):
    if mutation == "failed_exit":
        rewrite(parent.origin / "shard02/exit/record.json", returncode=1)
    elif mutation == "resource_observation":
        path = parent.origin / "virtual_point/result/record.json"
        result = json.loads(path.read_text())
        result["resources"]["observations"][0]["free_bytes"] = 1
        write_record(path, result)
    elif mutation == "wrong_point":
        rewrite(parent.origin / "virtual_point/result/record.json", point_id="step298-reference")
    else:
        (parent.checkpoint.parent / "step1192_outer").mkdir()
    with pytest.raises(ValueError):
        initialize(parent)
    assert not (parent.root / "inheritance/record.json").exists()


def test_bound_parent_metadata_tampering_after_registration_is_rejected(parent):
    _value, plan = initialize(parent)
    rewrite(parent.origin / "replay_R3/result/record.json", replayed_responses=526)
    with pytest.raises(ValueError, match="source bytes changed"):
        inheritance.require_upstream(
            parent.target, parent.context, plan, "distribution", validator([])
        )


def test_alias_cannot_be_moved_to_another_context_or_relabel_parent_id(parent):
    _value, plan = initialize(parent)
    alias = parent.target / "context/record.json"
    rewrite(alias, original_context_id="manufactured-new-context")
    with pytest.raises(ValueError, match="alias binding"):
        inheritance.resolve_origin_context(parent.target, plan)


def test_future_native_context_uses_new_stage_storage(parent):
    _value, plan = initialize(parent)
    future = parent.root / "contexts/seed137/full/step1192_outer"
    write_record(
        future / "context/record.json",
        dict(
            schema="v37_actual_production_context.v1",
            run_root=str(future),
            outer_root=str(future),
            due_outer=False,
        ),
    )
    assert inheritance.resolve_origin_context(future, plan) == future
    assert inheritance.stage_directory(future, plan, "distribution") == future / "distribution"


def test_large_feedback_json_is_stat_bound_once_and_left_for_original_worker(tmp_path, monkeypatch):
    path = tmp_path / "cohort.json"
    with path.open("wb") as stream:
        stream.truncate(64 * 1024**2 + 1)
    reference = dict(path=str(path), sha256="a" * 64)
    deferred = []

    def no_hash(_path):
        pytest.fail("large feedback JSON must be validated by the actual same-point worker")

    monkeypatch.setattr(inheritance, "sha", no_hash)
    inheritance._verify_refs(dict(seal_ref=reference, cohort=reference), deferred=deferred)
    assert len(deferred) == 1
    assert deferred[0]["reference"] == reference
    assert deferred[0]["file_identity"]["bytes"] == 64 * 1024**2 + 1
    assert deferred[0]["content_hash_verified_here"] is False
    assert deferred[0]["required_verification"] == "original_same_point_worker_before_use"
