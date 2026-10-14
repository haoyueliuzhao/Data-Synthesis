"""CPU-only automatic recovery safety classes and real whole-task ownership."""

import copy
import importlib
import sys
from pathlib import Path

import pytest
from test_finance_v38_inheritance import write_record
from test_finance_v42_task_overlay import data, overlay, values  # noqa: F401

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
subject = importlib.import_module("finqa_v43_inheritance")


def authority():
    return dict(
        user_consent="授权修复版运行，取消截止时间限制，设置自动恢复",
        time_limits_removed=True,
        automatic_recovery_authorized=True,
        unknown_feedback_retry_allowed=False,
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("time_limits_removed", False),
        ("automatic_recovery_authorized", False),
        ("unknown_feedback_retry_allowed", True),
    ],
)
def test_new_authority_is_explicit_and_does_not_authorize_unknown_feedback(tmp_path, field, value):
    body = authority()
    body[field] = value
    with pytest.raises(ValueError, match="safe-only"):
        subject._authorization(tmp_path, body=body)


def stopped_pool(
    tmp_path,
    stage="shard01",
    kind="TailStopRequested",
    error="stop requested at class_row_end",
    *,
    pre_cuda=False,
    resources=None,
):
    root = tmp_path / "recovery_04"
    protocol = write_record(
        root / "protocol/record.json",
        dict(schema="v43_explicit_no_deadline_supervised_protocol.v1", output_root=str(root)),
    )
    identity = dict(pid=999999999, birth="fixture_not_live")
    write_record(root / "launch_01/record.json", identity)
    write_record(
        root / "failure/record.json",
        dict(
            phase="STOPPED_FAILURE_NO_RETRY",
            stop_error=None,
            actual_progress_audit_error=None,
            error="worker reported failure: " + stage,
        ),
    )
    write_record(
        root / "queue/status.json", dict(phase="STOPPED_FAILURE_NO_RETRY", active_children=[])
    )
    write_record(
        root / "actual_final_progress/record.json",
        dict(endpoint_scores_or_answers_read=False, original_state_or_feedback_modified=False),
    )
    directory = root / (
        "evaluations/seed389_static/generate"
        if stage == "generate"
        else "contexts/seed389/full/step0596_outer/" + stage
    )
    shared = dict(protocol_id=protocol["id"], context_id="fixture-point", stage=stage)
    write_record(directory / "launch/record.json", dict(shared, **identity))
    write_record(directory / "exit/record.json", dict(shared, returncode=1, stop_requested=True))
    write_record(
        directory / "failure/record.json",
        dict(shared, error_type=kind, error=error, resources=resources),
    )
    write_record(
        directory / "pre_cuda_wait/status.json",
        dict(phase="STOPPED" if pre_cuda else "READY", cuda_initialized=False),
    )
    return root


@pytest.mark.parametrize("stage", ["shard01", "train", "replay_R3", "distribution"])
def test_resource_stop_has_actual_exit_boundary_for_supported_consumers(tmp_path, stage):
    result = subject.validate_safe_recovery(stopped_pool(tmp_path, stage))
    assert result["allowed"] is True
    assert result["unknown_feedback_retry"] is False


@pytest.mark.parametrize("stage", ["virtual_point", "generate"])
def test_partial_generation_after_cuda_is_manual_not_retried(tmp_path, stage):
    result = subject.validate_safe_recovery(
        stopped_pool(tmp_path, stage, resources={"observations": [{"label": "after_model_load"}]})
    )
    assert result["allowed"] is False
    assert result["reason"] == "unsupported_partial_generation_or_unknown_feedback_requires_user"


@pytest.mark.parametrize("stage", ["virtual_point", "generate"])
def test_generation_pre_cuda_zero_call_failure_can_continue(tmp_path, stage):
    result = subject.validate_safe_recovery(
        stopped_pool(
            tmp_path,
            stage,
            "AdmissionStopped",
            "safe stop requested before CUDA admission",
            pre_cuda=True,
        )
    )
    assert result["allowed"] is True
    assert result["interrupted_stages"][0]["recovery_kind"] == "pre_cuda_no_scientific_call"


def test_numerical_or_binding_failure_overrides_resource_words(tmp_path):
    result = subject.validate_safe_recovery(
        stopped_pool(tmp_path, error="gradient checksum mismatch after out of memory")
    )
    assert result["allowed"] is False
    assert result["reason"] == "numerical_or_binding_failure_requires_user"


