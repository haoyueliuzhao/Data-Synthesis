from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_full_condition_preflight_independent_audit as audit,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_full_condition_preflight_independent_audit_models as models,
)

ROOT = Path(__file__).resolve().parents[2]


def _audit_path() -> Path:
    explicit = os.environ.get("V207_EXTERNAL_AUDIT")
    path = (
        Path(explicit)
        if explicit
        else ROOT / "trusted_data_synthesis" / audit.OUTPUT_DIR / "external_audit.txt"
    )
    if not path.is_file():
        pytest.skip("v26.207 exact external Audit is not available")
    return path


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    output = tmp_path_factory.mktemp("v26-207") / "formal"
    audit.build(
        repository_root=ROOT,
        output_dir=output,
        external_audit_path=_audit_path(),
        source_identity=("1" * 40, "2" * 40),
    )
    return output


def _load(root: Path, name: str) -> dict[str, object]:
    return json.loads((root / name).read_bytes())


def test_exact_external_authorization() -> None:
    authorization, payload = audit._authorization(_audit_path())
    assert len(payload) == 12_167
    assert authorization.provider_calls_authorized == 0
    assert not authorization.online_execution_authorization_creation_authorized


def test_modified_external_authorization_rejects(tmp_path: Path) -> None:
    changed = tmp_path / "changed.txt"
    changed.write_bytes(_audit_path().read_bytes() + b"\n")
    with pytest.raises(audit.V207Error, match="external Audit bytes differ"):
        audit._authorization(changed)


def test_detached_rebuild_and_parent_chain_pass(built: Path) -> None:
    detached = models.DetachedSourceRebuildAudit.model_validate(
        _load(built, "detached_source_rebuild_audit.json")
    )
    parent = models.IndependentParentReconstructionAudit.model_validate(
        _load(built, "independent_parent_reconstruction_audit.json")
    )
    assert detached.actual_byte_match_count == 17
    assert parent.reconstructed_job_count == 192
    assert parent.predecessor_identity_collision_count == 0


def test_callsite_and_scripted_replay_pass(built: Path) -> None:
    callsites = models.IndependentCallsiteReconstructionAudit.model_validate(
        _load(built, "independent_callsite_reconstruction_audit.json")
    )
    replay = models.IndependentScriptedReplayAudit.model_validate(
        _load(built, "independent_scripted_replay_audit.json")
    )
    assert (callsites.exact_callsite_count, callsites.action_contract_compile_count) == (792, 600)
    assert (replay.exact_job_count, replay.qualified_control_count) == (192, 192)


def test_primary_no_bypass_gate_fails_nonvacuously(built: Path) -> None:
    route = models.SourceRouteNoBypassAudit.model_validate(
        _load(built, "source_route_no_bypass_audit.json")
    )
    assert route.registered_callsite_surface_no_bypass
    assert not route.future_online_route_no_bypass_proved
    assert route.first_unclosed_seam.endswith("transport_route_absent")


def test_gate_decision_and_transition_remain_blocked(built: Path) -> None:
    gates = models.IndependentAuditGateEvaluation.model_validate(
        _load(built, "independent_audit_gate_evaluation.json")
    )
    decision = models.IndependentAuditDecision.model_validate(_load(built, "decision.json"))
    transition = models.BlockedTransition.model_validate(_load(built, "blocked_transition.json"))
    assert (gates.passed_gate_count, gates.failed_gate_count) == (5, 1)
    assert decision.decision == models.BLOCKED_DECISION
    assert transition.next_stage is None
    assert not transition.recommended_candidate_is_authorized


def test_boundary_and_failure_controls_are_closed(built: Path) -> None:
    controls = models.IndependentFailureControlAudit.model_validate(
        _load(built, "independent_failure_control_audit.json")
    )
    boundary = models.EstimandResourceBoundaryAudit.model_validate(
        _load(built, "estimand_resource_boundary_audit.json")
    )
    assert controls.typed_outcome_count == 5
    assert boundary.exact_denominator == 192
    assert boundary.provider_calls == boundary.credential_lookups == 0


def test_complete_directory_rebuild_is_byte_exact(built: Path, tmp_path: Path) -> None:
    rebuilt = tmp_path / "rebuilt"
    audit.build(
        repository_root=ROOT,
        output_dir=rebuilt,
        external_audit_path=_audit_path(),
        source_identity=("1" * 40, "2" * 40),
    )
    names = tuple(sorted(path.name for path in built.iterdir()))
    assert names == tuple(sorted(path.name for path in rebuilt.iterdir()))
    assert all((built / name).read_bytes() == (rebuilt / name).read_bytes() for name in names)
