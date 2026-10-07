"""CPU-only checkpoint/OOM fault controls; no model, GPU, process or API actions."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/finqa_v28_checkpoint_resume.py"
SPEC = importlib.util.spec_from_file_location("v28_checkpoint_resume_tests", SCRIPT)
p = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(p)


def write_json(path, value, bound=True):
    path.parent.mkdir(parents=True, exist_ok=True)
    value = {key: item for key, item in value.items() if key != "id"}
    if bound:
        value = value | {"id": p.digest(value)}
    path.write_text(json.dumps(value))
    return value


def rewrite(path, **updates):
    return write_json(path, p.checked(path) | updates)


def bound_ref(path):
    return dict(path=str(path), sha256=p.reference(path)["sha256"], id=p.checked(path)["id"])


def save_checkpoint(f, *, step=298, arm="C-only", outer_done=None):
    outer_done = [] if outer_done is None else outer_done
    state = dict(
        seed=251,
        arm=arm,
        step=step,
        outer_done=outer_done,
        pool_id="pool",
        schedule=dict(schedule_sha256="schedule"),
        parameters={f"lora{i}": torch.tensor([float(i)]) for i in range(112)},
        buffers={},
        optimizer=dict(
            state={
                i: dict(
                    step=torch.tensor(float(step)),
                    exp_avg=torch.tensor([0.0]),
                    exp_avg_sq=torch.tensor([1.0]),
                )
                for i in range(112)
            }
        ),
        rng=dict(
            python=(1, 2, 3),
            torch=torch.tensor([7], dtype=torch.uint8),
            cuda=[torch.tensor([8], dtype=torch.uint8)],
        ),
        pi={"task": [1.0]},
        prior={"task": [1.0]},
        execution_plan={"steps": 1490},
        adapter_binding={"fixture": True},
        frozen_base_digest="base",
        model_training=True,
    )
    phase = "branch" if step == 298 else "step"
    directory = f.arm / f"training/step{step:04d}_{phase}"
    directory.mkdir(parents=True, exist_ok=True)
    torch.save(state, directory / "state.pt")
    metadata = dict(
        seed=251,
        arm=arm,
        step=step,
        phase=phase,
        state_sha256=p.reference(directory / "state.pt")["sha256"],
        actual_state_digest=p.h.tree_digest(state),
        pool_id="pool",
        schedule_sha256="schedule",
        checkpoint_contains_actual_model_Adam_RNG_pi=True,
    )
    write_json(directory / "record.json", metadata, bound=False)
    f.checkpoint, f.state = directory, state
    return directory


@pytest.fixture
def failure(tmp_path, monkeypatch):
    root, arm_name, key = tmp_path / "v25", "C-only", "replication-train-seed251-c_only"
    queue = root / "resource_recovery_02"
    arm = root / "training_replication/seed251/arms/c_only"
    attempt = queue / "queue/jobs" / key / "attempt001"
    worker = root / "implementation/finqa_v25_training_replication.py"
    job = dict(
        key=key,
        kind="arm",
        branch="training_replication",
        script=worker.name,
        args=["train", "--seed", "251", "--arm", "c_only"],
        result=str(arm / "result/record.json"),
    )
    plan, training = dict(id="science", jobs=[job]), dict(id="training")
    execution = write_json(
        queue / "protocol/record.json", dict(scientific_protocol={"id": "science"}, jobs=[job])
    )
    command = [
        "/cpu-fixture/python",
        "-u",
        str(worker),
        *job["args"],
        "--root",
        str(root / "training_replication"),
        "--gpu-index",
        "7",
    ]
    launch = dict(
        protocol_id=execution["id"],
        scientific_protocol_id=plan["id"],
        job=job,
        command=command,
        pid=12345,
        birth="99999",
        gpu=7,
    )
    for kind in ("launch", "intent"):
        write_json(attempt / f"{kind}/record.json", launch)
    write_json(
        attempt / "exit/record.json",
        dict(
            protocol_id=execution["id"],
            scientific_protocol_id="science",
            key=key,
            exit_code=1,
            completed=False,
            result=None,
        ),
    )
    scientific = arm / "launch_attempts/attempt001"
    write_json(
        scientific / "intent/record.json",
        dict(pid=12345, protocol_id="training", seed=251, arm=arm_name, explicit_resume=False),
    )
    error = "CUDA out of memory. Tried to allocate fixture bytes."
    write_json(
        scientific / "stopped/record.json",
        dict(
            error_type="OutOfMemoryError",
            error=error,
            outer_audit_write_error=None,
            retry_performed=False,
            partial_feedback_resampled=False,
        ),
    )
    log = (
        "Traceback (most recent call last):\n in run_until\n in _outer_update\n"
        " in class_gradients\n torch.autograd.grad\n"
    )
    (attempt / "worker.log").write_text(log + "torch.OutOfMemoryError: " + error + "\n")

    def latest(path):
        candidates = sorted(path.glob("step*_*"))
        return candidates[-1] if candidates else None

    def no_partial(path):
        for intent in path.glob("feedback/*/intent/record.json"):
            assert all(
                (intent.parents[1] / f"draw{i}/generation_seal/seal.json").is_file() for i in (0, 1)
            )

    rt = SimpleNamespace(
        launcher=SimpleNamespace(latest_checkpoint=latest),
        arms=SimpleNamespace(no_partial_arm_feedback=no_partial),
    )
    context = dict(
        plan=plan,
        training=training,
        job=job,
        seed=251,
        arm=arm_name,
        arm_root=arm,
        worker=worker,
        runtime=rt,
        sources={},
    )
    monkeypatch.setattr(p, "source_context", lambda *_: context)
    monkeypatch.setattr(p.h, "process_snapshot", lambda pid: None)
    monkeypatch.setattr(p.h, "live_session_members", lambda pid: [])
    f = SimpleNamespace(
        root=root,
        queue=queue,
        arm=arm,
        attempt=attempt,
        context=context,
        scientific=scientific,
        key=key,
        launch=launch,
        error=error,
        rt=rt,
    )
    save_checkpoint(f)
    shared = arm.parents[1] / "shared/step0298_step"
    shared.mkdir(parents=True)
    shared_state = f.state | {"arm": "shared"}
    torch.save(shared_state, shared / "state.pt")
    shared_metadata = json.loads((f.checkpoint / "record.json").read_text()) | dict(
        arm="shared",
        phase="step",
        state_sha256=p.reference(shared / "state.pt")["sha256"],
        actual_state_digest=p.h.tree_digest(shared_state),
    )
    write_json(shared / "record.json", shared_metadata, bound=False)
    audit_path = arm / "training/outer_attempts/step0298/attempt001/failure/record.json"
    write_json(
        audit_path,
        dict(
            step=298,
            last_phase="full_class_gradients",
            error_type="OutOfMemoryError",
            failure_kind="resource_OOM",
            feedback_artifacts={},
            retained_incomplete_feedback=[],
            outer_commit_record_exists=False,
        ),
    )
    rewrite(scientific / "stopped/record.json", outer_failure_audit=bound_ref(audit_path))
    return f


def prove(f):
    return p.prove_checkpoint_oom_resume(f.root, f.queue, f.key, f.attempt)


def test_first_outer_oom_proof_is_cpu_only_deterministic_and_read_only(failure):
    before = {
        str(path): path.stat().st_mtime_ns for path in failure.root.rglob("*") if path.is_file()
    }
    result = prove(failure)
    assert result["eligible"] and result["resume_checkpoint"] == str(failure.checkpoint)
    assert (
        result["feedback_resampling"] is False and result["checkpoint_evidence"]["outer_done"] == []
    )
    assert result == prove(failure) and not torch.cuda.is_initialized()
    assert before == {
        str(path): path.stat().st_mtime_ns for path in failure.root.rglob("*") if path.is_file()
    }


def test_static_training_oom_restores_arbitrary_committed_step(failure):
    failure.context["arm"] = "Static"
    rewrite(failure.scientific / "intent/record.json", arm="Static")
    save_checkpoint(failure, step=467, arm="Static")
    (failure.attempt / "worker.log").write_text(
        "Traceback (most recent call last):\n in run_until\n in step\n"
        + "torch.OutOfMemoryError: "
        + failure.error
    )
    result = prove(failure)
    assert result["checkpoint_evidence"]["step"] == 467


def add_history(f):
    save_checkpoint(f, step=596, outer_done=[298])
    rewrite(f.scientific / "stopped/record.json", outer_failure_audit=None)
    point = f.arm / "feedback/earlier-point-directory"
    write_json(
        point / "intent/record.json", dict(point_id="earlier-point", denominator=700), bound=False
    )
    for draw in (0, 1):
        episode = point / f"draw{draw}/episodes/fixture.json"
        write_json(episode, dict(fixture=True), bound=False)
        write_json(
            point / f"draw{draw}/generation_seal/seal.json",
            dict(
                complete=True,
                all_provider_calls_settled=True,
                registered_denominator=350,
                episodes=[
                    dict(
                        key=index,
                        path="episodes/fixture.json",
                        sha256=p.reference(episode)["sha256"],
                    )
                    for index in range(350)
                ],
            ),
        )
    body = dict(
        identity=dict(point_id="earlier-point"),
        denominator=700,
        episode_sha256=["fixture"] * 700,
        source_manifest_sha256="source",
        registered_episode_keys=list(range(700)),
        generation_complete=True,
    )
    seal_sha = p.digest(body)
    rewards = [0] * 700
    write_json(
        point / "cohort_seal/record.json",
        body | dict(seal_sha256=seal_sha, episodes=[]),
        bound=False,
    )
    write_json(
        point / "native_rewards/record.json",
        dict(cohort_seal_sha256=seal_sha, rewards=rewards, scores=[]),
        bound=False,
    )
    write_json(
        f.arm / "training/step0298_outer/record.json",
        dict(
            step=298,
            phase="outer",
            evidence=dict(
                feedback_seal_sha256=seal_sha,
                feedback_report=dict(
                    denominator=700,
                    all_receipts_validated=True,
                    point_id="earlier-point",
                    cohort_seal_sha256=seal_sha,
                    reward_sha256=p.digest(rewards),
                ),
            ),
        ),
        bound=False,
    )
    return point


def test_later_gradient_oom_preserves_completed_earlier_feedback(failure):
    add_history(failure)
    result = prove(failure)
    assert result["checkpoint_evidence"]["outer_done"] == [298]
    assert result["historical_feedback"]["sealed_feedback_points"] == ["earlier-point"]
    assert result["historical_feedback"]["no_current_outer_feedback"] is True


@pytest.mark.parametrize(
    "case",
    [
        "worker_alive",
        "session_alive",
        "unknown_exception",
        "generation",
        "replay",
        "wrong_exit",
        "partial_checkpoint",
        "cuda_rng",
        "Adam",
        "new_feedback",
        "wrong_outer",
        "completed",
        "new_launch",
        "traceback_twice",
    ],
)
def test_unsafe_or_unknown_failure_refuses_resume(failure, monkeypatch, case):
    if case == "worker_alive":
        monkeypatch.setattr(p.h, "process_snapshot", lambda _: dict(birth="99999", state="R"))
    elif case == "session_alive":
        monkeypatch.setattr(p.h, "live_session_members", lambda _: [dict(pid=111)])
    elif case == "unknown_exception":
        rewrite(failure.scientific / "stopped/record.json", error_type="RuntimeError")
    elif case in {"generation", "replay"}:
        (failure.attempt / "worker.log").write_text(
            "Traceback (most recent call last):\n in "
            + case
            + "\ntorch.OutOfMemoryError: "
            + failure.error
        )
    elif case == "wrong_exit":
        rewrite(failure.attempt / "exit/record.json", exit_code=None)
    elif case == "partial_checkpoint":
        (failure.arm / "training/step0299_step").mkdir()
    elif case in {"cuda_rng", "Adam"}:
        state = failure.state
        if case == "cuda_rng":
            state["rng"]["cuda"] = None
        else:
            state["optimizer"]["state"][0]["step"] = torch.tensor(299.0)
        torch.save(state, failure.checkpoint / "state.pt")
        metadata = json.loads((failure.checkpoint / "record.json").read_text())
        metadata.update(
            state_sha256=p.reference(failure.checkpoint / "state.pt")["sha256"],
            actual_state_digest=p.h.tree_digest(state),
        )
        write_json(failure.checkpoint / "record.json", metadata, bound=False)
    elif case == "new_feedback":
        (failure.arm / "feedback/uncommitted-new-point").mkdir(parents=True)
    elif case == "wrong_outer":
        save_checkpoint(failure, step=430)
    elif case == "completed":
        write_json(Path(failure.context["job"]["result"]), dict(complete=True))
    elif case == "new_launch":
        write_json(failure.arm / "launch_attempts/attempt002/intent/record.json", dict(pid=333))
    else:
        with (failure.attempt / "worker.log").open("a") as stream:
            stream.write("Traceback (most recent call last):\n")
    with pytest.raises((ValueError, FileNotFoundError, KeyError)):
        prove(failure)


def test_partial_historical_feedback_refuses_resume(failure):
    point = add_history(failure)
    rewrite(point / "draw1/generation_seal/seal.json", complete=False)
    with pytest.raises(ValueError, match="partial historical"):
        prove(failure)


def test_adopted_worker_uses_bound_original_log_without_wait_status(failure):
    original = failure.root / "execution_continuation_01/queue/jobs" / failure.key / "attempt001"
    write_json(original / "launch/record.json", failure.launch)
    (original / "worker.log").write_text((failure.attempt / "worker.log").read_text())
    origin = bound_ref(original / "launch/record.json")
    for kind in ("launch", "intent"):
        rewrite(
            failure.attempt / f"{kind}/record.json",
            adopted_existing_process=True,
            origin_launch=origin,
        )
    rewrite(failure.attempt / "exit/record.json", exit_code=None)
    (failure.attempt / "worker.log").write_text("shadow log is not the scientific traceback")
    result = prove(failure)
    assert result["references"]["worker_log"]["path"] == str(original / "worker.log")
    assert len(result["adopted_launch_chain"]) == 1


def test_adopted_log_identity_mismatch_refuses_resume(failure):
    original = failure.root / "execution_continuation_01/queue/jobs" / failure.key / "attempt001"
    write_json(original / "launch/record.json", failure.launch | {"pid": 999})
    origin = bound_ref(original / "launch/record.json")
    rewrite(
        failure.attempt / "launch/record.json", adopted_existing_process=True, origin_launch=origin
    )
    with pytest.raises(ValueError, match="identity changed"):
        prove(failure)


def wrap_command(f):
    wrapper = f.queue / "implementation/finqa_v28_memory_worker.py"
    wrapper.parent.mkdir()
    wrapper.write_text("# frozen CPU fixture wrapper\n")
    manifest = write_json(
        wrapper.parent / "record.json", dict(sha256={wrapper.name: p.reference(wrapper)["sha256"]})
    )
    execution = rewrite(f.queue / "protocol/record.json", implementation_id=manifest["id"])
    original = f.launch["command"][2:]
    command = [
        "/usr/bin/taskset",
        "--cpu-list",
        "0-3",
        "/cpu-fixture/python",
        "-u",
        str(wrapper),
        "--worker",
        original[0],
        "--receipt-dir",
        str(f.attempt / "memory_reservation"),
        "--memory-mode",
        "shared_checkpointed",
        "--",
        *original[1:],
    ]
    for kind in ("launch", "intent"):
        rewrite(
            f.attempt / f"{kind}/record.json",
            protocol_id=execution["id"],
            command=command,
            memory_mode="shared_checkpointed",
        )
    rewrite(f.attempt / "exit/record.json", protocol_id=execution["id"])
    write_json(
        f.attempt / "memory_reservation/wrapper_intent.json",
        dict(
            pid=12345,
            memory_mode="shared_checkpointed",
            original_command=original,
            scientific_arguments_changed=False,
            source_binding=dict(
                scientific_protocol_id="science", sources={p.h.WORKER: {"sha256": p.h.WORKER_SHA}}
            ),
        ),
    )
    return wrapper


def test_exact_frozen_memory_wrapper_command_is_supported(failure):
    wrapper = wrap_command(failure)
    result = prove(failure)
    assert result["wrapper_evidence"]["source"]["path"] == str(wrapper)


def test_changed_wrapper_bytes_refuse_auto_resume(failure):
    wrapper = wrap_command(failure)
    wrapper.write_text("changed wrapper")
    with pytest.raises(ValueError, match="wrapper binding"):
        prove(failure)


@pytest.mark.parametrize("case", ["episode", "cohort", "reward", "shared"])
def test_historical_hash_and_original_shared_binding_are_required(failure, case):
    point = add_history(failure)
    if case == "episode":
        (point / "draw0/episodes/fixture.json").write_text("changed")
    elif case == "cohort":
        path = point / "cohort_seal/record.json"
        value = json.loads(path.read_text()) | {"denominator": 701}
        write_json(path, value, bound=False)
    elif case == "reward":
        path = point / "native_rewards/record.json"
        value = json.loads(path.read_text()) | {"rewards": [1] * 700}
        write_json(path, value, bound=False)
    else:
        path = failure.arm.parents[1] / "shared/step0298_step/record.json"
        value = json.loads(path.read_text()) | {"pool_id": "different"}
        write_json(path, value, bound=False)
    with pytest.raises(ValueError):
        prove(failure)


def test_first_outer_missing_phase_audit_refuses_resume(failure):
    rewrite(failure.scientific / "stopped/record.json", outer_failure_audit=None)
    with pytest.raises(ValueError, match="first outer"):
        prove(failure)


def test_metadata_reader_omits_indented_answer_payload(tmp_path):
    path = tmp_path / "cohort.json"
    path.write_text(
        json.dumps(
            dict(denominator=1, episodes=[dict(answer="unread")], seal_sha256="sha"), indent=2
        )
    )
    metadata, _ = p.metadata_without_payload(path, {"episodes"})
    assert metadata == dict(denominator=1, seal_sha256="sha")
