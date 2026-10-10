"""CPU/mock checks that V38 admission delegates the frozen endpoint and score paths."""

import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
subject = importlib.import_module("finqa_v38_evaluation")


@pytest.fixture
def endpoint(tmp_path, monkeypatch):
    calls = []
    plan = dict(id="recovery-protocol", gpu_uuids={"4": "GPU-four"})
    ready = dict(index=4, uuid="GPU-four", free_mib=80000, processes=[])

    def require(value, message):
        if not value:
            raise ValueError(message)

    def publish(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x") as stream:
            json.dump(value, stream)
        return value

    control = SimpleNamespace(
        checked_protocol=lambda _root: plan,
        require=require,
        publish=publish,
        now=lambda: "2026-10-10T00:00:00+00:00",
        birth=lambda _pid: "birth",
        inventory=lambda: [ready],
        host_memory=lambda: dict(available_bytes=256 * 1024**3),
        process_memory=lambda _pid: dict(rss_bytes=1024, peak_rss_bytes=1024),
    )
    original_control = object()

    def original_hook(*_args, **_kwargs):
        return None

    sealed_result, scored_result = object(), object()
    parent = SimpleNamespace(control=original_control, install_observation_hook=original_hook)

    def generate(*arguments):
        calls.append(("parent_enter", arguments))
        row = parent.control.inventory()
        calls.append(("parent_generate", row))
        return sealed_result

    def score(root):
        calls.append(("parent_nine_seal_score_barrier", root))
        return scored_result

    def wait(*arguments, **keywords):
        calls.append(("admission", arguments, keywords))
        return ready

    parent.run, parent.score = generate, score
    fake_torch = object()
    monkeypatch.setattr(subject, "_controller", lambda: control)
    monkeypatch.setattr(subject, "_parent_module", lambda *_args: parent)
    monkeypatch.setattr(subject, "_torch", lambda: fake_torch)
    monkeypatch.setattr(
        subject, "__file__", str(tmp_path / "implementation/finqa_v38_evaluation.py")
    )
    monkeypatch.setattr(subject, "wait_for_pre_cuda_admission", wait)
    return SimpleNamespace(
        root=tmp_path,
        calls=calls,
        parent=parent,
        control=control,
        plan=plan,
        original_control=original_control,
        original_hook=original_hook,
        sealed_result=sealed_result,
        scored_result=scored_result,
        torch=fake_torch,
    )


def test_generation_is_the_same_parent_call_after_bound_wait(endpoint):
    f = endpoint
    assert subject.run(f.root, 137, "c_only", 4, 10000) is f.sealed_result
    assert [row[0] for row in f.calls] == ["parent_enter", "admission", "parent_generate"]
    arguments, keywords = f.calls[1][1:]
    assert arguments[:3] == (f.plan, "generate", 4)
    assert arguments[3] == f.root / "evaluations/seed137_c_only/generate"
    assert arguments[4:6] == (10000, f.torch)
    assert keywords["context_id"] == "evaluation:137:c_only"
    assert f.parent.control is f.original_control
    assert f.parent.install_observation_hook is f.original_hook


def test_pre_cuda_failure_is_saved_without_generation_or_scoring(endpoint, monkeypatch):
    f = endpoint

    def stopped(*_args, **_kwargs):
        raise subject.AdmissionStopped("requested during CPU admission")

    monkeypatch.setattr(subject, "wait_for_pre_cuda_admission", stopped)
    with pytest.raises(subject.AdmissionStopped):
        subject.run(f.root, 137, "full", 4, 10000)
    assert [row[0] for row in f.calls] == ["parent_enter"]
    record = json.loads(
        (f.root / "evaluations/seed137_full/generate/failure/record.json").read_text()
    )
    assert record["context_id"] == "evaluation:137:full"
    assert record["actual_response_calls"] == record["scoring_calls"] == 0
    assert f.parent.control is f.original_control


def test_score_delegates_to_parent_barrier_and_never_calls_admission(endpoint):
    f = endpoint
    assert subject.score(f.root) is f.scored_result
    assert f.calls == [("parent_nine_seal_score_barrier", f.root)]
    assert f.parent.control is f.original_control


def test_stop_between_admission_and_loader_prevents_even_the_original_observation_reset():
    calls = []
    final = SimpleNamespace()
    stop = SimpleNamespace(requested=False)
    state, loader = object(), object()

    def original_hook(final, factory, stop_requested):
        def observed_loader(*args, **kwargs):
            calls.append((args, kwargs))

        final.load_final_provider = observed_loader
        calls.append(stop_requested)
        return state, loader

    observed = subject._observation_bridge(original_hook, stop)
    assert observed(final, object(), lambda: False) == (state, loader)
    stop.requested = True
    with pytest.raises(subject.AdmissionStopped):
        final.load_final_provider("unchanged-model-arguments")
    assert len(calls) == 1 and calls[0]() is True
