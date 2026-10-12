"""Metadata-only V40 prefix recovery contracts; no model, CUDA or API calls."""

import hashlib
import importlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_finance_v38_inheritance import payload, resources, write_record

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
inheritance = importlib.import_module("finqa_v40_inheritance")


def rewrite(path, **changes):
    return write_record(path, json.loads(path.read_text()) | changes)


def stamp(value):
    return datetime.fromtimestamp(1791800000 + value, timezone.utc).isoformat()


@pytest.fixture
def replay(tmp_path):
    parent = tmp_path / "production/recovery_01"
    root = parent.parent / "recovery_02"
    directory = parent / inheritance.REPLAY_RELATIVE
    protocol = write_record(
        parent / "protocol/record.json",
        dict(
            gpu_uuids={"4": "gpu4"},
            stage_limits_seconds=dict(
                class_gradients=43200,
                virtual_first_sampling=43200,
                replay_R3=57600,
                distribution=7200,
                train=28800,
            ),
        ),
    )
    write_record(directory / "task_plan/record.json", dict(task_ids=["t"], assignments=[]))
    context = write_record(
        directory / "context/record.json",
        dict(
            schema="v37_actual_production_context.v1",
            seed=389,
            arm="Full",
            step=298,
            due_outer=True,
            run_root=str(directory),
            outer_root=str(directory),
            branch=dict(b_N=0.2, contribution_only=False),
            feedback=dict(mode="first_sampling"),
            task_plan=inheritance.entry(directory / "task_plan/record.json"),
        ),
    )
    state_dir = directory / "replay_R3/checkpoints/response000261"
    state_dir.mkdir(parents=True)
    raw = b"fake accumulated gradient and RNG checkpoint"
    (state_dir / "state.pt").write_bytes(raw)
    binding = dict(
        schema="v32_fixed_replay_point_binding.v1",
        execution_profile_id=context["id"],
        point_id="same-point",
        response_count=447,
        denominator=700,
        gradient_length_normalized=False,
    )
    saved = write_record(
        state_dir / "record.json",
        dict(
            schema="v19_response_boundary_checkpoint.v1",
            at=stamp(2999),
            cursor=261,
            binding=binding,
            full_replay_complete=False,
            response_prefix_complete=True,
            no_feedback_generation=True,
            optimizer_steps_performed=0,
            state_sha256=hashlib.sha256(raw).hexdigest(),
            state_digest="original-tree-digest",
        ),
    )
    source = directory / "replay_R3"
    common = dict(protocol_id=protocol["id"], context_id=context["id"], stage="replay_R3")
    write_record(
        source / "launch/record.json",
        common
        | dict(
            at=stamp(2000),
            pid=99999998,
            birth="gone",
            gpu_index=4,
            gpu_uuid="gpu4",
            deadline_epoch=1791855078.1726341,
        ),
    )
    write_record(
        source / "exit/record.json",
        common
        | dict(
            at=stamp(3000), returncode=-15, stop_requested=True, elapsed_worker_wall_seconds=1000.0
        ),
    )
    observations = resources("replay_R3")
    before = dict(observations["observations"][0], label="before_model_load")
    after = dict(observations["observations"][-1], label="replay.after_response")
    observations["observations"] = [before, observations["observations"][0], after]
    write_record(
        source / "failure/record.json",
        common
        | dict(
            at=stamp(2999),
            error_type="ReplayPaused",
            error="replay paused at complete response 261",
            automatic_retry=False,
            API_calls=0,
            durable_replay_checkpoint=saved,
            resources=observations,
        ),
    )
    virtual = directory / "virtual_point"
    value_ref = payload(virtual, context["id"], "virtual_point")
    write_record(
        virtual / "result/record.json",
        dict(
            protocol_id=protocol["id"],
            context_id=context["id"],
            stage="virtual_point",
            point_id="same-point",
            response_count=447,
            denominator=700,
            status="COMPLETE",
            payload=value_ref,
        ),
    )
    write_record(
        virtual / "exit/record.json",
        dict(
            protocol_id=protocol["id"],
            context_id=context["id"],
            stage="virtual_point",
            at=stamp(1000),
            returncode=0,
            stop_requested=False,
            elapsed_worker_wall_seconds=1000.0,
        ),
    )
    write_record(
        virtual / "launch/record.json",
        dict(
            protocol_id=protocol["id"],
            context_id=context["id"],
            stage="virtual_point",
            at=stamp(0),
            deadline_epoch=1791843200.0,
        ),
    )
    virtual_binding = dict(
        protocol_scope="parent",
        protocol_id=protocol["id"],
        directory=str(virtual),
        result=inheritance.entry(virtual / "result/record.json"),
        exit=inheritance.entry(virtual / "exit/record.json"),
        launch=inheritance.entry(virtual / "launch/record.json"),
        payload=value_ref,
    )
    return SimpleNamespace(
        root=root,
        parent=parent,
        directory=directory,
        source=source,
        state_dir=state_dir,
        protocol=protocol,
        context=context,
        binding=binding,
        virtual_binding=virtual_binding,
    )


