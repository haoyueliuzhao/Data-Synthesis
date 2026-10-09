"""CPU-only one-tail scope, resource gates and sealed queue adapter tests."""

import copy
import importlib
import signal
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
queue = importlib.import_module("finqa_v34_tail_controller")


def protocol():
    return dict(
        id="protocol",
        fixed_gpu_index=7,
        fixed_gpu_uuid="GPU-7",
        gpu_uuids={str(i): f"GPU-{i}" for i in queue.ALLOWED_GPUS},
        cpu_affinity={str(i): "0-3" for i in queue.ALLOWED_GPUS},
    )


def observation(label, *, boundary=True):
    return dict(
        label=label,
        boundary=boundary,
        allocated_bytes=1024,
        reserved_bytes=2048,
        peak_allocated_bytes=1536,
        peak_reserved_bytes=2048,
        free_bytes=3 * 1024**3,
        total_bytes=80 * 1024**3,
        limits=dict(
            allocated_memory_limit_bytes=queue.MAXIMUM_ALLOCATED_BYTES,
            free_memory_reserve_bytes=queue.MINIMUM_DEVICE_FREE_BYTES,
        ),
        allocated_pass=True,
        free_pass=True,
        stop_requested=False,
        passed=True,
    )


def result():
    return dict(
        protocol_id="protocol",
        stage=queue.STAGE,
        status="COMPLETE",
        numeric_pass=True,
        backend_version=queue.BACKEND_VERSION,
        API_calls=0,
        new_sampling_calls=0,
        scoring_calls=0,
        optimizer_steps=0,
        replayed_responses=0,
        class_gradient_passes=1,
        reused_completed_responses=573,
        original_B_resume_authorized=False,
        comparison=dict.fromkeys(queue.COHORT_COMPARISON_KEYS, True),
        resources=dict(
            all_gates_passed=True,
            limits_unchanged=True,
            maximum_allocated_bytes=queue.MAXIMUM_ALLOCATED_BYTES,
            minimum_device_free_bytes=queue.MINIMUM_DEVICE_FREE_BYTES,
            observed_peak_allocated_bytes=1536,
            observed_minimum_boundary_free_bytes=3 * 1024**3,
            peak_resets_before_model_load=1,
            peak_resets_after_model_loading_begins=0,
            helper_peak_reset_calls=0,
            observations=[
                observation(label)
                for label in (
                    "after_model_load.after_cleanup",
                    "class_gradients_complete.after_cleanup",
                    "after_distribution.after_cleanup",
                )
            ],
        ),
    )


def test_only_complete_one_pass_zero_replay_supplement_is_accepted():
    measured = result()
    assert queue.check_result(protocol(), queue.STAGE, measured) is measured


@pytest.mark.parametrize(
    "key,value",
    [
        ("protocol_id", "other"),
        ("stage", "cohort_resume"),
        ("status", "OOM"),
        ("numeric_pass", False),
        ("backend_version", "unregistered"),
        ("API_calls", 1),
        ("new_sampling_calls", 1),
        ("scoring_calls", 1),
        ("optimizer_steps", 1),
        ("replayed_responses", 1),
        ("replayed_responses", False),
        ("class_gradient_passes", 2),
        ("class_gradient_passes", True),
        ("reused_completed_responses", 572),
        ("original_B_resume_authorized", True),
    ],
)
def test_failed_or_expanded_scientific_work_is_rejected(key, value):
    measured = result()
    measured[key] = value
    with pytest.raises(ValueError):
        queue.check_result(protocol(), queue.STAGE, measured)


@pytest.mark.parametrize("key", queue.COHORT_COMPARISON_KEYS)
def test_every_numerical_comparison_is_independently_required(key):
    measured = result()
    measured["comparison"][key] = False
    with pytest.raises(ValueError, match="comparisons"):
        queue.check_result(protocol(), queue.STAGE, measured)


def test_additional_failed_comparison_cannot_be_hidden_by_the_original_eight():
    measured = result()
    measured["comparison"]["additional_guard"] = False
    with pytest.raises(ValueError, match="comparisons"):
        queue.check_result(protocol(), queue.STAGE, measured)


