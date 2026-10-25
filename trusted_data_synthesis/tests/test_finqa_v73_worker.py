"""No-model tests of V73's intent/return boundary and exact saved-result reuse."""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import finqa_v73_binding as b
import finqa_v73_worker as worker


def job_fixture():
    return dict(job_id="P.shard0", model="P", context_ids=["ctx"], target_keys=[])


def intent(job, attempt=1, *, source="source", kind="generation", key="ctx"):
    op = key if kind == "generation" else b.digest(key)
    root = worker.directory(job) / "attempts" / f"attempt{attempt:04d}"
    path = root / "operations" / kind / op / "intent.json"
    return b.publish(path, dict(protocol_id="protocol", job_id=job["job_id"], model=job["model"],
        kind=kind, key=key, operation_id=op, input_id="input", source_binding_id=source,
        attempt_root=str(root), created_epoch=float(attempt))), path


def returned(job, call):
    body = {k: call[k] for k in ("protocol_id", "job_id", "model", "kind", "key", "operation_id",
                               "input_id", "source_binding_id", "attempt_root")}
    path = worker.directory(job) / "outputs" / call["kind"] / call["operation_id"] / "returned.json"
    return b.publish(path, dict(body, intent_id=call["id"], value={}, returned_epoch=3.0))


def unexecuted(path, call, **overrides):
    body = dict(intent_id=call["id"], confirmed_forward_calls=0,
                actual_generate_calls=0, confirmed_resource_failure=True)
    body.update(overrides)
    return b.publish(path.parent / "not_executed.json", body)


def test_unresolved_intent_blocks_resume(tmp_path, monkeypatch):
    monkeypatch.setattr(b, "ROOT", tmp_path)
    job = job_fixture()
    intent(job)
    result = worker.audit(job, "protocol", "source")
    assert result["unknown_calls"] == 1
    assert result["resume_allowed"] is False


def test_valid_pre_call_resource_proof_allows_a_later_return(tmp_path, monkeypatch):
    monkeypatch.setattr(b, "ROOT", tmp_path)
    job = job_fixture()
    old, path = intent(job)
    unexecuted(path, old)
    new, _ = intent(job, 2)
    returned(job, new)
    result = worker.audit(job, "protocol", "source")
    assert result["progress_units"] == 1 and result["unknown_calls"] == 0


@pytest.mark.parametrize("override", [dict(actual_generate_calls=1), dict(confirmed_forward_calls=1),
                                      dict(intent_id="other"), dict(confirmed_resource_failure=False)])
def test_old_abort_proof_is_verified_even_after_new_return(tmp_path, monkeypatch, override):
    monkeypatch.setattr(b, "ROOT", tmp_path)
    job = job_fixture()
    old, path = intent(job)
    unexecuted(path, old, **override)
    new, _ = intent(job, 2)
    returned(job, new)
    with pytest.raises(ValueError, match="no-execution proof"):
        worker.audit(job, "protocol", "source")


def test_orphan_return_cannot_count_as_completed(tmp_path, monkeypatch):
    monkeypatch.setattr(b, "ROOT", tmp_path)
    job = job_fixture()
    call, path = intent(job)
    returned(job, call)
    path.unlink()
    with pytest.raises(ValueError, match="no corresponding"):
        worker.audit(job, "protocol", "source")


def test_moved_intent_and_different_model_source_are_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(b, "ROOT", tmp_path)
    job = job_fixture()
    _, path = intent(job)
    with pytest.raises(ValueError, match="foreign"):
        worker.audit(job, "protocol", "different checkpoint")
    moved = Path(str(path).replace("attempt0001", "attempt0002"))
    moved.parent.mkdir(parents=True)
    path.rename(moved)
    with pytest.raises(ValueError, match="moved"):
        worker.audit(job, "protocol", "source")


class ResourceFailure(RuntimeError):
    pass