def test_exact_saved_prefix_binding_and_bytes(replay):
    r = replay
    original = (r.source / "failure/record.json").read_bytes()
    value = inheritance.inspect_replay_restore(r.source, r.protocol, r.context)
    assert value["inherited_response_count"] == 261
    assert value["total_response_count"] == 447
    assert value["remaining_response_count"] == 186
    assert value["full_replay_complete"] is False
    assert value["binding"] == r.binding
    assert value["checkpoint"] == inheritance.entry(r.state_dir / "record.json")
    assert value["original_phase_deadline_epoch"] == 1791855078.1726341
    assert value["failed_parent_stage_reclassified"] is False
    assert original == (r.source / "failure/record.json").read_bytes()
    assert not r.root.exists()


@pytest.mark.parametrize(
    "mutation", ["exit", "error", "bytes", "cursor", "point", "later", "result", "resource"]
)
def test_non_authorized_or_corrupt_prefix_rejected(replay, mutation):
    r = replay
    if mutation == "exit":
        rewrite(r.source / "exit/record.json", returncode=1)
    elif mutation == "error":
        rewrite(r.source / "failure/record.json", error_type="OutOfMemoryError")
    elif mutation == "bytes":
        (r.state_dir / "state.pt").write_bytes(b"changed")
    elif mutation == "cursor":
        rewrite(r.state_dir / "record.json", cursor=260)
    elif mutation == "point":
        rewrite(r.directory / "virtual_point/result/record.json", point_id="other-point")
    elif mutation == "later":
        (r.state_dir.parent / "response000262").mkdir()
    elif mutation == "result":
        write_record(r.source / "result/record.json", dict(status="COMPLETE"))
    else:
        failure = inheritance.checked(r.source / "failure/record.json")
        failure["resources"]["observations"][-1]["free_bytes"] = 0
        write_record(r.source / "failure/record.json", failure)
    with pytest.raises(ValueError):
        inheritance.inspect_replay_restore(r.source, r.protocol, r.context)


def test_failed_replay_time_counts_without_completing_stage(replay):
    r = replay
    restore = inheritance.inspect_replay_restore(r.source, r.protocol, r.context)
    bindings = dict(
        virtual_point=r.virtual_binding,
        replay_R3=dict(
            protocol_scope="current",
            directory=str(r.root / "replay_R3"),
            durable_replay_restore=restore,
        ),
    )
    value = inheritance.context_timing(
        r.context, r.protocol, bindings, dict(at=stamp(2000), compute_seconds=32578.5368), restore
    )
    assert value["inherited_compute_seconds"] == 33579
    assert value["phase_deadlines_epoch"]["replay_R3"] == 1791855078.1726341
    assert value["phase_first_launch_epoch"]["replay_R3"] == 1791802000
    assert value["interrupted_worker_seconds"] == 1000
    assert bindings["replay_R3"]["protocol_scope"] == "current"
    assert "distribution" not in value["phase_deadlines_epoch"]