@pytest.mark.parametrize(
    "key,value",
    [
        ("all_gates_passed", False),
        ("limits_unchanged", False),
        ("maximum_allocated_bytes", 77 * 1024**3),
        ("minimum_device_free_bytes", 1024**3),
        ("observed_peak_allocated_bytes", 1024),
        ("observed_minimum_boundary_free_bytes", 0),
        ("peak_resets_before_model_load", 2),
        ("peak_resets_after_model_loading_begins", 1),
        ("helper_peak_reset_calls", 1),
    ],
)
def test_resource_summary_cannot_relax_limits_or_contradict_observations(key, value):
    measured = result()
    measured["resources"][key] = value
    with pytest.raises(ValueError):
        queue.check_result(protocol(), queue.STAGE, measured)


@pytest.mark.parametrize(
    "key,value",
    [
        ("peak_allocated_bytes", 77 * 1024**3),
        ("free_bytes", 2 * 1024**3 - 1),
        ("passed", False),
        ("allocated_pass", False),
        ("free_pass", False),
        ("stop_requested", True),
        ("boundary", False),
        ("allocated_bytes", -1),
        ("peak_allocated_bytes", True),
        ("limits", {}),
    ],
)
def test_resource_event_values_are_checked_not_only_pass_flags(key, value):
    measured = result()
    measured["resources"]["observations"][0][key] = value
    with pytest.raises(ValueError):
        queue.check_result(protocol(), queue.STAGE, measured)


def test_nonboundary_free_dip_is_recorded_without_relaxing_boundary_gate():
    measured = result()
    transient = observation("inside_backward", boundary=False)
    transient["free_bytes"] = 0
    measured["resources"]["observations"].insert(1, transient)
    queue.check_result(protocol(), queue.STAGE, measured)
    transient["peak_allocated_bytes"] = 77 * 1024**3
    with pytest.raises(ValueError):
        queue.check_result(protocol(), queue.STAGE, measured)


@pytest.fixture
def registered(tmp_path, monkeypatch):
    root = tmp_path / "trial"
    monkeypatch.setattr(queue, "ROOT", root)
    common = queue.checked(queue.V33_ROOT / "protocol/record.json")
    monkeypatch.setattr(queue, "inherited_protocol", lambda: common)
    monkeypatch.setattr(queue, "verify_original_B_paused", lambda _: None)
    implementation = root / "implementation"
    implementation.mkdir(parents=True)
    original = queue.checked(queue.V33_ROOT / "implementation/record.json")
    hashes = {}
    for name in queue.FILES:
        (implementation / name).write_bytes(name.encode())
        hashes[name] = queue.sha(implementation / name)
    for name in original["sha256"]:
        (implementation / name).write_bytes((queue.V33_ROOT / "implementation" / name).read_bytes())
        hashes[name] = queue.sha(implementation / name)
    manifest = queue.publish(
        implementation / "record.json",
        dict(
            schema="v34_committed_tail_implementation.v1",
            at="test",
            source_commit="a" * 40,
            committed_files=list(queue.FILES),
            inherited_V33_files=list(original["sha256"]),
            inherited_V33_implementation=queue.entry(queue.V33_ROOT / "implementation/record.json"),
            sha256=hashes,
        ),
    )
    queue.publish(root / "authorization/record.json", queue.authorization_body())
    body = queue.protocol_body(
        common,
        manifest,
        root,
        at="test",
        observed=[dict(index=i, uuid=common["gpu_uuids"][str(i)]) for i in queue.ALLOWED_GPUS],
    )
    queue.publish(root / "protocol/record.json", body)
    return root, body


def test_registration_retains_scientific_inputs_but_no_new_replay_or_speedup(registered):
    root, _ = registered
    plan = queue.checked_protocol(root)
    common = queue.checked(queue.V33_ROOT / "protocol/record.json")
    assert plan["fixed_gpu_index"] == 7
    assert plan["stages"] == [queue.STAGE]
    assert plan["stage_timeout_seconds"] == {queue.STAGE: 4 * 3600}
    assert plan["maximum_micro_response_calls"] == plan["replayed_responses"] == 0
    assert plan["micro_variants"] == []
    assert plan["candidate_count"] == plan["class_gradient_passes"] == 1
    assert plan["no_new_speedup_claim"] is True
    for field in (
        "source_outer",
        "benchmark_manifest",
        "replay_binding_expected",
        "same_point_manifests",
        "original_scientific_protocol",
        "cpu_affinity",
    ):
        assert plan[field] == common[field]
    assert plan["tail_storage_policy"]["version"] == queue.BACKEND_VERSION
    assert plan["original_V33_failure_reclassified"] is False