def run_fixture(tmp_path, monkeypatch, *, mode="normal", include_probability=False):
    monkeypatch.setattr(b, "ROOT", tmp_path)
    job = job_fixture()
    if include_probability:
        job["target_keys"] = ["task"]
    source = dict(checkpoint={"saved": True}, model_identity={"point_id": "P1192"})
    context = dict(request={"messages": [{"role": "user", "content": "question"}], "tools": []},
                   prompt_input_ids=[10, 11])
    bundle = dict(contexts={"ctx": context}, targets={"task": dict(target_id="target",
                  prompt_input_ids=[10, 11], raw_generated_token_ids=[12, 13])})
    b.publish(tmp_path / "inputs/record.json", bundle)
    protocol = dict(id="protocol", jobs={job["job_id"]: job}, model_bindings={"P": source},
                    gpu_uuids={"6": "GPU-test"}, inputs=b.entry(tmp_path / "inputs/record.json"))
    tracker = dict(instances=0, generated=0, measured=0, classified=0, post_failure=False)

    class Guard:
        def check(self, label, **kwargs):
            if label == "after_durable_probe_return" and mode == "post_return_resource" and not tracker["post_failure"]:
                tracker["post_failure"] = True
                assert (worker.directory(job) / "outputs/generation/ctx/returned.json").exists()
                raise ResourceFailure("after actual return")

        def report(self):
            return dict(all_gates_passed=True)

    @contextmanager
    def execution_context(*args):
        yield Guard()

    class Predictor:
        def __init__(self, *args):
            tracker["instances"] += 1
            self.provider = SimpleNamespace(actual_model_calls=0)
            self.counts = {}
            self.load_evidence = dict(model_identity=source["model_identity"],
                saved_A_B_installed_directly=True, random_LoRA_initialization_calls=0,
                optimizer_objects_created=0, backward_calls=0)

        @property
        def counters(self):
            return dict(self.counts)

        def generate(self, item):
            assert any(worker.directory(job).glob("attempts/*/operations/generation/ctx/intent.json"))
            assert "raw_generated_token_ids" not in item
            if mode == "before_generate_resource":
                raise ResourceFailure("zero model calls")
            self.provider.actual_model_calls += 1
            tracker["generated"] += 1
            if mode == "entered_generate_without_hook":
                raise ResourceFailure("model.generate entered before any forward hook")
            self.counts["model_forward_calls"] = 1
            raw = "response"
            receipt = dict(identity=source["model_identity"], prompt_input_ids=item["prompt_input_ids"],
                request_sha256=b.digest(item["request"]), raw_response_sha256=hashlib.sha256(raw.encode()).hexdigest(),
                raw_generated_token_ids=[12, 99], actual_eos=True, finish_reason="stop", sampling=dict(eos_token_ids=[99]))
            if mode == "wrong_source":
                receipt["identity"] = {"point_id": "other"}
            return dict(model_label="P", turn=dict(raw_text=raw, receipt=receipt))

        def measure(self, item):
            tracker["measured"] += 1
            self.counts["model_forward_calls"] = self.counts.get("model_forward_calls", 0) + 1
            return dict(model_label="P", target_id=item["target_id"], probability_summary=dict(sequences=1),
                        groups={"action_structure": {"nll": 1.0}})

        def close(self):
            pass

    def classify(*args):
        tracker["classified"] += 1
        return dict(category="ordinary_text", A=0, S=0)

    monkeypatch.setitem(sys.modules, "finqa_v73_registration", SimpleNamespace(checked_protocol=lambda: protocol))
    monkeypatch.setitem(sys.modules, "finqa_v73_resources", SimpleNamespace(execution_context=execution_context,
        ResourceDeferred=ResourceFailure, ResourceGateError=ResourceFailure,
        LifetimeResourceFailure=ResourceFailure, R3CapacityError=ResourceFailure))
    monkeypatch.setitem(sys.modules, "finqa_v73_runtime", SimpleNamespace(Predictor=Predictor))
    monkeypatch.setitem(sys.modules, "finqa_v73_measurement", SimpleNamespace(classification=classify,
        completion_labels=lambda **kwargs: dict(actual_eos=kwargs["actual_eos"])))
    monkeypatch.setenv("V54_JOB_ID", job["job_id"])
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "GPU-test")
    return job, protocol, tracker