def test_actual_checkpoint_reference_need_not_duplicate_record_coordinates(tmp_path, monkeypatch):
    directory = tmp_path / "step0298_branch"
    directory.mkdir()
    (directory / "state.pt").write_bytes(b"large model checkpoint fixture")
    write_record(
        directory / "record.json",
        dict(
            seed=389,
            arm="Full",
            step=298,
            phase="branch",
            state_sha256="a" * 64,
            actual_state_digest="tree",
        ),
    )
    reference = dict(
        path=str(directory),
        record=inheritance.file_ref(directory / "record.json"),
        state=dict(path=str(directory / "state.pt"), sha256="a" * 64),
        phase="branch",
        actual_state_digest="tree",
    )
    original = Path.open

    def guarded(path, *args, **kwargs):
        assert path.suffix != ".pt", "registration must not open the full model checkpoint"
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)
    value = inheritance.checkpoint_metadata(reference, coordinate=(389, "Full", 298))
    assert (value["seed"], value["arm"], value["step"]) == (389, "Full", 298)
    assert value["reference"] == reference
    with pytest.raises(ValueError, match="another coordinate"):
        inheritance.checkpoint_metadata(reference, coordinate=(251, "Full", 298))


def test_recovery_alias_routes_failed_replay_to_current_protocol(replay, monkeypatch):
    r = replay
    restore = inheritance.inspect_replay_restore(r.source, r.protocol, r.context)
    target = r.root / inheritance.REPLAY_RELATIVE
    bindings = {
        stage: dict(protocol_scope="current", directory=str(target / stage))
        for stage in inheritance.STAGES
    }
    bindings["virtual_point"] = r.virtual_binding
    bindings["replay_R3"]["durable_replay_restore"] = restore
    item = dict(
        seed=389,
        arm="Full",
        step=298,
        original_context=inheritance.entry(r.directory / "context/record.json"),
        original_context_id=r.context["id"],
        origin_context_directory=str(r.directory),
        new_context_directory=str(target),
        stage_bindings=bindings,
        durable_replay_restore=restore,
        parent_protocol=inheritance.entry(r.parent / "protocol/record.json"),
    )
    body = dict(schema=inheritance.SCHEMA, new_root=str(r.root), context_inheritances=[item])
    monkeypatch.setattr(inheritance, "inspect_parent_recovery", lambda *_: body)
    inheritance.initialize_parent_recovery(r.root, r.parent)
    plan = dict(
        id="new-protocol",
        output_root=str(r.root),
        inheritance=inheritance.entry(r.root / "inheritance/record.json"),
    )
    assert inheritance.resolve_origin_context(target, plan) == r.directory
    assert (
        inheritance.stage_directory(target, plan, "virtual_point") == r.directory / "virtual_point"
    )
    assert inheritance.stage_directory(target, plan, "replay_R3") == target / "replay_R3"
    assert inheritance.replay_resume_binding(target, plan) == restore
    observed = []
    inheritance.require_upstream(
        target,
        r.context,
        plan,
        "replay_R3",
        SimpleNamespace(
            check_result=lambda protocol, stage, *_: observed.append((protocol["id"], stage))
        ),
    )
    assert observed == [(r.protocol["id"], "virtual_point")]
    with pytest.raises(ValueError, match="must not rerun"):
        inheritance.require_upstream(target, r.context, plan, "virtual_point", SimpleNamespace())
    assert not (target / "replay_R3/result").exists()


def test_partial_process_resources_do_not_fabricate_model_release(replay):
    resources_value = inheritance.checked(replay.source / "failure/record.json")["resources"]
    inheritance.check_interrupted_resources(resources_value)
    assert resources_value["observations"][-1]["label"] == "replay.after_response"
    assert not any(
        row["label"] == "model_released.after_cleanup" for row in resources_value["observations"]
    )


def test_checkpoint_hashing_cannot_expand_to_model_or_other_cursor(tmp_path):
    path = tmp_path / "response000260/state.pt"
    path.parent.mkdir()
    path.write_bytes(b"not the authorized prefix")
    with pytest.raises(ValueError, match="bounded saved replay"):
        inheritance._state_sha(path)