@pytest.mark.parametrize(
    "field",
    [
        "fixed_gpu_index",
        "fixed_gpu_uuid",
        "stage_timeout_seconds",
        "allowed_gpu_indices",
        "class_gradient_passes",
        "candidate_count",
        "source_final_checkpoint",
        "source_final_checkpoint_state",
        "saved_gJ_digest",
        "maximum_allocated_bytes",
        "minimum_device_free_bytes",
        "replayed_responses",
        "reused_completed_responses",
        "original_B_resume_authorized",
        "tail_storage_policy",
        "replay_binding_expected",
        "resource_wait_budget_seconds",
        "no_automatic_retry",
        "no_implicit_fallback",
    ],
)
def test_even_rehashed_protocol_cannot_expand_authorization(registered, field):
    root, body = registered
    changed = copy.deepcopy(body)
    changed[field] = "changed"
    path = root / "protocol/record.json"
    path.unlink()
    queue.publish(path, changed)
    with pytest.raises(ValueError, match="fixed V34 contract"):
        queue.checked_protocol(root)


def test_inherited_source_bytes_and_order_are_immutable(registered):
    root, _ = registered
    (root / "implementation/finqa_v19_optimized_replay.py").write_bytes(b"changed")
    with pytest.raises(ValueError, match="frozen source bytes"):
        queue.checked_protocol(root)


def test_freeze_manifest_order_is_not_only_a_set(registered):
    root, _ = registered
    path = root / "implementation/record.json"
    manifest = queue.checked(path)
    manifest.pop("id")
    manifest["sha256"] = dict(reversed(list(manifest["sha256"].items())))
    path.unlink()
    queue.publish(path, manifest)
    with pytest.raises(ValueError, match="freeze order"):
        queue.checked_protocol(root)


def idle(index=7):
    return dict(index=index, uuid=f"GPU-{index}", free_mib=80000, processes=[])


def bare(tmp_path):
    ctl = queue.Controller.__new__(queue.Controller)
    ctl.root, ctl.protocol = tmp_path, protocol()
    ctl.wait_used, ctl.paired_gpu, ctl.stop, ctl.active = 0, None, False, None
    ctl.updates = []
    ctl.update = lambda phase, **extra: ctl.updates.append((phase, extra))
    ctl.verify_original_B_paused = lambda: None
    return ctl


def test_only_original_physical_gpu7_is_eligible_even_when_other_cards_are_idle():
    for index in range(8):
        assert queue.eligible(idle(index), protocol()) is (index == 7)
    assert not queue.eligible({**idle(), "processes": [{"pid": 42}]}, protocol())
    assert not queue.eligible({**idle(), "free_mib": queue.MINIMUM_FREE_MIB - 1}, protocol())
    assert not queue.eligible({**idle(), "uuid": "replaced"}, protocol())


def test_queue_waits_for_gpu7_and_never_takes_idle3_4_5(tmp_path, monkeypatch):
    ctl = bare(tmp_path)
    monkeypatch.setattr(
        queue,
        "inventory",
        lambda: [idle(3), idle(4), idle(5), {**idle(), "processes": [{"pid": 42}]}],
    )
    monkeypatch.setattr(queue.time, "sleep", lambda _: setattr(ctl, "stop", True))
    with pytest.raises(RuntimeError, match="before launch"):
        ctl.acquire_gpu(queue.STAGE)
    assert ctl.updates[-1][0] == "WAITING_FOR_IDLE_GPU"
    assert ctl.paired_gpu is None


def test_wait_budget_is_bounded_and_not_reset_on_a_new_poll(tmp_path):
    ctl = bare(tmp_path)
    ctl.wait_used = 24 * 3600
    with pytest.raises(ValueError, match="24-hour"):
        ctl.acquire_gpu(queue.STAGE)


