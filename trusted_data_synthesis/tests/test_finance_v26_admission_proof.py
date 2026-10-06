"""CPU-only negative controls for absence-of-computation admission evidence."""

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/finqa_v26_admission_proof.py"
SPEC = importlib.util.spec_from_file_location("v26_admission_proof_tests", SCRIPT)
proof = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(proof)


def publish(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    result = value | {"id": proof.digest(value)}
    path.write_text(json.dumps(result))
    return result


def rewrite(path, **fields):
    value = json.loads(path.read_text())
    value.pop("id")
    return publish(path, value | fields)


@pytest.fixture
def make_case(tmp_path, monkeypatch):
    monkeypatch.setattr(proof, "process_snapshot", lambda pid: None)
    monkeypatch.setattr(proof, "process_group_members", lambda pid: [])

    def make(kind="test", *, branch=None, continuation=False, second_gate=False):
        root = tmp_path / (kind + (branch or "default") + str(continuation) + str(second_gate))
        branch = branch or ("c_only_test_extension" if kind == "test" else "training_replication")
        seed = "47" if branch == "c_only_test_extension" else "251"
        script, function, lines = proof.WORKERS[kind]
        worker = root / "implementation" / script
        worker.parent.mkdir(parents=True)
        worker.write_bytes((SCRIPT.parent / script).read_bytes())
        manifest = publish(
            root / "implementation/record.json",
            {"sha256": {script: hashlib.sha256(worker.read_bytes()).hexdigest()}},
        )
        args = [{"test": "generate", "prefix": "prefix", "arm": "train"}[kind], "--seed", seed]
        if kind != "prefix":
            args += ["--arm", "c_only"]
        job = {
            "key": "cpu-fixture-job",
            "kind": kind,
            "branch": branch,
            "script": script,
            "args": args,
        }
        target = proof._target(root, job)
        job["result"] = str(target / "whole_test_seal/record.json")
        plan = publish(
            root / "protocol/record.json", {"jobs": [job], "implementation_id": manifest["id"]}
        )
        attempt = (
            root
            / ("execution_continuation_01" if continuation else "queue")
            / "jobs/cpu-fixture-job/attempt001"
        )
        command = [
            "/usr/bin/taskset",
            "--cpu-list",
            "0-1",
            "/unused/python",
            "-u",
            str(worker),
            *args,
            "--root",
            str(root / branch),
            "--gpu-index",
            "6",
        ]
        protocol = {"protocol_id": "new-execution-protocol" if continuation else plan["id"]}
        if continuation:
            protocol["scientific_protocol_id"] = plan["id"]
        publish(
            attempt / "intent/record.json", protocol | {"job": job, "gpu": 6, "command": command}
        )
        publish(
            attempt / "launch/record.json",
            protocol | {"job": job, "gpu": 6, "command": command, "pid": 12345, "birth": "67890"},
        )
        publish(
            attempt / "exit/record.json",
            protocol | {"key": job["key"], "exit_code": 1, "completed": False, "result": None},
        )
        line = max(lines) if second_gate else min(lines)
        (attempt / "worker.log").write_text(
            "Traceback (most recent call last):\n"
            f'  File "{worker}", line {line}, in {function}\n'
            "    row = final.eligible_gpu(plan, gpu_index, final.gpu_inventory())\n"
            '  File "/frozen/v9_training_launcher.py", line 365, in eligible_gpu\n'
            "    require(\n"
            '  File "/frozen/v9_training_launcher.py", line 46, in require\n'
            "    raise ValueError(message)\n" + proof.ERROR + "\n"
        )
        if kind == "test":
            publish(
                target / "shards/test1147/generation/run.json",
                {
                    "role": "test",
                    "registered_denominator": 1147,
                    "episode_keys": [f"registered-task-{n}" for n in range(1147)],
                },
            )
            if branch == "replication_evaluation":
                publish(target / "checkpoint_binding/record.json", {"cpu_fixture": True})
        return root, job, attempt, target

    return make


@pytest.mark.parametrize(
    "kind,branch",
    [
        ("test", "c_only_test_extension"),
        ("test", "replication_evaluation"),
        ("prefix", "training_replication"),
        ("arm", "training_replication"),
    ],
)
@pytest.mark.parametrize("continuation,second_gate", [(False, False), (True, True)])
def test_clean_original_and_future_attempts_are_read_only(
    make_case, kind, branch, continuation, second_gate
):
    root, job, attempt, target = make_case(
        kind, branch=branch, continuation=continuation, second_gate=second_gate
    )
    before = {str(p): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    evidence = proof.prove_clean_precompute_rejection(root, job, attempt)
    assert evidence["clean"] is True
    assert evidence["current_gpu_capacity_consulted"] is False
    assert evidence["scientific_budget_consumed_by_attempt"] == {
        "provider_calls": 0,
        "episodes": 0,
        "optimizer_steps": 0,
        "outer_updates": 0,
    }
    assert evidence["scientific_target"]["counts"]["scientific_files"] == 0
    assert before == {str(p): p.read_bytes() for p in root.rglob("*") if p.is_file()}


@pytest.mark.parametrize(
    "relative",
    [
        "attempts/001/intent/record.json",
        "shards/test1147/generation/calls/a/intent.json",
        "shards/test1147/generation/calls/a/receipt.json",
        "shards/test1147/generation/episodes/a.json",
        "shards/test1147/generation/generation_seal/seal.json",
        "scores/record.json",
        "unexpected-output.bin",
    ],
)
def test_zero_episodes_does_not_prove_absence_of_provider_work(make_case, relative):
    root, job, attempt, target = make_case()
    path = target / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("scientific or uncertain work exists")
    with pytest.raises(ValueError, match="non-registration scientific"):
        proof.prove_clean_precompute_rejection(root, job, attempt)


@pytest.mark.parametrize(
    "relative",
    [
        "launch_attempts/attempt001/intent/record.json",
        "fresh_initialization/record.json",
        "prefix/step0000_step/state.pt",
        "training/step0299_step/record.json",
        "feedback/intent.json",
    ],
)
def test_any_training_state_or_attempt_intent_disallows_requeue(make_case, relative):
    root, job, attempt, target = make_case("prefix")
    path = target / relative
    path.parent.mkdir(parents=True)
    path.write_text("not safe")
    with pytest.raises(ValueError, match="training target already exists"):
        proof.prove_clean_precompute_rejection(root, job, attempt)


def test_empty_attempt_directory_is_also_uncertain(make_case):
    root, job, attempt, target = make_case()
    (target / "attempts").mkdir()
    with pytest.raises(ValueError, match="non-registration scientific directory"):
        proof.prove_clean_precompute_rejection(root, job, attempt)


@pytest.mark.parametrize("bad", ["same_pid_birth", "orphaned_child", "missing_birth"])
def test_live_process_or_ambiguous_identity_blocks_proof(make_case, monkeypatch, bad):
    root, job, attempt, _ = make_case()
    if bad == "same_pid_birth":
        monkeypatch.setattr(proof, "process_snapshot", lambda pid: {"birth": "67890", "state": "S"})
    elif bad == "orphaned_child":
        monkeypatch.setattr(proof, "process_group_members", lambda pid: [{"pid": 54321}])
    else:
        rewrite(attempt / "launch/record.json", birth=None)
    with pytest.raises(ValueError, match="alive|live processes|process identity"):
        proof.prove_clean_precompute_rejection(root, job, attempt)


def test_reused_pid_with_different_birth_is_not_original_worker(make_case, monkeypatch):
    root, job, attempt, _ = make_case()
    monkeypatch.setattr(proof, "process_snapshot", lambda pid: {"birth": "later", "state": "S"})
    assert proof.prove_clean_precompute_rejection(root, job, attempt)["clean"]


@pytest.mark.parametrize(
    "bad",
    [
        "completed",
        "wrong_job",
        "wrong_protocol",
        "wrong_exit",
        "wrong_source",
        "wrong_line",
        "unrelated_error",
        "second_traceback",
        "resume",
    ],
)
def test_fail_closed_for_nonmatching_failure_or_mutated_evidence(make_case, bad):
    root, job, attempt, _ = make_case()
    if bad == "completed":
        rewrite(attempt / "exit/record.json", completed=True)
    elif bad == "wrong_job":
        rewrite(attempt / "exit/record.json", key="different-job")
    elif bad == "wrong_protocol":
        rewrite(attempt / "exit/record.json", protocol_id="another")
    elif bad == "wrong_exit":
        rewrite(attempt / "exit/record.json", exit_code=-9)
    elif bad == "wrong_source":
        (root / "implementation" / job["script"]).write_text("# changed worker")
    elif bad in ("wrong_line", "unrelated_error", "second_traceback"):
        path = attempt / "worker.log"
        text = path.read_text()
        text = text.replace("line 580", "line 614") if bad == "wrong_line" else text
        text = (
            text.replace(proof.ERROR, "RuntimeError: CUDA out of memory")
            if bad == "unrelated_error"
            else text
        )
        text = "Traceback (most recent call last):\n" + text if bad == "second_traceback" else text
        path.write_text(text)
    else:
        for name in ("intent", "launch"):
            path = attempt / name / "record.json"
            rewrite(path, command=json.loads(path.read_text())["command"] + ["--resume"])
    with pytest.raises(ValueError):
        proof.prove_clean_precompute_rejection(root, job, attempt)


def test_symlink_cannot_hide_scientific_content(make_case, tmp_path):
    root, job, attempt, target = make_case()
    other = tmp_path / "outside"
    other.mkdir()
    (target / "episodes").symlink_to(other, target_is_directory=True)
    with pytest.raises(ValueError, match="symlinked"):
        proof.prove_clean_precompute_rejection(root, job, attempt)
