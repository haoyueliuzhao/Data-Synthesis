"""CPU-only queue/selection/source-identity tests; no model, API or GPU worker."""

import importlib
import json
import signal
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
queue = importlib.import_module("finqa_v32_performance_controller")


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
    return dict(
        protocol_id="protocol",
        stage=stage,
        status="COMPLETE",
        numeric_pass=True,
        unprofiled_seconds=seconds,
        API_calls=0,
        new_sampling_calls=0,
        scoring_calls=0,
        optimizer_steps=0,
        case_results=[
            dict(
                case_id="short_short",
                response_index=2,
                bitwise_logp_equal=True,
                bitwise_gradient_equal=True,
                shape_dtype_keys_equal=True,
                state_unchanged=True,
                logp_digest="same-logp",
                baseline_logp_digest="same-logp",
                gradient_digest="same-grad",
                baseline_gradient_digest="same-grad",
                seconds=seconds,
                peak_allocated_bytes=1024,
                peak_reserved_bytes=2048,
            )
        ],
    )


def results(r0=12, r1=8, r2=7.8):
    return {
        stage: micro(stage, value)
        for stage, value in zip(queue.MICRO_STAGES, (r0, r1, r2), strict=True)
    }


@pytest.mark.parametrize(
    "times,expected",
    [
        ((12, 8, 7.8), "R1"),
        ((12, 8, 7.5), "R2"),
        ((12, 11, 8), "R2"),
        ((12, 8, 11), "R1"),
        ((12, 11, 11), None),
        ((12, 10, 10), "R1"),
    ],
)
def test_preregistered_material_speedup_and_prefer_r1(times, expected):
    selection = queue.choose_variant(protocol(), results(*times))
    assert selection["selected_variant"] == expected
    assert selection["selection_is_not_formal_B_resume_authority"] is True


@pytest.mark.parametrize(
    "change",
    [
        "OOM",
        "numeric",
        "case",
        "digest",
        "order",
        "score",
        "nan",
        "memory",
        "profile_in_total",
    ],
)
def test_r2_failure_or_case_contradiction_never_falls_back_to_good_r1(change):
    values = results()
    bad = values["micro_R2"]
    if change == "OOM":
        bad["status"] = "OOM"
    elif change == "numeric":
        bad["numeric_pass"] = False
    elif change == "case":
        bad["case_results"][0]["bitwise_gradient_equal"] = False
    elif change == "digest":
        bad["case_results"][0]["gradient_digest"] = "changed"
    elif change == "order":
        bad["case_results"][0]["response_index"] = 99
    elif change == "score":
        bad["scoring_calls"] = 1
    elif change == "nan":
        bad["unprofiled_seconds"] = float("nan")
    elif change == "memory":
        bad["case_results"][0]["peak_allocated_bytes"] = 76 * 1024**3 + 1
    elif change == "profile_in_total":
        bad["unprofiled_seconds"] += 1
    with pytest.raises(ValueError):
        queue.choose_variant(protocol(), values)


def cohort_result(stage="cohort_first"):
    expected = protocol()["replay_binding_expected"]
    binding = dict(
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
            variant="R1",
            version=queue.BACKEND_VERSION,
            adapter_source=expected["adapter_source"],
            inherited_V19_source=expected["inherited_V19_source"],
        ),
    )
    checkpoint = dict(
        schema="v19_response_boundary_checkpoint.v1",
        cursor=16,
        binding=binding,
        response_prefix_complete=True,
        full_replay_complete=False,
        optimizer_steps_performed=0,
        no_feedback_generation=True,
        state_sha256="fake-tensor-sha",
    )
    checkpoint["id"] = queue.digest(checkpoint)
    final = stage == "cohort_resume"
    report = dict(
        response_checkpoint_binding=binding,
        restored_completed_responses=16 if final else 0,
        completed_responses=573 if final else 16,
        accounting=dict(responses_replayed=573 if final else 16),
        complete_replay=final,
        pause_reason="registered_boundary",
        new_sampling_calls=0,
        optimizer_steps_performed=0,
    )
    return dict(
        protocol_id="protocol",
        stage=stage,
        status="COMPLETE" if final else "PAUSED_AT_REGISTERED_BOUNDARY",
        numeric_pass=True,
        pause_cursor=16,
        full_cohort_validation_complete=final,
        checkpoint=checkpoint,
        replay_report=report,
        selected_variant="R1",
        comparison={key: True for key in queue.COHORT_COMPARISON_KEYS},
        class_gradient_passes=1,
        original_reference_full700_reruns=0,
        pause_resume_verified=final,
        model_optimizer_rng_buffers_unchanged=True,
        API_calls=0,
        new_sampling_calls=0,
        scoring_calls=0,
        optimizer_steps=0,
    )


