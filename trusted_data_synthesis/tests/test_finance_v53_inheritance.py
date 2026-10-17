"""Focused V53 authority, native-proof and explicit-transition boundaries."""

import copy
import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
subject = importlib.import_module("finqa_v53_inheritance")
GIB = 1024**3


@pytest.mark.parametrize("mutation", [None, "automatic", "anchor", "raw_gate", "cursor137"])
def test_actual_controller_authority_reaches_explicit_transition_only_in_exact_scope(monkeypatch, mutation):
    controller = importlib.import_module("finqa_v53_controller")
    body = controller.authorization_body(parentroot=subject.SOURCE_ROOT, automatic=False)
    assert subject.ROOT.name == "r3_native_recovery_01"
    assert subject.SOURCE_ROOT.name == "signal_checkpoint_recovery_03"
    assert body["max_gpu_workers"] is body["independent_total_worker_limit"] is None
    assert body["allowed_gpu_indices"] == [0, 1, 3, 4, 5, 6, 7]
    if mutation == "automatic":
        body["automatic_attempt"] = True
    elif mutation == "anchor":
        body["R3_anchor_disabled"] = False
    elif mutation == "raw_gate":
        body["R3_original_empty_cache_unchanged"] = False
    elif mutation == "cursor137":
        body["initial_inherited_response_count"] = 137

    class TransitionReached(RuntimeError):
        pass

    def reached(parent, protocol):
        assert parent == subject.SOURCE_ROOT
        assert protocol["id"] == subject.SOURCE_PROTOCOL_ID
        raise TransitionReached("actual producer authority accepted")

    monkeypatch.setattr(subject, "_inspect_explicit_source_stop", reached)
    with pytest.raises(TransitionReached if mutation is None else ValueError):
        subject.inspect_authorized_recovery(
            subject.ROOT, subject.SOURCE_ROOT, authorization_body=body
        )


def test_native_physical_failure_uses_native_invariants_not_nonexistent_anchor():
    value = dict(
        stage="replay_R3",
        observation=dict(
            label="response.boundary", allocated_bytes=20 * GIB,
            reserved_bytes=24 * GIB, peak_allocated_bytes=22 * GIB,
            peak_reserved_bytes=24 * GIB, physical_free_bytes=GIB,
            device_total_bytes=80 * GIB,
        ),
        required_physical_free_bytes=2 * GIB,
        lifetime_allocated_limit_bytes=76 * GIB,
        reason="physical_boundary_free_exhausted",
        model_load_started=True,
        proof_no_scientific_work=False,
        allocator_lifetime_peak_invariants_passed=True,
        allocator_anchor_invariants_applicable=False,
        allocation_mode="native_demand",
    )
    assert subject._physical_resource_assessment(value) == value["observation"]
    altered = copy.deepcopy(value)
    altered["allocator_anchor_invariants_applicable"] = True
    with pytest.raises(ValueError):
        subject._physical_resource_assessment(altered)


def test_old_manual_stop_does_not_enter_new_automatic_tree():
    decision = subject.validate_safe_recovery(subject.SOURCE_ROOT)
    assert decision["allowed"] is False
    assert "foreign automatic-recovery parent" in decision["reason"]
