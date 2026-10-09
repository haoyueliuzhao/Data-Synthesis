"""CPU-only scope, queue, frozen-source and numerical-admission adapter tests."""

import copy
import importlib
import signal
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
queue = importlib.import_module("finqa_v33_bounded_controller")


def protocol():
    return dict(
        id="protocol",
        gpu_uuids={str(i): f"GPU-{i}" for i in queue.ALLOWED_GPUS},
        cpu_affinity={str(i): "0-3" for i in queue.ALLOWED_GPUS},
        cases=[dict(case_id="short_short", response_index=2)],
        actual_response_count=573,
        replay_binding_expected=dict(
            point_id="point",
            parameter_digest="theta",
            cohort_seal_sha256="seal",
            reward_sha256=queue.digest([1] * 700),
            response_order_sha256=queue.digest([[i, 0, f"call{i}"] for i in range(573)]),
            rng_restore_source=dict(field="pre_state.rng", digest="rng"),
            backend_version=queue.BACKEND_VERSION,
            adapter_source=dict(path="adapter", sha256="adapter"),
            inherited_V19_source=dict(path="v19", sha256="v19"),
        ),
    )


def micro(stage, seconds=10):
    variant = stage.removeprefix("micro_")
    return dict(
        protocol_id="protocol",
        stage=stage,
        status="COMPLETE",
        numeric_pass=True,
        variant=variant,
        active_variant=variant,
        unprofiled_seconds=seconds,
        API_calls=0,
        new_sampling_calls=0,
        scoring_calls=0,
        optimizer_steps=0,
        warmup_responses=1,
        profile_responses=0,
        diagnostic_profile=None,
        case_count=1,
        model_optimizer_rng_buffers_unchanged=True,
        case_results=[
            dict(
                case_id="short_short",
                response_index=2,
                bitwise_logp_equal=True,
                bitwise_gradient_equal=True,
                shape_dtype_keys_equal=True,
                state_unchanged=True,
                logp_digest="logp",
                baseline_logp_digest="logp",
                gradient_digest="gradient",
                baseline_gradient_digest="gradient",
                seconds=seconds,
                peak_allocated_bytes=1024,
                peak_reserved_bytes=2048,
            )
        ],
    )


def results(r0=12, r3=9):
    return {"micro_R0": micro("micro_R0", r0), "micro_R3": micro("micro_R3", r3)}


@pytest.mark.parametrize("r3,expected", [(10, "R3"), (9, "R3"), (10.01, None), (12, None)])
def test_exact_one_point_two_gate_uses_new_paired_baseline(r3, expected):
    result = queue.choose_variant(protocol(), results(r3=r3))
    assert result["selected_variant"] == expected
    assert result["prior_trial_timings_used"] is False
    assert result["selection_is_not_formal_B_resume_authority"] is True
    assert result["unprofiled_seconds"] == {"R0": 12, "R3": r3}


@pytest.mark.parametrize(
    "field,value",
    [
        ("status", "OOM"),
        ("numeric_pass", False),
        ("active_variant", "R2"),
        ("protocol_id", "old-trial"),
        ("warmup_responses", 2),
        ("profile_responses", 1),
        ("diagnostic_profile", {"id": "extra-profile"}),
        ("optimizer_steps", 1),
        ("unprofiled_seconds", float("nan")),
        ("model_optimizer_rng_buffers_unchanged", False),
    ],
)
def test_candidate_failure_cannot_fall_back_or_enter_cohort(field, value):
    measured = results()
    measured["micro_R3"][field] = value
    with pytest.raises(ValueError):
        queue.choose_variant(protocol(), measured)


def test_old_or_extra_candidate_is_forbidden():
    measured = results()
    measured["micro_R2"] = micro("micro_R2")
    with pytest.raises(ValueError, match="exactly one"):
        queue.choose_variant(protocol(), measured)


def binding():
    plan = protocol()
    expected = plan["replay_binding_expected"]
    return dict(
        schema="v32_fixed_replay_point_binding.v1",
        execution_profile_id="protocol",
        **{
            key: expected[key]
            for key in (
                "point_id",
                "parameter_digest",
                "cohort_seal_sha256",
                "reward_sha256",
                "response_order_sha256",
                "rng_restore_source",
            )
        },
        response_count=573,
        denominator=700,
        block_size=8,
        gradient_length_normalized=False,
        checkpoint_every_responses=16,
        replay_state_adapter=queue.BACKEND_VERSION,
        reward_vector=[1] * 700,
        response_order=[[i, 0, f"call{i}"] for i in range(573)],
        backend_identity=dict(
            protocol_id="protocol",
            variant="R3",
            version=queue.BACKEND_VERSION,
            adapter_source=expected["adapter_source"],
            inherited_V19_source=expected["inherited_V19_source"],
        ),
    )