def test_cohort_first_is_only_a_prefix_and_resume_requires_full_validation():
    first = cohort_result()
    queue.check_result(protocol(), "cohort_first", first)
    first["pause_cursor"] = 17
    with pytest.raises(ValueError, match="response16"):
        queue.check_result(protocol(), "cohort_first", first)
    final = {**cohort_result("cohort_resume"), "full_cohort_validation_complete": False}
    with pytest.raises(ValueError, match="complete saved-cohort"):
        queue.check_result(protocol(), "cohort_resume", final)
    final["full_cohort_validation_complete"] = True
    queue.check_result(protocol(), "cohort_resume", final)


@pytest.mark.parametrize("field", queue.COHORT_COMPARISON_KEYS)
def test_final_summary_cannot_override_any_failed_independent_comparison(field):
    final = cohort_result("cohort_resume")
    final["comparison"][field] = False
    with pytest.raises(ValueError, match="contradicts summary"):
        queue.check_result(protocol(), "cohort_resume", final)


@pytest.mark.parametrize(
    "field,value",
    [
        ("class_gradient_passes", 2),
        ("original_reference_full700_reruns", 1),
        ("pause_resume_verified", False),
        ("restored_completed_responses", 0),
    ],
)
def test_no_extra_full_pass_or_claimed_cold_resume_without_actual_cursor(field, value):
    final = cohort_result("cohort_resume")
    if field == "restored_completed_responses":
        final["replay_report"][field] = value
    else:
        final[field] = value
    with pytest.raises(ValueError, match="contradicts summary"):
        queue.check_result(protocol(), "cohort_resume", final)


@pytest.mark.parametrize(
    "field", ["point_id", "reward_sha256", "response_order_sha256", "rng_restore_source"]
)
def test_rebound_checkpoint_still_cannot_change_registered_point_reward_order_or_rng(field):
    first = cohort_result()
    first["checkpoint"]["binding"][field] = "changed"
    first["checkpoint"]["id"] = queue.digest(
        {k: v for k, v in first["checkpoint"].items() if k != "id"}
    )
    with pytest.raises(ValueError, match="differs from protocol"):
        queue.check_result(protocol(), "cohort_first", first)


def test_durable_checkpoint_tensor_corruption_is_detected_without_gpu(tmp_path):
    plan, first = protocol(), cohort_result()
    plan["output_root"] = str(tmp_path)
    directory = tmp_path / "cohort_replay/checkpoints/response000016"
    directory.mkdir(parents=True)
    (directory / "state.pt").write_bytes(b"saved-prefix")
    body = {k: v for k, v in first["checkpoint"].items() if k != "id"}
    body["state_sha256"] = queue.sha(directory / "state.pt")
    first["checkpoint"] = queue.publish(directory / "record.json", body)
    queue.publish(
        tmp_path / "selection/record.json", dict(protocol_id="protocol", selected_variant="R1")
    )
    queue.verify_durable_prefix(plan, first)
    (directory / "state.pt").write_bytes(b"changed-prefix")
    with pytest.raises(ValueError, match="missing or changed"):
        queue.verify_durable_prefix(plan, first)


@pytest.mark.parametrize("change", ["excluded", "occupied", "insufficient", "uuid"])
def test_only_empty_bound_white_list_gpu_with_72gib_is_eligible(change):
    row = dict(index=3, uuid="GPU-3", free_mib=73728, processes=[])
    assert queue.eligible(row, protocol())
    if change == "excluded":
        row.update(index=0, uuid="GPU-0")
    elif change == "occupied":
        row["processes"] = [dict(pid=1)]
    elif change == "insufficient":
        row["free_mib"] -= 1
    else:
        row["uuid"] = "changed"
    assert not queue.eligible(row, protocol())


def receipt(call, prompt, output):
    body = dict(call_id=call, prompt_input_ids=[1] * prompt, raw_generated_token_ids=[2] * output)
    return SimpleNamespace(**body, model_dump=lambda **kwargs: body)


def test_median_case_selection_original_order_empty_cells_not_filled():
    turns = [
        SimpleNamespace(receipt=receipt(str(i), p, t))
        for i, (p, t) in enumerate([(3, 1), (2, 2), (8, 8), (10, 10)])
    ]
    cohort = SimpleNamespace(episodes=[SimpleNamespace(turns=turns)])
    cases, medians, counts, total = queue.select_cases(cohort, [1])
    assert total == 4 and medians == dict(prompt_tokens=5.5, output_tokens=5.0)
    assert [(case["case_id"], case["response_index"]) for case in cases] == [
        ("short_short", 0),
        ("long_long", 2),
    ]
    assert counts == dict(short_short=2, long_long=2)