def test_failed_handoff_uses_actual_wall_not_unspent_plan_deadline(tmp_path):
    parent = tmp_path / "production/recovery_01"
    protocol = write_record(parent / "protocol/record.json", dict(schema="original-parent"))
    failure = dict(
        phase="STOPPED_FAILURE_NO_RETRY",
        error_type="ValueError",
        error="worker reported failure: replay_R3",
        stop_error=None,
        actual_progress_audit_error=None,
        automatic_retry=False,
        protocol_id=protocol["id"],
    )
    write_record(parent / "failure/record.json", failure)
    (parent / "queue").mkdir()
    (parent / "queue/status.json").write_text(
        json.dumps(
            failure
            | dict(
                active_children=[],
                pilot_accepted=True,
                global_external_resource_wait_seconds=4531.917209,
            )
        )
    )
    write_record(parent / "launch_01/record.json", dict(pid=99999998, birth="gone"))
    handoff = parent / "controlled_handoff_gpu6_01"
    plan = write_record(
        handoff / "plan/record.json",
        dict(
            at=stamp(0),
            deadline_epoch=1791900000,
            parent_protocol=inheritance.file_ref(parent / "protocol/record.json"),
            initial_queue=dict(global_external_resource_wait_seconds=4531.917209),
        ),
    )
    stopped = dict(
        at=stamp(23555.826),
        plan_id=plan["id"],
        status="STOPPED_NO_MIGRATION",
        error="observed stage recorded failure",
        controller_signalled=False,
        workers_signalled=False,
        new_experiment_started_by_handoff=False,
        continuation_callback_invoked=False,
        automatic_retry=False,
    )
    write_record(handoff / "failure/record.json", stopped)
    write_record(
        parent.parent / "gpu6_resume_01/migration_launch/record.json",
        dict(pid=99999997, birth="gone"),
    )
    _queue, value = inheritance._parent_stopped(parent, protocol)
    assert value["inherited_resource_wait_seconds"] == 28088
    assert (
        value["resource_wait_accounting"][
            "failed_handoff_unspent_plan_deadline_not_a_recovery_deadline"
        ]
        is True
    )
    rewrite(handoff / "failure/record.json", controller_signalled=True)
    with pytest.raises(ValueError, match="handoff was altered"):
        inheritance._parent_stopped(parent, protocol)


@pytest.fixture
def partial_class(tmp_path):
    parent = tmp_path / "production/recovery_01"
    root = parent.parent / "recovery_02"
    directory = parent / "contexts/seed251/c_only/step1192_outer"
    target = root / directory.relative_to(parent)
    spec = [dict(name="p", shape=[1], dtype="torch.float32")]
    tasks = [
        dict(task_id=f"task{i:04d}", index=i, shard=i % 4, state_ids=["s"]) for i in range(744)
    ]
    assignments = [
        dict(task_ids=[row["task_id"] for row in tasks if row["shard"] == shard])
        for shard in range(4)
    ]
    plan = write_record(
        directory / "task_plan/record.json",
        dict(
            task_ids=[row["task_id"] for row in tasks],
            tasks=tasks,
            assignments=assignments,
            parameter_spec=spec,
        ),
    )
    binding = dict(seed=251, arm="C-only", step=1192, task_plan_id=plan["id"], same_point="actual")
    context = write_record(
        directory / "context/record.json",
        dict(
            schema="v37_actual_production_context.v1",
            seed=251,
            arm="C-only",
            step=1192,
            due_outer=True,
            run_root=str(directory),
            outer_root=str(directory),
            branch=dict(b_N=0, contribution_only=True),
            parameter_spec=spec,
            task_binding=binding,
            math_context_id=inheritance.digest(binding),
            task_plan=inheritance.entry(directory / "task_plan/record.json"),
            task_cache_root=str(directory / "task_cache"),
        ),
    )
    for task in tasks:
        if task["shard"] != 2:
            continue
        cache = directory / f"task_cache/task{task['index']:04d}"
        raw = f"parent-gradient-{task['index']}".encode()
        write_record(
            cache / "record.json",
            dict(
                schema="v35_complete_task_gradient.v1",
                binding=binding,
                binding_sha256=context["math_context_id"],
                task_plan_id=plan["id"],
                task=task,
                parameter_spec=spec,
                complete_task=True,
                gradient_sha256=hashlib.sha256(raw).hexdigest(),
                gradient_bytes=len(raw),
            ),
        )
        (cache / "gradient.pt").write_bytes(raw)
    write_record(
        directory / "shard02/result/record.json", dict(task_ids=assignments[2]["task_ids"])
    )
    bindings = dict(
        shard02=dict(
            protocol_scope="parent",
            directory=str(directory / "shard02"),
            result=inheritance.entry(directory / "shard02/result/record.json"),
        )
    )
    authority_path = tmp_path / "authority/record.json"
    write_record(
        authority_path, dict(partial_class_recovery=inheritance.PARTIAL_CLASS_AUTHORIZATION)
    )
    return SimpleNamespace(
        root=root,
        parent=parent,
        directory=directory,
        target=target,
        context=context,
        plan=plan,
        bindings=bindings,
        authority=inheritance.entry(authority_path),
    )