def test_r3_enum_adapter_keeps_all_other_v32_point_guards_and_original_binding():
    original = binding()
    before = copy.deepcopy(original)
    queue.check_replay_binding(protocol(), original, variant="R3")
    assert original == before
    for field in (
        "point_id",
        "parameter_digest",
        "reward_sha256",
        "response_order_sha256",
        "rng_restore_source",
    ):
        changed = {**original, field: "wrong"}
        with pytest.raises(ValueError, match="differs from protocol"):
            queue.check_replay_binding(protocol(), changed, variant="R3")
    with pytest.raises(ValueError, match="only preregistered"):
        queue.check_replay_binding(protocol(), original, variant="R2")


@pytest.fixture
def registered(tmp_path, monkeypatch):
    """Synthetic registration under --basetemp, never in the formal trial root."""
    root = tmp_path / "trial"
    monkeypatch.setattr(queue, "ROOT", root)
    common = queue.checked(queue.V32_ROOT / "protocol/record.json")
    monkeypatch.setattr(queue, "inherited_protocol", lambda: common)
    monkeypatch.setattr(queue, "verify_original_B_paused", lambda _: None)
    implementation = root / "implementation"
    implementation.mkdir(parents=True)
    original = queue.checked(queue.V32_ROOT / "implementation/record.json")
    hashes = {}
    for name in original["sha256"]:
        data = (queue.V32_ROOT / "implementation" / name).read_bytes()
        (implementation / name).write_bytes(data)
        hashes[name] = queue.sha(implementation / name)
    for name in queue.FILES:
        (implementation / name).write_bytes(name.encode())
        hashes[name] = queue.sha(implementation / name)
    manifest = queue.publish(
        implementation / "record.json",
        dict(
            schema="v33_committed_bounded_implementation.v1",
            at="test",
            source_commit="a" * 40,
            committed_files=list(queue.FILES),
            inherited_V32_files=list(original["sha256"]),
            inherited_V32_implementation=queue.entry(queue.V32_ROOT / "implementation/record.json"),
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


def test_registered_protocol_retains_common_point_and_limits(registered):
    root, body = registered
    plan = queue.checked_protocol(root)
    assert plan["maximum_micro_response_calls"] == 10
    assert plan["candidate_count"] == 1
    assert plan["resident_saved_activation_budget_bytes"] == 16 * 1024**3
    assert plan["micro_variants"] == ["R0", "R3"]
    assert plan["stage_timeout_seconds"] == queue.STAGE_TIMEOUTS
    assert plan["profile_responses"] == 0
    assert "R2_minimum_extra_speedup" not in body


@pytest.mark.parametrize(
    "field",
    [
        "minimum_speedup",
        "cases",
        "maximum_micro_response_calls",
        "micro_variants",
        "profile_responses",
        "resident_saved_activation_budget_bytes",
        "candidate_count",
        "original_B_resume_authorized",
        "original_B_training_or_evaluation_allowed",
        "denominator",
        "actual_response_count",
        "pause_after_response",
        "stage_timeout_seconds",
        "resource_wait_budget_seconds",
        "allowed_gpu_indices",
        "replay_binding_expected",
        "activation_budget_admission_rule",
        "prior_timings_in_speed_ratio",
    ],
)
def test_even_rehashed_protocol_cannot_change_fixed_fields(registered, field):
    root, body = registered
    changed = copy.deepcopy(body)
    changed[field] = "changed"
    path = root / "protocol/record.json"
    path.unlink()
    queue.publish(path, changed)
    with pytest.raises(ValueError, match="fixed V33 contract"):
        queue.checked_protocol(root)


def test_changed_inherited_frozen_file_is_rejected(registered):
    root, _ = registered
    (root / "implementation/finqa_v19_optimized_replay.py").write_bytes(b"changed")
    with pytest.raises(ValueError, match="frozen source"):
        queue.checked_protocol(root)


def bare(tmp_path):
    ctl = queue.Controller.__new__(queue.Controller)
    ctl.root, ctl.protocol = tmp_path, protocol()
    ctl.wait_used, ctl.paired_gpu, ctl.stop, ctl.active = 0, None, False, None
    ctl.updates = []
    ctl.update = lambda phase, **extra: ctl.updates.append((phase, extra))
    ctl.verify_original_B_paused = lambda: None
    return ctl


def idle(index=3):
    return dict(index=index, uuid=f"GPU-{index}", free_mib=80000, processes=[])


def test_inherited_pairing_never_switches_to_another_idle_card(tmp_path, monkeypatch):
    ctl = bare(tmp_path)
    monkeypatch.setattr(queue, "inventory", lambda: [idle(3), idle(4)])
    row, lock = ctl.acquire_gpu("micro_R0")
    lock.close()
    assert row["index"] == 3
    monkeypatch.setattr(
        queue, "inventory", lambda: [{**idle(3), "processes": [{"pid": 2}]}, idle(4)]
    )
    monkeypatch.setattr(queue.time, "sleep", lambda _: setattr(ctl, "stop", True))
    with pytest.raises(RuntimeError, match="before launch"):
        ctl.acquire_gpu("micro_R3")
    assert ctl.paired_gpu["index"] == 3


def test_worker_command_names_the_new_worker_without_changing_cpu_locality(tmp_path):
    command = queue.worker_command(tmp_path, "micro_R3", idle(), protocol())
    assert command[:3] == ["/usr/bin/taskset", "--cpu-list", "0-3"]
    assert command[5] == str(tmp_path / "implementation/finqa_v33_performance_worker.py")
    assert command[9] == "micro_R3"


def test_cpu_initialization_counts_as_worker_and_retry_is_blocked(tmp_path):
    ctl = bare(tmp_path)
    ctl.active = dict(pid=123, GPU_context_not_yet_initialized=True)
    with pytest.raises(ValueError, match="one worker"):
        ctl.run_stage("micro_R3")
    ctl.active = None
    path = tmp_path / "micro_R3/launch/record.json"
    path.parent.mkdir(parents=True)
    path.write_text("{}")
    with pytest.raises(ValueError, match="retry forbidden"):
        ctl.run_stage("micro_R3")


def test_stage_timeout_preserves_owned_v33_worker_path(tmp_path, monkeypatch):
    ctl = bare(tmp_path)
    lock = (tmp_path / "fake.lock").open("w")
    ctl.acquire_gpu = lambda _: (idle(), lock)
    process = SimpleNamespace(pid=123, returncode=None)
    process.poll = lambda: process.returncode
    process.wait = lambda **kwargs: process.returncode
    clock = [0]
    monkeypatch.setattr(queue.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(queue.time, "sleep", lambda _: clock.__setitem__(0, clock[0] + 7200))
    monkeypatch.setattr(queue.subprocess, "Popen", lambda *args, **kwargs: process)
    monkeypatch.setattr(queue, "birth", lambda _: "owned")
    observed = []

    def stop(launch, sig):
        observed.append((launch["worker"], sig))
        process.returncode = -15
        return True

    monkeypatch.setattr(queue, "signal_owned", stop)
    with pytest.raises(ValueError, match="timed out"):
        ctl.run_stage("micro_R3")
    assert observed == [(str(tmp_path / "implementation" / queue.FILES[1]), signal.SIGTERM)]
    assert ctl.active is None and lock.closed


def test_inherited_run_stops_after_pair_if_speedup_fails(tmp_path, monkeypatch):
    ctl = bare(tmp_path)
    monkeypatch.setattr(queue, "__file__", str(tmp_path / "implementation" / queue.FILES[0]))
    monkeypatch.setattr(
        queue._runtime, "__file__", str(tmp_path / "implementation" / queue._runtime.FILES[0])
    )
    calls = []

    def stage(name):
        calls.append(name)
        return micro(name)

    ctl.run_stage = stage
    assert ctl.run() is False
    assert calls == list(queue.MICRO_STAGES)
    assert queue.checked(tmp_path / "selection/record.json")["selected_variant"] is None
    assert ctl.updates[-1][0] == "STOPPED_NO_MATERIAL_SPEEDUP"
    assert not (tmp_path / "cohort_first").exists()


def test_frozen_v32_module_globals_are_not_modified():
    assert queue._common.MICRO_STAGES == ("micro_R0", "micro_R1", "micro_R2")
    assert queue._common.ROOT == queue.V32_ROOT
    assert queue._runtime.MICRO_STAGES == queue.MICRO_STAGES
    assert queue._common.BACKEND_VERSION != queue.BACKEND_VERSION