def run_attempt(job, number):
    return worker.run(job["job_id"], 6, worker.directory(job) / "attempts" / f"attempt{number:04d}")


def test_return_is_durable_before_resource_check_and_reused_without_loading_model(tmp_path, monkeypatch):
    job, protocol, tracker = run_fixture(tmp_path, monkeypatch, mode="post_return_resource")
    with pytest.raises(ResourceFailure):
        run_attempt(job, 1)
    assert tracker["generated"] == 1
    assert worker.audit(job, protocol["id"], b.digest(protocol["model_bindings"]["P"]))["resume_allowed"]
    result = run_attempt(job, 2)
    assert result["status"] == "COMPLETE"
    assert tracker["generated"] == tracker["instances"] == tracker["classified"] == 1
    assert result["actual_new_forward_counters"] == {}
    assert (worker.directory(job) / "attempts/attempt0001/model_load/record.json").exists()
    assert not (worker.directory(job) / "attempts/attempt0002/model_load/record.json").exists()


def test_entered_generate_without_forward_hook_stays_UNKNOWN(tmp_path, monkeypatch):
    job, protocol, tracker = run_fixture(tmp_path, monkeypatch, mode="entered_generate_without_hook")
    with pytest.raises(ResourceFailure):
        run_attempt(job, 1)
    assert not list(worker.directory(job).glob("attempts/*/operations/*/*/not_executed.json"))
    assert worker.audit(job, protocol["id"])["unknown_calls"] == 1
    with pytest.raises(ValueError, match="unresolved model call"):
        run_attempt(job, 2)
    assert tracker["instances"] == 1 and tracker["generated"] == 1


def test_confirmed_zero_calls_and_zero_forwards_produce_retryable_proof(tmp_path, monkeypatch):
    job, protocol, tracker = run_fixture(tmp_path, monkeypatch, mode="before_generate_resource")
    with pytest.raises(ResourceFailure):
        run_attempt(job, 1)
    state = worker.audit(job, protocol["id"])
    proof_path = next(worker.directory(job).glob("attempts/*/operations/*/*/not_executed.json"))
    proof = b.checked(proof_path)
    assert proof["actual_generate_calls"] == proof["confirmed_forward_calls"] == 0
    assert state["resume_allowed"] and tracker["generated"] == 0


def test_generation_and_probability_channels_stay_separate_and_progress_is_written(tmp_path, monkeypatch):
    job, _, tracker = run_fixture(tmp_path, monkeypatch, include_probability=True)
    result = run_attempt(job, 1)
    assert tracker["generated"] == tracker["measured"] == tracker["classified"] == 1
    assert result["generation_results"] == result["probability_results"] == 1
    progress = json.loads((worker.directory(job) / "progress/status.json").read_text())
    assert progress["completed_operations"] == 2
    assert progress["generation_completed"] == progress["probability_completed"] == 1
    assert result["tools_executed"] == result["native_scores"] == result["optimizer_updates"] == 0
    loaded = b.checked(worker.directory(job) / "attempts/attempt0001/model_load/record.json")
    assert loaded["protocol_id"] == "protocol" and loaded["job_id"] == job["job_id"]
    assert loaded["load_evidence"]["saved_A_B_installed_directly"] is True
    assert loaded["load_evidence"]["random_LoRA_initialization_calls"] == 0


def test_wrong_model_return_is_not_normalized_or_marked_complete(tmp_path, monkeypatch):
    job, _, tracker = run_fixture(tmp_path, monkeypatch, mode="wrong_source")
    with pytest.raises(ValueError, match="frozen model/request"):
        run_attempt(job, 1)
    assert tracker["generated"] == 1 and tracker["classified"] == 0
    assert not (worker.directory(job) / "result/record.json").exists()