def test_partial_class_overlay_is_exact_disjoint_186_plus_558(partial_class, monkeypatch):
    p = partial_class
    original_open = Path.open

    def guarded(path, *args, **kwargs):
        assert path.suffix != ".pt", "registration must not reread parent gradient bytes"
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)
    value = inheritance.inspect_task_cache_overlay(
        p.directory, p.target, p.context, p.plan, p.bindings, p.authority
    )
    assert len(value["parent_task_ids"]) == len(value["parent_records"]) == 186
    assert len(value["local_task_ids"]) == 558
    assert set(value["parent_task_ids"]).isdisjoint(value["local_task_ids"])
    assert set(value["parent_task_ids"]) | set(value["local_task_ids"]) == set(p.plan["task_ids"])
    assert value["parent_task_indices"] == list(range(2, 744, 4))
    assert value["binding_sha256"] == p.context["math_context_id"]
    assert value["allowed_new_stages"] == ["shard00", "shard01", "shard03"]
    assert value["local_cache_root"] == str(p.target / "task_cache")
    assert not p.root.exists()


@pytest.mark.parametrize(
    "mutation",
    [
        "foreign_context",
        "duplicate_partition",
        "wrong_binding",
        "extra_parent_task",
        "missing_gradient",
        "extra_completed_shard",
    ],
)
def test_partial_overlay_rejects_unapproved_or_changed_task_partition(partial_class, mutation):
    p = partial_class
    if mutation == "foreign_context":
        p.context["seed"] = 389
    elif mutation == "duplicate_partition":
        p.plan["assignments"][0]["task_ids"][0] = p.plan["assignments"][2]["task_ids"][0]
    elif mutation == "wrong_binding":
        rewrite(p.directory / "task_cache/task0002/record.json", binding_sha256="foreign")
    elif mutation == "extra_parent_task":
        (p.directory / "task_cache/task0000").mkdir()
    elif mutation == "missing_gradient":
        (p.directory / "task_cache/task0002/gradient.pt").unlink()
    else:
        p.bindings["shard00"] = dict(protocol_scope="parent")
    with pytest.raises((ValueError, FileNotFoundError)):
        inheritance.inspect_task_cache_overlay(
            p.directory, p.target, p.context, p.plan, p.bindings, p.authority
        )


def test_four_hour_extension_requires_exact_explicit_authority(partial_class):
    p = partial_class
    assert inheritance._partial_class_authority(p.root, p.authority) == p.authority
    assert inheritance.PARTIAL_CLASS_AUTHORIZATION["window_seconds"] == 14400
    assert inheritance.PARTIAL_CLASS_AUTHORIZATION["original_phase_deadline_extended"] is True
    altered = dict(inheritance.PARTIAL_CLASS_AUTHORIZATION, outer_compute_budget_reset=True)
    rewrite(Path(p.authority["path"]), partial_class_recovery=altered)
    reference = inheritance.entry(p.authority["path"])
    with pytest.raises(ValueError, match="four-hour class exception authority"):
        inheritance._partial_class_authority(p.root, reference)