def test_case_selection_uses_actual_positive_work_but_keeps_episode_indices():
    cohort = SimpleNamespace(
        episodes=[
            SimpleNamespace(turns=[SimpleNamespace(receipt=receipt("skip", 100, 100))]),
            SimpleNamespace(turns=[SimpleNamespace(receipt=receipt("first", 3, 2))]),
        ]
    )
    cases, _, _, total = queue.select_cases(cohort, [0, 1])
    assert total == 1 and cases[0]["episode_index"] == 1 and cases[0]["call_id"] == "first"


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


def test_gpu_race_after_lock_is_rechecked_and_does_not_launch(tmp_path, monkeypatch):
    ctl = bare(tmp_path)
    observations = iter([[idle()], [{**idle(), "processes": [{"pid": 999}]}]])
    monkeypatch.setattr(queue, "inventory", lambda: next(observations))
    monkeypatch.setattr(queue.time, "sleep", lambda _: setattr(ctl, "stop", True))
    with pytest.raises(RuntimeError, match="before launch"):
        ctl.acquire_gpu("micro_R0")
    assert ctl.paired_gpu is None


def test_first_chosen_gpu_is_retained_for_later_pairing_without_reservation(tmp_path, monkeypatch):
    ctl = bare(tmp_path)
    monkeypatch.setattr(queue, "inventory", lambda: [idle(3), idle(4)])
    row, lock = ctl.acquire_gpu("micro_R0")
    assert row["index"] == 3
    lock.close()
    monkeypatch.setattr(
        queue, "inventory", lambda: [{**idle(3), "processes": [{"pid": 2}]}, idle(4)]
    )
    monkeypatch.setattr(queue.time, "sleep", lambda _: setattr(ctl, "stop", True))
    with pytest.raises(RuntimeError, match="before launch"):
        ctl.acquire_gpu("micro_R1")
    assert ctl.paired_gpu["index"] == 3


def test_resource_wait_is_bounded_even_when_all_cards_remain_busy(tmp_path, monkeypatch):
    ctl = bare(tmp_path)
    ctl.wait_used = queue.WAIT_BUDGET_SECONDS
    monkeypatch.setattr(queue, "inventory", lambda: pytest.fail("no observation after deadline"))
    with pytest.raises(ValueError, match="24-hour"):
        ctl.acquire_gpu("micro_R0")


def test_pid_reuse_is_never_signaled(monkeypatch):
    monkeypatch.setattr(queue, "birth", lambda _: "different")
    monkeypatch.setattr(queue.os, "kill", lambda *_: pytest.fail("foreign process signaled"))
    assert not queue.signal_owned(dict(pid=999, birth="registered"), signal.SIGTERM)


def test_matching_birth_but_wrong_command_is_never_signaled(monkeypatch):
    monkeypatch.setattr(queue, "birth", lambda _: "same")
    monkeypatch.setattr(Path, "read_bytes", lambda _: b"python\0other.py\0")
    monkeypatch.setattr(queue.os, "kill", lambda *_: pytest.fail("foreign process signaled"))
    with pytest.raises(ValueError, match="command"):
        queue.signal_owned(
            dict(pid=999, birth="same", worker="ours.py", stage="micro_R0"), signal.SIGTERM
        )


def test_freeze_reads_new_code_from_full_commit_and_retains_baseline(tmp_path, monkeypatch):
    repo, frozen, root = tmp_path / "repo", tmp_path / "frozen", tmp_path / "trial"
    current = repo / "trusted_data_synthesis/scripts"
    old = frozen / "trusted_data_synthesis/scripts"
    current.mkdir(parents=True)
    old.mkdir(parents=True)
    for name in queue.FILES + queue.BASE_SCRIPTS:
        (current / name).write_bytes(name.encode())
    for name in queue.BASE_SCRIPTS:
        (old / name).write_bytes(name.encode())
    monkeypatch.setattr(queue, "REPO", repo)
    monkeypatch.setattr(queue, "FROZEN", frozen)
    monkeypatch.setattr(queue, "entry", lambda _: dict(id="parent", path="parent", sha256="parent"))
    calls = []

    def git(command, **kwargs):
        calls.append(command)
        if command[1] == "rev-parse":
            return "a" * 40 + "\n"
        return command[2].rsplit("/", 1)[1].encode()

    monkeypatch.setattr(queue.subprocess, "check_output", git)
    commit, manifest = queue._freeze(root, "HEAD")
    assert commit == "a" * 40
    assert len([c for c in calls if c[1] == "show"]) == len(queue.FILES)
    assert all(c[2].startswith("a" * 40 + ":") for c in calls if c[1] == "show")
    assert set(manifest["sha256"]) == set(queue.FILES + queue.BASE_SCRIPTS)
    (current / queue.FILES[0]).write_bytes(b"uncommitted")
    with pytest.raises(ValueError, match="uncommitted"):
        queue._freeze(tmp_path / "second", "HEAD")
    assert not (tmp_path / "second").exists()