def test_command_uses_new_worker_and_preserves_cpu_locality(tmp_path):
    command = queue.worker_command(tmp_path, queue.STAGE, idle(), protocol())
    assert command[:3] == ["/usr/bin/taskset", "--cpu-list", "0-3"]
    assert command[5] == str(tmp_path / "implementation" / queue.FILES[1])
    assert command[9] == queue.STAGE
    with pytest.raises(ValueError):
        queue.worker_command(tmp_path, "cohort_resume", idle(), protocol())


def test_cpu_initialization_counts_and_retry_is_forbidden(tmp_path):
    ctl = bare(tmp_path)
    ctl.active = dict(pid=123, GPU_context_not_yet_initialized=True)
    with pytest.raises(ValueError, match="one worker"):
        ctl.run_stage(queue.STAGE)
    ctl.active = None
    path = tmp_path / queue.STAGE / "launch/record.json"
    path.parent.mkdir(parents=True)
    path.write_text("{}")
    with pytest.raises(ValueError, match="retry forbidden"):
        ctl.run_stage(queue.STAGE)


def test_timeout_signals_only_the_owned_v34_worker(tmp_path, monkeypatch):
    ctl = bare(tmp_path)
    lock = (tmp_path / "fake.lock").open("w")
    ctl.acquire_gpu = lambda _: (idle(), lock)
    process = SimpleNamespace(pid=123, returncode=None)
    process.poll = lambda: process.returncode
    process.wait = lambda **kwargs: process.returncode
    clock = [0]
    monkeypatch.setattr(queue.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(queue.time, "sleep", lambda _: clock.__setitem__(0, clock[0] + 14400))
    monkeypatch.setattr(queue.subprocess, "Popen", lambda *args, **kwargs: process)
    monkeypatch.setattr(queue, "birth", lambda _: "owned")
    signals = []

    def stop(launch, sig):
        signals.append((launch["worker"], sig))
        process.returncode = -15
        return True

    monkeypatch.setattr(queue, "signal_owned", stop)
    with pytest.raises(ValueError, match="timed out"):
        ctl.run_stage(queue.STAGE)
    assert signals == [(str(tmp_path / "implementation" / queue.FILES[1]), signal.SIGTERM)]
    assert ctl.active is None and lock.closed
    assert queue.checked(tmp_path / queue.STAGE / "exit/record.json")["no_retry"] is True


def test_run_only_dispatches_the_tail_stage(tmp_path, monkeypatch):
    ctl = bare(tmp_path)
    monkeypatch.setattr(queue, "__file__", str(tmp_path / "implementation" / queue.FILES[0]))
    calls = []

    def stage(name):
        calls.append(name)
        return queue.publish(tmp_path / name / "result/record.json", result())

    ctl.run_stage = stage
    assert ctl.run() is True
    assert calls == [queue.STAGE]
    output = queue.checked(tmp_path / "result/record.json")
    assert output["replayed_responses"] == 0
    assert output["original_V33_failure_reclassified"] is False
    assert ctl.updates[-1][0] == "COMPLETE"
    with pytest.raises(FileExistsError):
        ctl.run()
    assert calls == [queue.STAGE]


def test_stage_failure_stops_without_automatic_retry_or_fallback(tmp_path, monkeypatch):
    ctl = bare(tmp_path)
    monkeypatch.setattr(queue, "__file__", str(tmp_path / "implementation" / queue.FILES[0]))
    calls = []

    def stage(name):
        calls.append(name)
        raise ValueError("resource gate failed")

    ctl.run_stage = stage
    with pytest.raises(ValueError, match="resource gate"):
        ctl.run()
    assert calls == [queue.STAGE]
    failure = queue.checked(tmp_path / "failure/record.json")
    assert failure["no_automatic_retry"] is failure["no_implicit_fallback"] is True
    assert ctl.updates[-1][0] == "STOPPED_FAILURE_NO_RETRY"


def test_original_v33_module_globals_remain_pristine():
    assert queue._common.ROOT == queue.V33_ROOT
    assert queue._common.STAGES == ("micro_R0", "micro_R3", "cohort_first", "cohort_resume")
    assert queue._runtime.STAGES == (queue.STAGE,)
    assert queue._common.FILES[0] == "finqa_v33_bounded_controller.py"
    assert queue._runtime.FILES == queue.FILES
