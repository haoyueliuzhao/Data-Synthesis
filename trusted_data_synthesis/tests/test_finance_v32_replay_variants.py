"""CPU-only storage equivalence and durable ordered-H_k pause controls."""

import importlib
import json
import signal
import sys
from pathlib import Path

import pytest
import torch
from test_finance_v19_optimized_replay import cpu_baseline, tiny
from test_finance_v19_replay_state import Backend, fixture

from trusted_synthesis.finance_research.feedback import feedback_gradient as original_gradient

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
v32 = importlib.import_module("finqa_v32_replay_variants")


def run(local, cohort, rewards, root, backend, **kwargs):
    return v32.feedback_gradient(
        cohort,
        rewards,
        local.model,
        local.parameters,
        root=root,
        profile_id="v32-cpu-test",
        backend_factory=lambda *a: backend,
        backend_identity={"variant": "R1", "version": v32.BACKEND_VERSION},
        rng_restore_source={"kind": "cpu_fixture", "id": "fixed-source"},
        cpu_test=True,
        **kwargs,
    )


@pytest.mark.parametrize("variant", ["R1", "R2"])
def test_fixed8_bytecode_full_gradients_and_bank_reuse(variant):
    model, theta = tiny()
    prompt, targets = [2, 3, 5, 7], list(range(1, 18))
    values, gradients, _ = cpu_baseline()(model, theta, prompt, targets, block_size=8, offload=True)
    rng = torch.get_rng_state().clone()
    monitor = []
    session = v32.ReplaySession(
        model,
        theta,
        variant=variant,
        profile_id="cpu",
        cpu_test=True,
        response_monitor=monitor.append,
    )
    frozen_forward = v32.optimized.legacy.SegmentedOperation.forward
    for call in range(2):
        actual, derivative, report = session(
            model, theta, prompt, targets, expected=values.tolist()
        )
        assert torch.equal(actual, values)
        assert all(torch.equal(gradients[name], derivative[name]) for name in gradients)
        assert report["cached_frozen_bank_responses"] == call + 1
        assert report["complete_prefix_adjoint_included"]
        assert (
            report["single_complete_CPU_KV_bytes"] > 0
            if variant == "R1"
            else report["single_complete_CPU_KV_bytes"] == 0
        )
        assert (
            report["single_complete_GPU_KV_bytes"] == 0
            if variant == "R1"
            else report["single_complete_GPU_KV_bytes"] > 0
        )
    assert session.operation.forward.__code__ is frozen_forward.__code__
    assert v32.optimized.legacy.SegmentedOperation.forward is frozen_forward
    assert torch.equal(torch.get_rng_state(), rng)
    assert [row["phase"] for row in monitor] == ["before_response", "after_response"] * 2
    assert session.bank.resident_limit == (0 if variant == "R1" else 2 * v32.GIB)
    session.close()


def test_r2_full_kv_admission_is_separate_from_saved_kv_budget():
    model, theta = tiny()
    session = v32.ReplaySession(
        model,
        theta,
        variant="R2",
        profile_id="cpu",
        cpu_test=True,
        full_kv_budget_bytes=1,
        resident_kv_budget_bytes=0,
    )
    with pytest.raises(ValueError, match="full-KV residency budget exceeded"):
        session(model, theta, [1, 2], [3, 4], expected=None)
    assert session.calls == 0
    session.close()


def test_registered_response16_pause_restores_actual_hk_without_double_add(tmp_path):
    local, cohort, rewards = fixture()
    expected, _ = original_gradient(
        cohort, rewards, local.model, local.parameters, replay=Backend()
    )
    first = Backend()
    with pytest.raises(v32.ReplayPaused) as caught:
        run(local, cohort, rewards, tmp_path, first, pause_after_response=16)
    assert first.calls == 16
    assert caught.value.checkpoint_record["cursor"] == 16
    state = torch.load(tmp_path / "response000016/state.pt", weights_only=False)
    assert state["total"]["weight"].item() != 0
    assert state["binding"]["reward_vector"] == rewards
    assert state["binding"]["backend_identity"]["variant"] == "R1"
    assert state["binding"]["rng_restore_source"]["id"] == "fixed-source"
    second = Backend()
    actual, report = run(local, cohort, rewards, tmp_path, second)
    assert second.calls == sum(rewards) - 16
    assert torch.equal(actual["weight"], expected["weight"])
    assert report["restored_completed_responses"] == 16
    assert report["new_sampling_calls"] == report["optimizer_steps_performed"] == 0