@pytest.mark.parametrize(
    "kind,error,observed",
    [
        ("TailMemoryError", "V34 CUDA memory envelope failed: {}", True),
        ("TailMemoryError", "V34 CUDA memory envelope failed: {}", False),
        ("ValueError", "production host RAM envelope failed", True),
        ("ValueError", "production host RAM envelope failed", False),
    ],
)
def test_memory_gate_error_requires_actual_structured_failure(tmp_path, kind, error, observed):
    resources = dict(
        limits_unchanged=True, observations=[dict(allocated_pass=not observed, free_pass=True)]
    )
    result = subject.validate_safe_recovery(
        stopped_pool(tmp_path, kind=kind, error=error, resources=resources)
    )
    assert result["allowed"] is observed


def test_exact_pre_cuda_ram_failure_is_recoverable(tmp_path):
    result = subject.validate_safe_recovery(
        stopped_pool(
            tmp_path,
            "train",
            "AdmissionError",
            "host available RAM below 96 GiB reserve",
            pre_cuda=True,
        )
    )
    assert result["allowed"] is True


def _context(fixture):
    path = fixture.parent_root.parent / "task_plan/record.json"
    write_record(path, {key: value for key, value in fixture.data.plan.items() if key != "id"})
    return dict(
        fixture.context,
        task_plan=subject.entry(path),
        math_context_id=subject.digest(fixture.data.binding),
    )


def test_initial_277_cache_keeps_time_as_history_only(overlay):  # noqa: F811
    context = _context(overlay)
    old = dict(overlay.binding, class_deadline_epoch=12345)
    value = subject._cache_union(context, overlay.directory, old)
    assert value["schema"] == subject.PARTIAL_CACHE_SCHEMA
    assert value["parent_tasks"] == 277 and value["new_tasks"] == 467
    assert value["class_deadline_epoch"] is None
    assert value["historical_class_deadline_epoch"] == 12345


def test_auto_partial_tasks_union_new_cache_without_recomputing_parent(overlay):  # noqa: F811
    contexts = importlib.import_module("finqa_v37_task_cache")
    original = importlib.import_module("finqa_v35_task_cache")
    f = overlay
    context = _context(f)
    first = subject._cache_union(context, f.directory, dict(f.binding, class_deadline_epoch=12345))
    local = contexts.ProductionTaskCache(
        f.directory / "task_cache",
        f.data.binding,
        f.data.plan,
        f.data.spec,
        f.data.rt,
        original_cache_module=original,
    )
    task = f.local_ids[0]
    local.commit(task, values(local.task(task)["index"]), receipt={"stage": "shard01"})
    view, merged = subject._automatic_cache(
        context,
        f.directory,
        f.directory.parent / "next",
        dict(task_cache_overlay=first),
        {"shard00": {}},
    )
    assert view is None and merged["parent_tasks"] == 278 and merged["new_tasks"] == 466
    assert len(merged["cache_sources"]) == 2
    assert task in merged["parent_task_ids"] and task not in merged["local_task_ids"]
    assert merged["allowed_new_stages"] == ["shard01", "shard02", "shard03"]


def test_replay_uses_maximum_actual_prefix_and_defers_tensor_load(tmp_path, monkeypatch):
    root = tmp_path / "replay_R3"
    binding = dict(
        execution_profile_id="context",
        point_id="point",
        response_count=3,
        denominator=700,
        gradient_length_normalized=False,
    )
    for cursor in (1, 2):
        folder = root / "checkpoints" / f"response{cursor:06d}"
        write_record(
            folder / "record.json",
            dict(
                schema="v19_response_boundary_checkpoint.v1",
                binding=binding,
                cursor=cursor,
                response_prefix_complete=True,
                no_feedback_generation=True,
                optimizer_steps_performed=0,
                full_replay_complete=False,
                state_sha256="a" * 64,
            ),
        )
        (folder / "state.pt").write_bytes(b"not loaded during registration")
    write_record(root / "launch/record.json", dict(at="2026-10-14T00:00:00+00:00"))
    write_record(root / "exit/record.json", dict(returncode=1))
    virtual = tmp_path / "virtual_point/result/record.json"
    write_record(virtual, dict(point_id="point", response_count=3))
    original = Path.read_bytes

    def bounded(path):
        assert path.suffix != ".pt"
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", bounded)
    result = subject._replay_prefix(root, dict(id="context"), dict(result=subject.entry(virtual)))
    assert result["inherited_response_count"] == 2 and result["remaining_response_count"] == 1
    assert result["state_bytes_verified"] is False
    with pytest.raises(ValueError, match="point/cohort/cursor"):
        subject._replay_prefix(root, dict(id="different"), dict(result=subject.entry(virtual)))


