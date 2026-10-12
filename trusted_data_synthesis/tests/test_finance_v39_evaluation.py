"""CPU-only checks of the temporary device adapter and unchanged evaluator calls."""

import asyncio
import copy
import importlib
import json
import sys
import time
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
subject = importlib.import_module("finqa_v39_evaluation")
original_shell = importlib.import_module("finqa_v37_evaluation")


def require(condition, message):
    if not condition:
        raise ValueError(message)


@pytest.fixture
def endpoint(tmp_path, monkeypatch):
    calls = []
    plan = dict(
        id="new-handoff-protocol",
        allowed_gpu_indices=list(subject.admission.ALLOWED_GPUS),
        gpu_uuids=dict(subject.admission.GPU_UUIDS),
        evaluation_root=str(tmp_path / "original_eval"),
    )
    ready = dict(index=6, uuid=plan["gpu_uuids"]["6"], free_mib=80000, processes=[])
    source_row = dict(index=6, uuid=ready["uuid"], free=80000)
    science = dict(
        id="unchanged-scientific-evaluation",
        block="B",
        jobs={"seed389/c_only": {"id": "original-job"}},
        device_policy=dict(allowed_gpu_indices=[3, 4, 5, 7], minimum_free_mib=60000),
        generation={"temperature": 0, "answer_limit": 1147},
    )
    before = copy.deepcopy(science)
    state = SimpleNamespace(cuda=False, resets=0, sealed=False, stopped=False)

    def publish(path, body):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x") as stream:
            json.dump(dict(body, id="record-id"), stream)
        return dict(body, id="record-id")

    control = SimpleNamespace(
        __file__=str(tmp_path / "implementation/finqa_v39_controller.py"),
        checked_protocol=lambda _root: plan,
        checked_implementation=lambda _root: {},
        require=require,
        publish=publish,
        now=lambda: "2026-10-12T00:00:00+00:00",
        birth=lambda _pid: 123,
        inventory=lambda: [ready],
        host_memory=lambda: dict(available_bytes=256 * 1024**3),
        process_memory=lambda _pid: dict(rss_bytes=1024, peak_rss_bytes=1024),
        entry=lambda path: {"path": str(path), "id": "record-id"},
    )

    def reset():
        assert not state.cuda
        state.cuda = True
        state.resets += 1

    class Provider:
        async def chat(self, payload):
            calls.append(("original_response", payload))
            return "unchanged-answer"

    def original_loader(*args, **kwargs):
        calls.append(("original_model_load", args, kwargs))
        return Provider()

    def original_eligible(view, index, inventory):
        calls.append(("original_eligible", copy.deepcopy(view), index))
        require(index in view["device_policy"]["allowed_gpu_indices"], "old card gate")
        row = next(row for row in inventory if row["index"] == index)
        require(row["free"] >= view["device_policy"]["minimum_free_mib"], "old memory gate")
        return row

    final = SimpleNamespace(
        torch=SimpleNamespace(
            cuda=SimpleNamespace(
                is_initialized=lambda: state.cuda,
                reset_peak_memory_stats=reset,
            )
        ),
        eligible_gpu=original_eligible,
        load_final_provider=original_loader,
    )
    model_dir = Path(plan["evaluation_root"]) / "seed389_c_only"
    seal_path = model_dir / "whole_test_seal/record.json"

    def generate(root, seed, arm, gpu, *, resume):
        calls.append(("original_generate", root, seed, arm, gpu, resume))
        assert science == before and resume is False
        assert final.eligible_gpu(science, gpu, [source_row]) is source_row
        assert final.eligible_gpu(science, gpu, [source_row]) is source_row
        provider = final.load_final_provider(science, science["jobs"]["seed389/c_only"], "state")
        assert asyncio.run(provider.chat("original-test-input")) == "unchanged-answer"
        del provider
        return publish(seal_path, {"sealed": True})

    evaluator = SimpleNamespace(
        arm_name=lambda _arm: "C-only",
        load_runtime=lambda: final,
        checked_plan=lambda *_args: science,
        coordinate=lambda seed, arm: f"seed{seed}/{arm}",
        model_root=lambda *_args: model_dir,
        generate=generate,
    )
    monkeypatch.setattr(original_shell, "frozen_evaluator", lambda _plan: evaluator)
    monkeypatch.setattr(subject, "_controller", lambda: control)
    monkeypatch.setattr(subject, "_parent_module", lambda *_args: original_shell)
    monkeypatch.setattr(
        subject, "__file__", str(tmp_path / "implementation/finqa_v39_evaluation.py")
    )
    monkeypatch.setattr(
        subject.admission, "__file__", str(tmp_path / "implementation/finqa_v39_admission.py")
    )

    class Pause:
        requested = False

        def signals(self):
            return nullcontext()

    class Monitor:
        def __init__(self, torch, *, event_sink, stop_requested):
            self.sink = event_sink

        def snapshot(self, label, **kwargs):
            self.sink(dict(label=label, passed=True))

        def clear_unused(self, label):
            self.snapshot(label)

        def check_stop(self, label, **kwargs):
            self.snapshot(label)

    modules = {
        "finqa_v34_tail_memory": SimpleNamespace(TailMemoryMonitor=Monitor),
        "finqa_v32_replay_variants": SimpleNamespace(PauseRequest=Pause),
        "finqa_v35_task_worker": SimpleNamespace(
            host_memory=lambda: dict(
                peak_rss_bytes=1024,
                available_bytes=256 * 1024**3,
            )
        ),
        "finqa_v34_tail_worker": SimpleNamespace(
            accepted_resources=lambda *_args: dict(
                all_gates_passed=True,
                maximum_allocated_bytes=76 * 1024**3,
                minimum_device_free_bytes=2 * 1024**3,
                peak_resets_after_model_loading_begins=0,
            )
        ),
        "finqa_v32_performance_worker": SimpleNamespace(DeviceSamples=lambda _uuid: nullcontext()),
    }
    monkeypatch.setattr(subject, "importlib", SimpleNamespace(import_module=modules.__getitem__))

    def wait(protocol, stage, gpu, directory, deadline, torch, stop, **kwargs):
        calls.append(("admission", stage, gpu))
        assert protocol is plan and not torch.cuda.is_initialized()
        assert gpu == 6 and kwargs["context_id"] == "evaluation:389:c_only"
        assert deadline > time.time() and not stop()
        return ready

    monkeypatch.setattr(subject.admission, "wait_for_pre_cuda_admission", wait)
    return SimpleNamespace(
        root=tmp_path,
        plan=plan,
        ready=ready,
        source_row=source_row,
        science=science,
        before=before,
        control=control,
        final=final,
        original_eligible=original_eligible,
        original_loader=original_loader,
        calls=calls,
        state=state,
        seal_path=seal_path,
        publish=publish,
    )