def test_pause_during_response_commits_next_complete_response_not_next16(tmp_path):
    local, cohort, rewards = fixture(6)
    request = v32.PauseRequest()

    class InterruptingBackend(Backend):
        def __call__(self, *args, **kwargs):
            result = super().__call__(*args, **kwargs)
            if self.calls == 3:
                request.signal_handler(signal.SIGTERM, None)
            return result

    with pytest.raises(v32.ReplayPaused) as caught:
        run(local, cohort, rewards, tmp_path, InterruptingBackend(), pause_request=request)
    assert caught.value.checkpoint_record["cursor"] == 3
    assert caught.value.report["pause_reason"] == f"signal:{signal.SIGTERM}"
    assert (tmp_path / "response000003/state.pt").is_file()
    backend = Backend()
    actual, _ = run(local, cohort, rewards, tmp_path, backend)
    expected, _ = original_gradient(
        cohort, rewards, local.model, local.parameters, replay=Backend()
    )
    assert backend.calls == sum(rewards) - 3
    assert torch.equal(actual["weight"], expected["weight"])


@pytest.mark.parametrize("failure", ["logp", "gradient", "exception"])
def test_requested_pause_never_commits_invalid_or_incomplete_response(tmp_path, failure):
    local, cohort, rewards = fixture(3)
    request = v32.PauseRequest()

    class BrokenBackend(Backend):
        def __call__(self, *args, **kwargs):
            values, gradient, used = super().__call__(*args, **kwargs)
            request.request()
            if failure == "exception":
                raise RuntimeError("mid-response failure")
            if failure == "logp":
                values = values + 1
            else:
                gradient["weight"].fill_(float("nan"))
            return values, gradient, used

    with pytest.raises((ValueError, RuntimeError)) as caught:
        run(local, cohort, rewards, tmp_path, BrokenBackend(), pause_request=request)
    assert not isinstance(caught.value, v32.ReplayPaused)
    assert not list(tmp_path.glob("response*"))
    assert json.loads((tmp_path / "progress/status.json").read_text())["completed_responses"] == 0


def test_pause_before_work_saves_zero_and_no_backend_calls(tmp_path):
    local, cohort, rewards = fixture(3)
    request = v32.PauseRequest()
    request.request("preexisting")
    backend = Backend(fail_after=0)
    with pytest.raises(v32.ReplayPaused) as caught:
        run(local, cohort, rewards, tmp_path, backend, pause_request=request)
    assert backend.calls == 0 and caught.value.checkpoint_record["cursor"] == 0
    assert (
        torch.load(tmp_path / "response000000/state.pt", weights_only=False)["total"][
            "weight"
        ].item()
        == 0
    )


def test_backend_and_rng_source_are_immutable_checkpoint_binding(tmp_path):
    local, cohort, rewards = fixture(3)
    with pytest.raises(v32.ReplayPaused):
        run(local, cohort, rewards, tmp_path, Backend(), pause_after_response=1)
    with pytest.raises(ValueError, match="another profile"):
        v32.feedback_gradient(
            cohort,
            rewards,
            local.model,
            local.parameters,
            root=tmp_path,
            profile_id="v32-cpu-test",
            backend_factory=lambda *a: Backend(),
            backend_identity={"variant": "R2", "version": v32.BACKEND_VERSION},
            rng_restore_source={"kind": "cpu_fixture", "id": "fixed-source"},
            cpu_test=True,
        )