def test_actual_metadata_frontier_can_make_one_safe_automatic_attempt(tmp_path):
    """Real immutable metadata, isolated simulated failure; no tensor/model/API use."""
    parent = Path(__file__).parents[1] / (
        "artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/"
        "v25_training_replication_01/production_resume_01/recovery_03"
    )
    if not (parent / "closeout_01/record.json").exists():
        pytest.skip("actual stopped V42 metadata not available")
    original_root = parent.parent / "recovery_04"
    # The production directory may already be prepared when tests are rerun;
    # read its sealed initial inheritance instead of attempting registration.
    if (original_root / "inheritance/record.json").exists():
        initial = subject.checked(original_root / "inheritance/record.json")
        initial = {key: value for key, value in initial.items() if key != "id"}
    else:
        initial = subject.inspect_parent_recovery(
            original_root, parent, authorization_body=authority()
        )
    root = tmp_path / "recovery_04"
    initial = copy.deepcopy(initial)
    initial["new_root"] = str(root)
    for item in initial["context_inheritances"]:
        old_directory = Path(item["new_context_directory"])
        directory = root / old_directory.relative_to(original_root)
        item["new_context_directory"] = str(directory)
        for stage, binding in item["stage_bindings"].items():
            if binding["protocol_scope"] == "current":
                binding["directory"] = str(directory / stage)
        if item.get("task_cache_overlay"):
            item["task_cache_overlay"]["local_cache_root"] = str(directory / "task_cache")
        if item.get("feedback_resume"):
            item["feedback_resume"]["new_feedback_base_root"] = str(
                directory / "feedback_resume_view"
            )
    subject._publish_aliases(root, initial)
    protocol = write_record(
        root / "protocol/record.json",
        dict(
            schema="v43_explicit_no_deadline_supervised_protocol.v1",
            output_root=str(root),
            supervision_root=str(root),
            inheritance=subject.entry(root / "inheritance/record.json"),
        ),
    )
    write_record(root / "implementation/record.json", dict(fixture=True))
    progress = subject.checked(parent / "actual_final_progress/record.json")
    write_record(
        root / "actual_final_progress/record.json",
        {key: value for key, value in progress.items() if key != "id"},
    )
    identity = dict(pid=999999999, birth="fixture_not_live")
    write_record(root / "launch_01/record.json", identity)
    write_record(
        root / "queue/status.json",
        dict(
            phase="STOPPED_FAILURE_NO_RETRY",
            active_children=[],
            global_external_resource_wait_seconds=93725.25,
        ),
    )
    write_record(
        root / "failure/record.json",
        dict(
            phase="STOPPED_FAILURE_NO_RETRY",
            stop_error=None,
            actual_progress_audit_error=None,
            error="worker reported failure: distribution",
        ),
    )
    for item in initial["context_inheritances"]:
        directory = Path(item["new_context_directory"])
        write_record(
            directory / "queue/status.json",
            dict(at="2026-10-14T07:00:00+00:00", compute_seconds=item["inherited_compute_seconds"]),
        )
    item = initial["context_inheritances"][0]
    directory = Path(item["new_context_directory"]) / "distribution"
    shared = dict(
        protocol_id=protocol["id"], context_id=item["original_context_id"], stage="distribution"
    )
    write_record(
        directory / "launch/record.json", dict(shared, **identity, at="2026-10-14T07:00:00+00:00")
    )
    write_record(
        directory / "exit/record.json",
        dict(
            shared,
            at="2026-10-14T07:00:10+00:00",
            elapsed_worker_wall_seconds=10.0,
            returncode=1,
            stop_requested=True,
        ),
    )
    write_record(
        directory / "failure/record.json",
        dict(
            shared,
            error_type="AdmissionError",
            error="host available RAM below 96 GiB reserve",
            resources=None,
        ),
    )
    write_record(
        directory / "pre_cuda_wait/status.json", dict(phase="FAILED", cuda_initialized=False)
    )
    result = subject.inspect_automatic_recovery(
        root / "attempts/attempt0002", root, authorization_body=authority()
    )
    assert result["inherited_resource_wait_seconds"] == 93726
    assert result["remaining_optimizer_updates"] == 2355 and result["remaining_outer_updates"] == 7
    assert [item["inherited_compute_seconds"] for item in result["context_inheritances"]] == [
        45941,
        29728,
        10688,
    ]
    assert all(item["phase_deadlines_epoch"] == {} for item in result["context_inheritances"])
    assert result["remaining_scientific_budget"]["remaining_new_feedback_episodes"] == 3750
    assert result["remaining_scientific_budget"]["future_first_sampling_feedback_episodes"] == 3500
    assert result["context_inheritances"][2]["task_cache_overlay"]["parent_tasks"] == 277