def test_overlay_alias_reads_only_parent_shard02(partial_class, monkeypatch):
    p = partial_class
    overlay = inheritance.inspect_task_cache_overlay(
        p.directory, p.target, p.context, p.plan, p.bindings, p.authority
    )
    stages = {
        stage: dict(protocol_scope="current", directory=str(p.target / stage))
        for stage in inheritance.STAGES
    }
    stages["shard02"] = p.bindings["shard02"]
    item = dict(
        seed=251,
        arm="C-only",
        step=1192,
        original_context=inheritance.entry(p.directory / "context/record.json"),
        original_context_id=p.context["id"],
        origin_context_directory=str(p.directory),
        new_context_directory=str(p.target),
        stage_bindings=stages,
        task_cache_overlay=overlay,
    )
    body = dict(schema=inheritance.SCHEMA, new_root=str(p.root), context_inheritances=[item])
    monkeypatch.setattr(inheritance, "inspect_parent_recovery", lambda *_: body)
    inheritance.initialize_parent_recovery(p.root, p.parent)
    plan = dict(
        output_root=str(p.root),
        inheritance=inheritance.entry(p.root / "inheritance/record.json"),
        audit=p.authority,
    )
    assert inheritance.task_cache_overlay_binding(p.target, plan) == overlay
    assert inheritance.stage_directory(p.target, plan, "shard02") == p.directory / "shard02"
    assert inheritance.stage_directory(p.target, plan, "shard00") == p.target / "shard00"
    assert inheritance.replay_resume_binding(p.target, plan) is None
    plan["audit"] = dict(path="foreign")
    with pytest.raises(ValueError, match="same-point authority"):
        inheritance.task_cache_overlay_binding(p.target, plan)


def test_real_parent_read_only_preflight_when_explicitly_requested(tmp_path, monkeypatch):
    if os.environ.get("FINQA_V40_REAL_READ_ONLY") != "1":
        pytest.skip("explicitly requested read-only production metadata preflight only")
    parent = (
        Path(__file__).parents[1]
        / "artifacts/finance_research_20260928/finqa_v6_01"
        / "v18_researcher_continuation_01/v25_training_replication_01"
        / "production_resume_01/recovery_01"
    ).resolve()
    authority = tmp_path / "authorization/record.json"
    write_record(authority, dict(partial_class_recovery=inheritance.PARTIAL_CLASS_AUTHORIZATION))
    original_open = Path.open

    def guarded(path, *args, **kwargs):
        assert path.suffix != ".pt" or path.parent.name == "response000261", (
            "only the small authorized response prefix may be byte-read in metadata preflight"
        )
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)
    value = inheritance.inspect_parent_recovery(
        parent.parent / "recovery_02", parent, authorization_record=inheritance.entry(authority)
    )
    assert value["inherited_resource_wait_seconds"] == 28088
    assert (value["remaining_optimizer_updates"], value["remaining_outer_updates"]) == (4143, 11)
    assert value["remaining_scientific_budget"]["remaining_new_feedback_episodes"] == 7000
    assert len(value["completed_evaluations"]) == 4
    contexts = {(row["seed"], row["arm"]): row for row in value["context_inheritances"]}
    assert set(contexts) == {(251, "C-only"), (251, "Full"), (389, "Full")}
    c251 = contexts[(251, "C-only")]
    assert len(c251["task_cache_overlay"]["parent_records"]) == 186
    assert len(c251["task_cache_overlay"]["local_task_ids"]) == 558
    assert c251["inherited_compute_seconds"] == 6785
    assert c251["class_deadline_override"]["original_phase_deadline_extended"] is True
    assert c251["class_deadline_override"]["original_deadline_epoch"] == 1791821820.3839567
    assert c251["class_deadline_override"]["window_seconds"] == 14400
    assert contexts[(389, "Full")]["inherited_compute_seconds"] == 44470
    assert contexts[(389, "Full")]["phase_deadlines_epoch"]["replay_R3"] == 1791855078.1726341
    assert contexts[(389, "Full")]["durable_replay_restore"]["remaining_response_count"] == 186