def test_gpu6_generation_crosses_both_old_admission_gates_without_scientific_changes(endpoint):
    f = endpoint
    previous = original_shell.control
    result = subject.run(f.root, 389, "c_only", 6, time.time() + 3600)
    assert result["status"] == "COMPLETE" and result["protocol_id"] == f.plan["id"]
    assert result["gpu_index"] == 6 and result["gpu_uuid"] == f.plan["gpu_uuids"]["6"]
    assert result["scoring_calls"] == result["API_calls"] == 0
    assert result["resources"]["maximum_allocated_bytes"] == 76 * 1024**3
    assert result["resources"]["host"]["rss_limit_bytes"] == 192 * 1024**3
    assert result["resources"]["host"]["available_reserve_bytes"] == 96 * 1024**3
    gates = [row for row in f.calls if row[0] == "original_eligible"]
    assert len(gates) == 2 and f.state.resets == 1
    assert all(row[1]["device_policy"]["allowed_gpu_indices"] == [3, 4, 5, 6, 7] for row in gates)
    assert all(row[1]["device_policy"]["minimum_free_mib"] == 72 * 1024 for row in gates)
    assert all(row[1]["generation"] == f.before["generation"] for row in gates)
    assert f.science == f.before
    assert f.final.eligible_gpu is f.original_eligible
    assert f.final.load_final_provider is f.original_loader
    assert original_shell.control is previous


def test_complete_model_is_not_generated_or_admitted_again(endpoint):
    f = endpoint
    f.publish(f.seal_path, {"sealed": True})
    with pytest.raises(ValueError, match="completed model"):
        subject.run(f.root, 389, "c_only", 6, time.time() + 3600)
    assert not f.calls and not f.state.cuda


@pytest.mark.parametrize("gpu", [0, 1, 2, 8])
def test_unauthorized_gpu_cannot_reach_original_evaluator(endpoint, gpu):
    f = endpoint
    with pytest.raises(ValueError, match="unregistered"):
        subject.run(f.root, 389, "c_only", gpu, time.time() + 3600)
    assert not f.calls and not f.state.cuda


@pytest.mark.parametrize("change", ["uuid", "busy", "free", "deadline", "stop"])
def test_nested_adapter_keeps_identity_margin_and_stop_gates(endpoint, change):
    f = endpoint
    stop = SimpleNamespace(requested=change == "stop")
    deadline = time.time() - 1 if change == "deadline" else time.time() + 10
    if change == "uuid":
        f.ready["uuid"] = "different"
    elif change == "busy":
        f.ready["processes"] = [{"pid": 999}]
    elif change == "free":
        f.ready["free_mib"] = 73727
    with pytest.raises(ValueError):
        with subject.endpoint_gpu_policy(f.final, f.plan, 6, f.control, stop, deadline):
            f.final.eligible_gpu(f.science, 6, [f.source_row])
    assert not f.calls and f.science == f.before
    assert f.final.eligible_gpu is f.original_eligible


def test_adapter_cannot_redirect_to_a_different_allowed_card(endpoint):
    f = endpoint
    with pytest.raises(ValueError, match="dispatched physical"):
        with subject.endpoint_gpu_policy(
            f.final, f.plan, 6, f.control, SimpleNamespace(requested=False), time.time() + 10
        ):
            f.final.eligible_gpu(f.science, 5, [f.source_row])
    assert f.final.eligible_gpu is f.original_eligible


def test_original_stricter_free_margin_is_preserved(endpoint):
    f = endpoint
    f.science["device_policy"]["minimum_free_mib"] = 81000
    with pytest.raises(ValueError, match="old memory gate"):
        with subject.endpoint_gpu_policy(
            f.final, f.plan, 6, f.control, SimpleNamespace(requested=False), time.time() + 10
        ):
            f.final.eligible_gpu(f.science, 6, [f.source_row])
    assert f.final.eligible_gpu is f.original_eligible


def test_scoring_delegates_only_to_unchanged_nine_model_barrier(endpoint, monkeypatch):
    f = endpoint
    sentinel = object()
    monkeypatch.setattr(
        original_shell,
        "score",
        lambda root: (f.calls.append(("original_nine_seal_scoring_barrier", root)), sentinel)[1],
    )
    assert subject.score(f.root) is sentinel
    assert f.calls == [("original_nine_seal_scoring_barrier", f.root)]
    assert f.final.eligible_gpu is f.original_eligible and not f.state.cuda