def test_one_worker_slot_includes_cpu_initialization(tmp_path):
    ctl = bare(tmp_path)
    ctl.active = dict(pid=123, stage="micro_R0", GPU_context_not_yet_initialized=True)
    with pytest.raises(ValueError, match="one worker"):
        ctl.run_stage("micro_R1")


def test_already_launched_stage_cannot_implicitly_retry(tmp_path):
    ctl = bare(tmp_path)
    path = tmp_path / "micro_R0/launch/record.json"
    path.parent.mkdir(parents=True)
    path.write_text("{}")
    with pytest.raises(ValueError, match="retry forbidden"):
        ctl.run_stage("micro_R0")


def test_stage_timeout_requests_safe_stop_then_stops_trial(tmp_path, monkeypatch):
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
    signals = []

    def stop(launch, sig):
        signals.append((launch["pid"], sig))
        process.returncode = -15
        return True

    monkeypatch.setattr(queue, "signal_owned", stop)
    with pytest.raises(ValueError, match="timed out"):
        ctl.run_stage("micro_R0")
    assert signals == [(123, signal.SIGTERM)]
    assert queue.checked(tmp_path / "micro_R0/exit/record.json")["timed_out"] is True
    assert ctl.active is None and lock.closed


def test_failure_in_r2_stops_before_selection_or_cohort(tmp_path, monkeypatch):
    ctl = bare(tmp_path)
    monkeypatch.setattr(queue, "__file__", str(tmp_path / "implementation" / queue.FILES[0]))
    calls = []

    def stage(name):
        calls.append(name)
        if name == "micro_R2":
            raise RuntimeError("genuine OOM")
        return micro(name)

    ctl.run_stage = stage
    with pytest.raises(RuntimeError, match="genuine OOM"):
        ctl.run()
    assert calls == list(queue.MICRO_STAGES)
    assert not (tmp_path / "selection/record.json").exists()
    assert queue.checked(tmp_path / "failure/record.json")["no_implicit_fallback"] is True


def test_successful_prefix_requires_new_process_stage_and_never_dispatches_b(tmp_path, monkeypatch):
    ctl = bare(tmp_path)
    monkeypatch.setattr(queue, "__file__", str(tmp_path / "implementation" / queue.FILES[0]))
    calls, values = [], results()

    def stage(name):
        calls.append(name)
        if name in values:
            return values[name]
        if name == "cohort_first":
            return cohort_result()
        final = {
            **cohort_result(name),
            "status": "COMPLETE",
            "full_cohort_validation_complete": True,
        }
        queue.publish(tmp_path / "cohort_resume/result/record.json", final)
        return final

    ctl.run_stage = stage
    assert ctl.run()
    assert calls == list(queue.STAGES)
    outcome = queue.checked(tmp_path / "result/record.json")
    assert outcome["original_B_resume_authorized"] is False
    assert outcome["selected_variant"] == "R1"


def test_source_controller_import_is_standard_library_only():
    source = Path(queue.__file__).read_text()
    assert "import torch" not in source
    assert "import finqa_v32_same_point_guard" not in source
    assert "import finqa_v19" not in source


def test_original_cpu_environment_locality_and_live_pause_gate(tmp_path, monkeypatch):
    monkeypatch.setenv("OMP_NUM_THREADS", "99")
    monkeypatch.setenv("MKL_NUM_THREADS", "99")
    monkeypatch.setenv("TOKENIZERS_PARALLELISM", "true")
    env = queue.worker_environment(idle())
    assert (env["OMP_NUM_THREADS"], env["MKL_NUM_THREADS"], env["TOKENIZERS_PARALLELISM"]) == (
        "4",
        "4",
        "false",
    )
    assert queue.worker_command(tmp_path, "micro_R0", idle(), protocol())[:3] == [
        "/usr/bin/taskset",
        "--cpu-list",
        "0-3",
    ]
    monkeypatch.setattr(queue, "V25_SOURCE_ROOT", tmp_path)
    path = tmp_path / "four_gpu_release_01/queue/status.json"
    path.parent.mkdir(parents=True)
    value = dict(
        protocol_id="old-B",
        phase="PAUSED_BY_USER_CHECKPOINT_SAVED",
        active_children=[],
        automatic_resume_authorized=False,
    )
    path.write_text(json.dumps(value))
    plan = dict(original_B_queue_status=dict(path=str(path), protocol_id="old-B"))
    assert queue.verify_original_B_paused(plan)["active_children"] == []
    value["active_children"] = [dict(pid=7)]
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="no longer cold-paused"):
        queue.verify_original_B_paused(plan)
