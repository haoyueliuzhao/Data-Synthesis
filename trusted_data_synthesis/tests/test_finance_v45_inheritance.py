"""Five-worker handoff proof and same-point metadata-only continuation contracts."""

import copy
import hashlib
import importlib
import sys
from pathlib import Path

import pytest
from test_finance_v38_inheritance import write_record

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
subject = importlib.import_module("finqa_v45_inheritance")


def authority():
    return dict(
        user_consent="暂时增至五个",
        max_gpu_workers=5,
        host_ram_admission_changed=True,
        host_ram_runtime_hard_gates_unchanged=True,
        time_limits_removed=True,
        automatic_recovery_authorized=True,
        unknown_feedback_retry_allowed=False,
    )


@pytest.mark.parametrize(
    "change",
    [
        dict(max_gpu_workers=6),
        dict(max_gpu_workers=4),
        dict(host_ram_admission_changed=False),
        dict(host_ram_runtime_hard_gates_unchanged=False),
        dict(unknown_feedback_retry_allowed=True),
    ],
)
def test_only_five_workers_without_ram_or_unknown_feedback_expansion(tmp_path, change):
    with pytest.raises(ValueError):
        subject._authorization(tmp_path, body={**authority(), **change})


def _protocol(root):
    return write_record(
        root / "protocol/record.json",
        dict(
            schema="v43_explicit_no_deadline_supervised_protocol.v1",
            output_root=str(root),
            supervision_root=str(root),
        ),
    )


def test_live_workers_are_rejected_before_preflight_can_authorize_signal(tmp_path):
    protocol = _protocol(tmp_path)
    queue = dict(
        protocol_id=protocol["id"],
        active_children=[dict(pid=999)],
        phase="RUNNING",
        pilot_accepted=True,
    )
    with pytest.raises(ValueError, match="fresh empty"):
        subject.preflight_clean_handoff(tmp_path, queue)


def test_nine_complete_endpoints_leave_unified_scoring_uninterrupted(tmp_path):
    protocol = _protocol(tmp_path)
    queue = dict(
        protocol_id=protocol["id"],
        active_children=[],
        phase="RUNNING",
        pilot_accepted=True,
        completed_evaluation_coordinates=[{}] * 9,
    )
    with pytest.raises(ValueError, match="NO_REMAINING_WORK"):
        subject.preflight_clean_handoff(tmp_path, queue)


def _handoff(root, protocol, preflight, *, worker_signals=0, returncode=1):
    write_record(
        root / "launch_01/record.json",
        dict(pid=999999991, birth="old-controller", protocol_id=protocol["id"]),
    )
    write_record(
        root / "supervisor/launch/record.json", dict(pid=999999992, birth="old-supervisor")
    )
    write_record(
        root / "supervisor/attempt0001/actual_exit/record.json",
        dict(
            pid=999999991,
            birth="old-controller",
            attempt_root=str(root),
            returncode=returncode,
            manual_stop_requested=True,
            stop_forwarded=True,
        ),
    )
    write_record(
        root / "supervisor/closeout/record.json",
        dict(
            status="STOPPED_BY_EXPLICIT_REQUEST",
            automatic_recovery_after_manual_stop=False,
            received_signals=[15],
        ),
    )
    write_record(
        root / "failure/record.json",
        dict(
            phase="PAUSED_DURABLE_BOUNDARY_NO_AUTO_RESUME",
            error_type="DurablePause",
            error="explicit safe stop requested",
            stop_error=None,
            actual_progress_audit_error=None,
        ),
    )
    write_record(
        root / "queue/status.json",
        dict(
            protocol_id=protocol["id"],
            active_children=[],
            phase="PAUSED_DURABLE_BOUNDARY_NO_AUTO_RESUME",
            global_external_resource_wait_seconds=100000.25,
        ),
    )
    preflight_path = root / "controlled_five_handoff/preflight/record.json"
    write_record(preflight_path, preflight)
    path = root / "controlled_five_handoff/closeout/record.json"
    write_record(
        path,
        dict(
            schema="v45_clean_natural_handoff.v1",
            status="CLEAN_NATURAL_HANDOFF",
            parent_root=str(root),
            parent_protocol=subject.entry(root / "protocol/record.json"),
            worker_signals_sent=worker_signals,
            all_gpu_locks_held=list(range(8)),
            fresh_empty_queue_verified=True,
            controller_original_process_exited=True,
            supervisor_original_process_exited=True,
            supervisor_signal_sent=True,
            supervisor_signals_sent=1,
            controller_launch=subject.entry(root / "launch_01/record.json"),
            supervisor_launch=subject.entry(root / "supervisor/launch/record.json"),
            supervisor_actual_controller_exit=subject.entry(
                root / "supervisor/attempt0001/actual_exit/record.json"
            ),
            supervisor_closeout=subject.entry(root / "supervisor/closeout/record.json"),
            actual_progress=subject.entry(root / "actual_final_progress/record.json"),
            parent_final_queue=subject.file_ref(root / "queue/status.json"),
            preflight=subject.entry(preflight_path),
            global_resource_wait_seconds=100001,
        ),
    )
    return path


