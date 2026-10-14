"""CPU-only checks of the temporary device adapter and unchanged evaluator calls."""

import asyncio
import copy
import importlib
import json
import signal
import sys
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
subject = importlib.import_module("finqa_v43_evaluation")
original_shell = importlib.import_module("finqa_v37_evaluation")


def test_endpoint_audits_actual_stop_receipt_without_changing_stop_handler(monkeypatch, tmp_path):
    seen, records = [], []
    control = SimpleNamespace(
        now=lambda: "2026-10-12T23:00:00+08:00",
        checked=lambda path: dict(id="v40"),
        publish=lambda path, value: records.append((path, value)),
    )
    monkeypatch.setattr(subject, "_controller", lambda: control)

    def actual_run(*args):
        signal.signal(signal.SIGTERM, lambda number, frame: seen.append(number))
        signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)
        raise RuntimeError("normal cooperative stop")

    monkeypatch.setattr(subject, "_run", actual_run)
    previous = signal.getsignal(signal.SIGTERM)
    with pytest.raises(RuntimeError, match="normal cooperative stop"):
        subject.run(tmp_path, 389, "full", 3, None)
    assert seen == [signal.SIGTERM] and signal.getsignal(signal.SIGTERM) == previous
    assert len(records) == 1
    assert records[0][1]["received_signals"][0]["signal_number"] == signal.SIGTERM
    assert records[0][1]["sender_attribution"] == "unknown"
    assert records[0][1]["signals_ignored"] is False


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
        time_policy=subject.time_policy.record(),
        gpu_admission_policy=subject.policy.policy_record(
            scope=dict(
                allowed_gpu_indices=list(subject.admission.ALLOWED_GPUS),
                gpu_uuids=subject.admission.GPU_UUIDS,
            ),
            evidence_refs=[{"mock": True}],
        ),
    )
    ready = dict(index=6, uuid=plan["gpu_uuids"]["6"], free_mib=80000, processes=[])
    source_row = dict(
        index=6, uuid=ready["uuid"], free=80000, free_mib=48 * 1024, processes=[{"pid": 42}]
    )
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
        __file__=str(tmp_path / "implementation/finqa_v43_controller.py"),
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
        subject, "__file__", str(tmp_path / "implementation/finqa_v43_evaluation.py")
    )
    monkeypatch.setattr(
        subject.admission, "__file__", str(tmp_path / "implementation/finqa_v43_admission.py")
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
        assert gpu == ready["index"] and kwargs["context_id"] == "evaluation:389:c_only"
        assert deadline is None and not stop()
        return source_row

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


def test_real_none_endpoint_preserves_original_generator_and_runtime_safety(endpoint):
    f = endpoint
    result = subject.run(f.root, 389, "c_only", 6, None)
    assert result["status"] == "COMPLETE"
    assert result["minimum_free_mib"] == 48 * 1024
    assert result["time_policy_schema"] == subject.time_policy.SCHEMA
    assert result["resources"]["maximum_allocated_bytes"] == 76 * 1024**3
    assert result["resources"]["minimum_device_free_bytes"] == 2 * 1024**3
    assert result["resources"]["peak_resets_after_model_loading_begins"] == 0
    assert all(
        row["deadline_pass"] and row["wallclock_limits_removed"]
        for row in result["resources"]["observations"]
    )
    assert f.science == f.before
    assert not [call for call in f.calls if call[0] == "original_eligible"]
    assert len([call for call in f.calls if call[0] == "original_generate"]) == 1


def test_numeric_deadline_is_rejected_instead_of_becoming_sentinel(endpoint):
    with pytest.raises(ValueError, match="unexpected wall-clock"):
        subject.run(endpoint.root, 389, "c_only", 6, 1e300)
    assert not endpoint.calls
