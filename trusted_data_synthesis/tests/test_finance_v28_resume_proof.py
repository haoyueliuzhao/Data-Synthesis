"""CPU fault controls for the uniquely inspected same-run gradient-OOM restore."""

import copy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/finqa_v28_resume_proof.py"
SPEC = importlib.util.spec_from_file_location("v28_resume_proof_tests", SCRIPT)
proof = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(proof)


def publish(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    result = value | {"id": proof.digest(value)}
    path.write_text(json.dumps(result))
    return result


def ref(path):
    return {
        "path": str(path),
        "sha256": proof.reference(path)["sha256"],
        "id": proof.checked(path)["id"],
    }


def rewrite(path, **fields):
    value = proof.checked(path)
    value.pop("id")
    return publish(path, value | fields)


@pytest.fixture
def checkpoints(tmp_path, monkeypatch):
    arm = tmp_path / "v25/training_replication/seed251/arms/c_only"
    shared = tmp_path / "v25/training_replication/seed251/shared/step0298_step"
    branch = arm / "training/step0298_branch"
    state = {
        "seed": 251,
        "arm": "shared",
        "step": 298,
        "outer_done": [],
        "pool_id": "pool",
        "schedule": {"schedule_sha256": "schedule"},
        "parameters": {f"lora{i}": torch.tensor([float(i)]) for i in range(112)},
        "buffers": {},
        "optimizer": {
            "state": {
                i: {
                    "step": torch.tensor(298.0),
                    "exp_avg": torch.tensor([0.0]),
                    "exp_avg_sq": torch.tensor([1.0]),
                }
                for i in range(112)
            }
        },
        "rng": {
            "python": (1, 2, 3),
            "torch": torch.tensor([7], dtype=torch.uint8),
            "cuda": [torch.tensor([8], dtype=torch.uint8)],
        },
        "pi": {"task": [1.0]},
        "prior": {"task": [1.0]},
        "execution_plan": {"steps": 1490},
        "adapter_binding": {"fixture": True},
        "frozen_base_digest": "base",
        "model_training": True,
    }
    for label, directory, arm_name, phase in (
        ("SHARED", shared, "shared", "step"),
        ("BRANCH", branch, "C-only", "branch"),
    ):
        directory.mkdir(parents=True)
        saved = state | {"arm": arm_name}
        torch.save(saved, directory / "state.pt")
        sha, actual = proof.reference(directory / "state.pt")["sha256"], proof.tree_digest(saved)
        monkeypatch.setattr(proof, label + "_SHA", sha)
        monkeypatch.setattr(proof, label + "_DIGEST", actual)
        metadata = {
            "seed": 251,
            "arm": arm_name,
            "step": 298,
            "phase": phase,
            "state_sha256": sha,
            "actual_state_digest": actual,
            "pool_id": "pool",
            "schedule_sha256": "schedule",
            "checkpoint_contains_actual_model_Adam_RNG_pi": True,
        }
        if label == "BRANCH":
            metadata["evidence"] = {
                "shared_actual_state_digest": proof.SHARED_DIGEST,
                "shared_checkpoint": str(shared),
            }
        (directory / "record.json").write_text(json.dumps(metadata))
    return SimpleNamespace(root=tmp_path / "v25", arm=arm, branch=branch, shared=shared)


@pytest.fixture
def setup(checkpoints, monkeypatch):
    c = checkpoints
    root, predecessor = c.root, c.root / "same_run_recovery_01"
    c.predecessor = predecessor
    runtime = root / "frozen"
    source_hashes = {}
    for name in proof.SOURCE_SHA:
        path = runtime / "trusted_data_synthesis/src/trusted_synthesis/finance_research" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# cpu frozen source " + name)
        source_hashes[name] = proof.reference(path)["sha256"]
    monkeypatch.setattr(proof, "SOURCE_SHA", source_hashes)
    worker = root / "implementation" / proof.WORKER
    worker.parent.mkdir()
    worker.write_text("# CPU worker source")
    worker_sha = proof.reference(worker)["sha256"]
    monkeypatch.setattr(proof, "WORKER_SHA", worker_sha)
    manifest = publish(
        root / "implementation/record.json",
        {"scientific_runtime": str(runtime), "sha256": {proof.WORKER: worker_sha}},
    )
    job = {
        "key": proof.JOB_KEY,
        "kind": "arm",
        "branch": "training_replication",
        "script": proof.WORKER,
        "args": ["train", "--seed", "251", "--arm", "c_only"],
    }
    plan = publish(
        root / "protocol/record.json", {"jobs": [job], "implementation_id": manifest["id"]}
    )
    train = publish(
        root / "training_replication/registration/record.json",
        {"source_binding": {"script_sha256": worker_sha, "source_runtime": str(runtime)}},
    )
    execution = publish(predecessor / "protocol/record.json", {"cpu_fixture": True})
    c.attempt = predecessor / "queue/jobs" / proof.JOB_KEY / "attempt001"
    common = {"protocol_id": execution["id"], "scientific_protocol_id": plan["id"]}
    command = [
        "/unused/python",
        "-u",
        str(worker),
        *job["args"],
        "--root",
        str(root / "training_replication"),
        "--gpu-index",
        "7",
    ]
    publish(c.attempt / "intent/record.json", common | {"job": job, "command": command})
    publish(
        c.attempt / "launch/record.json",
        common | {"job": job, "command": command, "pid": 651779, "birth": "373851616", "gpu": 7},
    )
    publish(
        c.attempt / "exit/record.json",
        common | {"key": proof.JOB_KEY, "exit_code": 1, "completed": False, "result": None},
    )
    publish(
        c.arm / "launch_attempts/attempt001/intent/record.json",
        {
            "pid": 651779,
            "protocol_id": train["id"],
            "seed": 251,
            "arm": "C-only",
            "explicit_resume": False,
        },
    )
    identity = {
        "seed": 251,
        "arm": "C-only",
        "step": 298,
        "CPU_control_only": False,
        "pool_id": "pool",
        "schedule_sha256": "schedule",
    }
    outer = c.arm / proof.OUTER
    publish(
        outer / "intent/record.json",
        identity | {"optimizer_steps_in_outer": 0, "automatic_resampling": False},
    )
    publish(outer / "phases/000/record.json", identity | {"phase": "capture_pre_outer_state"})
    publish(outer / "phases/001/record.json", identity | {"phase": "full_class_gradients"})
    error = "CUDA out of memory. CPU fixture only."
    c.failure = outer / "failure/record.json"
    publish(
        c.failure,
        identity
        | {
            "intent": ref(outer / "intent/record.json"),
            "last_phase_record": ref(outer / "phases/001/record.json"),
            "failure_kind": "resource_OOM",
            "error_type": "OutOfMemoryError",
            "error": error,
            "last_phase": "full_class_gradients",
            "feedback_artifacts": {},
            "retained_incomplete_feedback": [],
            "last_completed_replay_response": None,
            "outer_commit_record_exists": False,
            "last_committed_training_step": 298,
            "stopped_before_next_training_step": True,
            "failure_counted_as_Q_zero": False,
            "feedback_resampled": False,
            "automatic_retry": False,
        },
    )
    c.stopped = c.arm / "launch_attempts/attempt001/stopped/record.json"
    publish(
        c.stopped,
        {
            "outer_failure_audit": ref(c.failure),
            "error_type": "OutOfMemoryError",
            "outer_audit_write_error": None,
            "retry_performed": False,
            "partial_feedback_resampled": False,
            "error": error,
        },
    )
    (c.attempt / "worker.log").write_text(
        'Traceback (most recent call last):\n  File "v8.py", line 537, in class_gradients\n'
        "    gradients = torch.autograd.grad(loss, tuple(named.values()))\n"
        + "torch.OutOfMemoryError: "
        + error
        + "\n"
    )
    monkeypatch.setattr(proof, "process_snapshot", lambda pid: None)
    monkeypatch.setattr(proof, "live_session_members", lambda pid: [])
    return c


def test_complete_cpu_proof_stable_and_read_only(setup):
    c = setup
    before = {str(p): proof.reference(p)["sha256"] for p in c.root.rglob("*") if p.is_file()}
    result = proof.prove_same_run_gradient_oom_resume(c.root, c.predecessor)
    assert result == proof.prove_same_run_gradient_oom_resume(c.root, c.predecessor)
    assert result["id"] == proof.digest({k: v for k, v in result.items() if k != "id"})
    assert result["eligible"] and result["arm_file_count"] == 8
    assert result["checkpoint_evidence"]["shared_comparison_differences"] == ["arm"]
    assert result["optimizer_updates_repeated"] == 0 and result["feedback_resampling"] is False
    assert before == {
        str(p): proof.reference(p)["sha256"] for p in c.root.rglob("*") if p.is_file()
    }
    assert not torch.cuda.is_initialized()


@pytest.mark.parametrize(
    "relative",
    [
        "feedback/point/intent/record.json",
        "feedback/point/draw0/calls/provider_intent.json",
        "feedback/point/draw0/episodes/one.json",
        "training/step0298_outer/record.json",
        "training/step0299_step/record.json",
        "launch_attempts/attempt002/intent/record.json",
    ],
)
def test_feedback_or_additional_training_work_rejects_restore(setup, relative):
    path = setup.arm / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not permitted")
    with pytest.raises(ValueError, match="unexpected"):
        proof.prove_same_run_gradient_oom_resume(setup.root, setup.predecessor)


def test_empty_feedback_root_is_not_proof_of_no_generation(setup):
    (setup.arm / "feedback").mkdir()
    with pytest.raises(ValueError, match="unexpected arm directory"):
        proof.prove_same_run_gradient_oom_resume(setup.root, setup.predecessor)


@pytest.mark.parametrize(
    "field,value",
    [
        ("last_phase", "feedback_generation"),
        ("failure_kind", "nonfinite_numeric"),
        ("outer_commit_record_exists", True),
        ("last_completed_replay_response", {"response": 1}),
        ("retained_incomplete_feedback", [{"episode": "uncertain"}]),
        ("feedback_artifacts", {"draw0": {"exists": True}}),
        ("feedback_resampled", True),
    ],
)
def test_failure_class_or_progress_changes_are_refused(setup, field, value):
    rewrite(setup.failure, **{field: value})
    rewrite(setup.stopped, outer_failure_audit=ref(setup.failure))
    with pytest.raises(ValueError, match="audited pre-feedback"):
        proof.prove_same_run_gradient_oom_resume(setup.root, setup.predecessor)


@pytest.mark.parametrize("bad", ["live_worker", "live_orphan", "missing_identity"])
def test_live_or_uncertain_original_process_blocks_restore(setup, monkeypatch, bad):
    if bad == "live_worker":
        monkeypatch.setattr(
            proof, "process_snapshot", lambda pid: {"state": "S", "birth": "373851616"}
        )
    elif bad == "live_orphan":
        monkeypatch.setattr(proof, "live_session_members", lambda pid: [{"pid": 45678}])
    else:
        rewrite(setup.attempt / "launch/record.json", birth=None)
    with pytest.raises(ValueError, match="alive|identity missing"):
        proof.prove_same_run_gradient_oom_resume(setup.root, setup.predecessor)


def test_checkpoint_byte_change_refused_before_deserialization(setup, monkeypatch):
    (setup.branch / "state.pt").write_bytes(b"tampered-state")
    monkeypatch.setattr(
        torch, "load", lambda *a, **k: pytest.fail("must not deserialize changed bytes")
    )
    with pytest.raises(ValueError, match="checkpoint bytes"):
        proof.prove_same_run_gradient_oom_resume(setup.root, setup.predecessor)


@pytest.mark.parametrize("change", [{"pid": 651780}, {"birth": "373851617"}])
def test_different_original_process_identity_is_refused(setup, change):
    rewrite(setup.attempt / "launch/record.json", **change)
    with pytest.raises(ValueError, match="explicitly audited original process identity"):
        proof.prove_same_run_gradient_oom_resume(setup.root, setup.predecessor)


def test_wrong_predecessor_is_refused(setup):
    with pytest.raises(ValueError, match="wrong predecessor root"):
        proof.prove_same_run_gradient_oom_resume(
            setup.root, setup.root / "execution_continuation_01"
        )


@pytest.mark.parametrize("field", ["parameters", "optimizer", "rng", "pi", "outer_done"])
def test_tensor_semantics_even_with_fixture_rebinding_are_refused(checkpoints, monkeypatch, field):
    c = checkpoints
    state = torch.load(c.branch / "state.pt", map_location="cpu", weights_only=False)
    changed = copy.deepcopy(state)
    if field == "parameters":
        changed[field]["lora0"] += 1
    elif field == "optimizer":
        changed[field]["state"][0]["step"] += 1
    elif field == "rng":
        changed[field]["torch"] += 1
    elif field == "pi":
        changed[field]["task"] = [0.5]
    else:
        changed[field] = [298]
    torch.save(changed, c.branch / "state.pt")
    sha, actual = proof.reference(c.branch / "state.pt")["sha256"], proof.tree_digest(changed)
    monkeypatch.setattr(proof, "BRANCH_SHA", sha)
    monkeypatch.setattr(proof, "BRANCH_DIGEST", actual)
    metadata = json.loads((c.branch / "record.json").read_text())
    (c.branch / "record.json").write_text(
        json.dumps(metadata | {"state_sha256": sha, "actual_state_digest": actual})
    )
    with pytest.raises(ValueError, match="state coordinates|beyond the arm label"):
        proof.checkpoint_evidence(c.branch, c.shared)


def test_concurrent_change_during_cpu_preflight_rejected(setup, monkeypatch):
    original = proof.checkpoint_evidence

    def changed(*args):
        value = original(*args)
        (setup.arm / "feedback").mkdir()
        return value

    monkeypatch.setattr(proof, "checkpoint_evidence", changed)
    with pytest.raises(ValueError, match="unexpected arm directory"):
        proof.prove_same_run_gradient_oom_resume(setup.root, setup.predecessor)


@pytest.mark.parametrize("bad", ["source", "wrong_command", "missing_artifact", "symlink"])
def test_source_and_complete_evidence_binding_required(setup, bad):
    if bad == "source":
        (setup.root / "implementation" / proof.WORKER).write_text("changed")
    elif bad == "wrong_command":
        for name in ("intent", "launch"):
            path = setup.attempt / name / "record.json"
            rewrite(path, command=proof.checked(path)["command"] + ["--resume"])
    elif bad == "missing_artifact":
        (setup.arm / proof.OUTER / "phases/000/record.json").unlink()
    else:
        (setup.arm / "other").symlink_to(setup.shared, target_is_directory=True)
    with pytest.raises(ValueError):
        proof.prove_same_run_gradient_oom_resume(setup.root, setup.predecessor)