@pytest.mark.parametrize(
    "signals,code,accepted", [(0, 1, True), (1, 1, False), (0, 0, False), (0, -9, False)]
)
def test_clean_handoff_requires_zero_worker_signals_and_real_controller_pause(
    tmp_path, signals, code, accepted
):
    protocol = _protocol(tmp_path)
    write_record(tmp_path / "actual_final_progress/record.json", dict(fixture=True))
    preflight = dict(
        status="CLEAN_NATURAL_WORKER_BOUNDARY",
        parent_protocol=subject.entry(tmp_path / "protocol/record.json"),
        launched_workers_all_complete_and_exit_zero=True,
        worker_signals_sent=0,
        observed_stage_bindings=[],
    )
    path = _handoff(tmp_path, protocol, preflight, worker_signals=signals, returncode=code)
    if accepted:
        assert (
            subject._read_handoff(tmp_path, protocol, path)[1]["status"] == "CLEAN_NATURAL_HANDOFF"
        )
    else:
        with pytest.raises(ValueError):
            subject._read_handoff(tmp_path, protocol, path)


def _checkpoint(directory, step):
    directory.mkdir(parents=True)
    raw = b"metadata-only simulation; never loaded as a scientific tensor"
    (directory / "state.pt").write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    write_record(
        directory / "record.json",
        dict(
            seed=389,
            arm="Static",
            step=step,
            phase="step",
            state_sha256=digest,
            actual_state_digest="CPU_METADATA_FIXTURE_" + str(step),
        ),
    )
    return dict(
        path=str(directory),
        record=subject.file_ref(directory / "record.json"),
        state=dict(path=str(directory / "state.pt"), sha256=digest),
        phase="step",
        actual_state_digest="CPU_METADATA_FIXTURE_" + str(step),
    )


