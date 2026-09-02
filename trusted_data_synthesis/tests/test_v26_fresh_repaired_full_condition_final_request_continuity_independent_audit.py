# ruff: noqa: E501, SLF001
from __future__ import annotations

import ast
import json
import os
from pathlib import Path

import pytest

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_full_condition_final_request_continuity_independent_audit as audit,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_full_condition_final_request_continuity_independent_audit_models as models,
)

ROOT = Path(__file__).resolve().parents[2]
ATTACHED_REVIEW = Path(
    "/home/zhuxinrui/.codex/attachments/97593421-0247-413b-b42d-d420e48d7c31/pasted-text.txt"
)


def _review_path() -> Path:
    explicit = os.environ.get("V210_EXTERNAL_REVIEW")
    formal = ROOT / "trusted_data_synthesis" / audit.OUTPUT_DIR / "external_review.txt"
    path = Path(explicit) if explicit else (formal if formal.is_file() else ATTACHED_REVIEW)
    if not path.is_file():
        pytest.skip("exact v26.210 external review is unavailable")
    return path


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    output = tmp_path_factory.mktemp("v26-210") / "formal"
    audit.build(
        repository_root=ROOT,
        output_dir=output,
        external_review_path=_review_path(),
        source_identity=("1" * 40, "2" * 40),
    )
    return output


def _load(root: Path, name: str) -> dict[str, object]:
    return json.loads((root / name).read_bytes())


def test_exact_external_authorization() -> None:
    authorization, review, directive = audit._authorization(_review_path())
    assert len(review) == 15_336
    assert directive.decode("utf-8") == audit.OPERATOR_DIRECTIVE
    assert authorization.only_authorized_stage == models.CONSUMED_STAGE
    assert authorization.provider_calls_authorized == 0
    assert not authorization.online_execution_authorized


def test_modified_external_authorization_rejects(tmp_path: Path) -> None:
    changed = tmp_path / "changed.txt"
    changed.write_bytes(_review_path().read_bytes() + b"\n")
    with pytest.raises(audit.V210Error, match="external review bytes differ"):
        audit._authorization(changed)


def test_independent_implementation_does_not_call_candidate_continuity_helper() -> None:
    tree = ast.parse((ROOT / audit.IMPLEMENTATION_FILES[0]).read_text(encoding="utf-8"))
    called = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "_frozen_request_continuity_audit" not in called
    assert "_run_full_condition_control" not in called
    assert "_failure_controls" not in called
    assert "_dynamic_nonreference_branch" not in called


def test_a0_detached_rebuild_is_exact(built: Path) -> None:
    freeze = models.V209PreflightFreeze.model_validate(_load(built, "v209_preflight_freeze.json"))
    detached = models.DetachedRebuildAudit.model_validate(
        _load(built, "detached_rebuild_audit.json")
    )
    assert freeze.documentation_action_final_transport_count_correction == "4/1/5"
    assert detached.actual_byte_equality_count == 21
    assert detached.rebuilt_total_byte_count == 44_916_386
    assert not detached.candidate_continuity_audit_used_as_outcome_oracle


def test_a1_a2_callsite_and_request_continuity_are_exact(built: Path) -> None:
    geometry = models.IndependentCallsiteGeometryAudit.model_validate(
        _load(built, "independent_callsite_geometry_audit.json")
    )
    continuity = models.IndependentRequestContinuityAudit.model_validate(
        _load(built, "independent_request_continuity_audit.json")
    )
    assert (
        geometry.first_action_count,
        geometry.subsequent_action_count,
        geometry.correction_side_branch_count,
        geometry.final_count,
    ) == (192, 288, 120, 192)
    assert not geometry.single_linear_provider_trajectory_claimed
    assert continuity.total_message_match_count == 792
    assert continuity.total_request_match_count == 792
    assert continuity.final_actual_message_byte_equality_count == 192
    assert continuity.final_actual_request_byte_equality_count == 192
    assert continuity.candidate_continuity_helper_call_count == 0


def test_a3_actual_runner_replay_and_dynamic_branch_are_exact(built: Path) -> None:
    replay = models.IndependentExecutableReplayAudit.model_validate(
        _load(built, "independent_executable_replay_audit.json")
    )
    assert replay.main_reference_path_count == 192
    assert replay.correction_side_branch_call_count == 120
    assert replay.qualified_scripted_main_path_count == 192
    assert replay.saved_invocation_record_match_count == 792
    assert (
        replay.dynamic_nonreference_action_dispatch_count,
        replay.dynamic_nonreference_final_dispatch_count,
        replay.dynamic_nonreference_transport_dispatch_count,
    ) == (4, 1, 5)


def test_a4_failures_boundary_and_transition_are_closed(built: Path) -> None:
    failure = models.IndependentFailureBoundaryAudit.model_validate(
        _load(built, "independent_failure_boundary_audit.json")
    )
    gate = models.IndependentAuditGateEvaluation.model_validate(
        _load(built, "independent_audit_gate_evaluation.json")
    )
    decision = models.IndependentAuditDecision.model_validate(
        _load(built, "independent_audit_decision.json")
    )
    transition = models.ProspectiveTransition.model_validate(
        _load(built, "prospective_transition.json")
    )
    assert tuple(item.observed_terminal for item in failure.controls) == (
        "first_response_abi_invalid",
        "first_action_reference_invalid",
        "correction_response_abi_invalid",
        "final_response_abi_invalid",
        "instrument_failure",
    )
    assert failure.provider_calls == failure.credential_lookups == 0
    assert gate.all_gates_passed
    assert decision.decision == models.DECISION
    assert transition.next_stage == models.NEXT_STAGE
    assert not transition.online_execution_authorization_created


def test_complete_directory_rebuild_is_byte_exact(built: Path, tmp_path: Path) -> None:
    rebuilt = tmp_path / "rebuilt"
    audit.build(
        repository_root=ROOT,
        output_dir=rebuilt,
        external_review_path=_review_path(),
        source_identity=("1" * 40, "2" * 40),
    )
    names = tuple(sorted(path.name for path in built.iterdir()))
    assert names == tuple(sorted(path.name for path in rebuilt.iterdir()))
    assert all((built / name).read_bytes() == (rebuilt / name).read_bytes() for name in names)