def test_complete_clean_handoff_initializes_actual_shaped_frontier_without_tensor_reads(
    tmp_path, monkeypatch
):
    """Real accepted metadata plus an isolated mocked quiescent cut; never signals."""
    actual = Path(__file__).parents[1] / (
        "artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/"
        "v25_training_replication_01/production_resume_01/recovery_04"
    )
    if not (actual / "contexts/seed251/full/step0894_outer/train/result/record.json").exists():
        pytest.skip("real completed V43 stage metadata unavailable")
    root, target = tmp_path / "recovery_04", tmp_path / "host_memory_admission_01"
    old_protocol = subject.checked(actual / "protocol/record.json")
    original = subject.read_ref(old_protocol["inheritance"])
    prior = copy.deepcopy({key: value for key, value in original.items() if key != "id"})
    prior["new_root"] = str(root)
    success = {
        (251, "Full", 894): ["distribution", "train"],
        (389, "C-only", 894): ["virtual_point"],
        (389, "Full", 596): ["shard01", "shard02", "shard03"],
    }
    for item in prior["context_inheritances"]:
        olddir = Path(item["new_context_directory"])
        directory = root / olddir.relative_to(actual)
        context = subject.read_ref(item["original_context"])
        plan = subject.read_ref(context["task_plan"])
        item["new_context_directory"] = str(directory)
        for stage in success[(item["seed"], item["arm"], item["step"])]:
            binding = subject.inspect_stage(
                olddir / stage,
                old_protocol,
                context,
                stage,
                plan,
                protocol_ref=subject.entry(actual / "protocol/record.json"),
            )
            assert binding is not None
            item["stage_bindings"][stage] = binding
            prior["all_parent_stage_bindings"].append(binding)
        for stage, binding in item["stage_bindings"].items():
            if binding["protocol_scope"] == "current":
                binding["directory"] = str(directory / stage)
        write_record(
            directory / "queue/status.json",
            dict(at="2026-10-14T14:00:00+00:00", compute_seconds=item["inherited_compute_seconds"]),
        )
    unstarted = actual / "contexts/seed251/full/step1192_outer"
    context = subject.checked(unstarted / "context/record.json")
    unstarted_target = root / unstarted.relative_to(actual)
    prior["context_inheritances"].append(
        dict(
            seed=251,
            arm="Full",
            step=1192,
            new_context_directory=str(unstarted_target),
            original_context=subject.entry(unstarted / "context/record.json"),
            original_context_id=context["id"],
            origin_context_directory=str(unstarted),
            stage_bindings={
                stage: dict(protocol_scope="current", directory=str(unstarted_target / stage))
                for stage in subject.STAGES
            },
        )
    )
    inherited = write_record(root / "inheritance/record.json", prior)
    for item in inherited["context_inheritances"]:
        write_record(
            Path(item["new_context_directory"]) / "context/record.json",
            dict(
                schema=subject.source.ALIAS_SCHEMA,
                inheritance=subject.entry(root / "inheritance/record.json"),
                **{
                    key: item[key]
                    for key in (
                        "new_context_directory",
                        "original_context",
                        "original_context_id",
                        "origin_context_directory",
                    )
                },
            ),
        )
    protocol_body = {key: value for key, value in old_protocol.items() if key != "id"}
    protocol_body.update(
        output_root=str(root),
        supervision_root=str(root),
        inheritance=subject.entry(root / "inheritance/record.json"),
    )
    protocol = write_record(root / "protocol/record.json", protocol_body)
    write_record(root / "implementation/record.json", dict(fixture=True))
    progress = subject.read_ref(old_protocol["initial_state_snapshot"])
    progress = copy.deepcopy({key: value for key, value in progress.items() if key != "id"})
    for arm in progress["arms"]:
        if (arm["seed"], arm["arm"]) == (251, "Full"):
            arm.update(
                step=1192,
                checkpoint=context["checkpoint"],
                outer_done=[298, 596, 894],
                remaining_updates=298,
                remaining_outers=1,
                due_outer=True,
            )
    # Simulate a fully sealed Static389 model whose endpoint generation has not started.
    static_dir = root / "contexts/seed389/static/step1221_train"
    initial_checkpoint = _checkpoint(tmp_path / "fake_training/step1221_step", 1221)
    final_checkpoint = _checkpoint(tmp_path / "fake_training/step1490_step", 1490)
    static = subject.checked(actual / "contexts/seed389/static/step1221_train/context/record.json")
    static = {key: value for key, value in static.items() if key != "id"}
    static.update(
        run_root=str(static_dir),
        outer_root=str(static_dir),
        checkpoint=initial_checkpoint,
        arm_root=str(tmp_path / "fake_training"),
        pre_state_digest=initial_checkpoint["actual_state_digest"],
    )
    static = write_record(static_dir / "context/record.json", static)
    template = actual / "contexts/seed251/full/step0894_outer/train"
    for marker in ("launch", "result", "exit"):
        value = subject.checked(template / marker / "record.json")
        value = {key: data for key, data in value.items() if key != "id"}
        value.update(protocol_id=protocol["id"], context_id=static["id"])
        if marker == "result":
            value.update(
                seed=389,
                arm="Static",
                initial_step=1221,
                committed_step=1490,
                actual_optimizer_steps=269,
                outer_committed=False,
                outer_done=[],
                outer_checkpoint=None,
                first_sft_after_outer=None,
                next_checkpoint=final_checkpoint["path"],
                endpoint_complete=True,
                endpoint_result=str(tmp_path / "fake_training/result/record.json"),
            )
        write_record(static_dir / "train" / marker / "record.json", value)
    write_record(
        tmp_path / "fake_training/result/record.json",
        dict(
            seed=389,
            arm="Static",
            final_checkpoint=final_checkpoint,
            result=dict(committed_step=1490),
            test_opened=False,
        ),
    )
    for arm in progress["arms"]:
        if (arm["seed"], arm["arm"]) == (389, "Static"):
            arm.update(
                step=1490, checkpoint=final_checkpoint, remaining_updates=0, remaining_outers=0
            )
    progress.update(
        completed_physical_updates=9834,
        remaining_physical_updates=1788,
        completed_outers=18,
        remaining_outers=6,
    )
    write_record(root / "actual_final_progress/record.json", progress)
    queue = dict(
        protocol_id=protocol["id"],
        active_children=[],
        phase="RUNNING",
        pilot_accepted=True,
        completed_evaluation_coordinates=[
            dict(seed=x["seed"], arm=x["arm"]) for x in prior["completed_evaluations"]
        ],
    )
    original_read = Path.read_bytes

    def no_tensor_reads(path):
        assert path.suffix != ".pt", "handoff metadata audit must not read a tensor"
        return original_read(path)

    monkeypatch.setattr(Path, "read_bytes", no_tensor_reads)
    preflight = subject.preflight_clean_handoff(root, queue)
    assert preflight["worker_signals_sent"] == 0
    record = _handoff(root, protocol, preflight)
    auth = write_record(target / "authorization/record.json", authority())
    value = subject.initialize_parent_handoff(
        target,
        root,
        handoff_record=record,
        authorization_record=subject.entry(target / "authorization/record.json"),
    )
    assert auth["max_gpu_workers"] == value["max_gpu_workers"] == 5
    assert value["inherited_resource_wait_seconds"] == 100001
    assert value["remaining_optimizer_updates"] == 1788 and value["remaining_outer_updates"] == 6
    assert value["remaining_scientific_budget"]["remaining_new_feedback_episodes"] == 3500
    assert len(value["completed_evaluations"]) == 5
    assert any(row["seed"] == 251 and row["arm"] == "Full" for row in value["unused_contexts"])
    c389 = next(
        item
        for item in value["context_inheritances"]
        if (item["seed"], item["arm"]) == (389, "C-only")
    )
    result = subject.read_ref(c389["stage_bindings"]["virtual_point"]["result"])
    assert result["inherited_feedback_episodes"] == 450 and result["new_feedback_episodes"] == 250
    assert result["explicitly_reexecuted_unreturned_requests"] == 1
    assert c389["stage_bindings"]["virtual_point"]["protocol_ref"] == subject.entry(
        actual / "protocol/record.json"
    )
    assert (
        c389["feedback_resume"]["new_feedback_base_root"]
        == next(i for i in prior["context_inheritances"] if i.get("arm") == "C-only")[
            "feedback_resume"
        ]["new_feedback_base_root"]
    )
    assert (Path(c389["new_context_directory"]) / "context/record.json").is_file()
