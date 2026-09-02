# ruff: noqa: E501
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_full_condition_executable_runner_route_closure_preflight as subject,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_fresh_repaired_full_condition_executable_runner_route_closure_preflight_models as models,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
FORMAL_ROOT = REPOSITORY_ROOT / "trusted_data_synthesis" / subject.OUTPUT_DIR
ATTACHED_REVIEW = Path(
    "/home/zhuxinrui/.codex/attachments/736b825a-de5d-44bb-b2d0-c115e8589391/pasted-text.txt"
)


def _review_path() -> Path:
    formal = FORMAL_ROOT / "external_review.txt"
    if formal.is_file():
        return formal
    if ATTACHED_REVIEW.is_file():
        return ATTACHED_REVIEW
    pytest.skip("exact v26.208 review input is unavailable")
    raise AssertionError("unreachable after pytest.skip")


def test_external_review_and_operator_authorization_are_exact() -> None:
    authorization, review, directive = subject._authorization(_review_path())
    assert len(review) == 13_410
    assert models.canonical_sha256(
        authorization.model_dump(mode="json", exclude={"authorization_id"})
    )
    assert directive.decode("utf-8") == subject.OPERATOR_DIRECTIVE
    assert authorization.only_authorized_stage == models.CONSUMED_STAGE
    assert authorization.provider_calls_authorized == 0


def test_modified_external_review_rejects(tmp_path: Path) -> None:
    changed = bytearray(_review_path().read_bytes())
    changed[-1] ^= 1
    path = tmp_path / "changed-review.txt"
    path.write_bytes(changed)
    with pytest.raises(subject.V208Error, match="external review bytes differ"):
        subject._authorization(path)


def test_v207_and_v206_parent_chain_is_frozen() -> None:
    authorization, _, _ = subject._authorization(_review_path())
    parents = subject._predecessor_freeze(
        repository_root=REPOSITORY_ROOT,
        authorization_id=authorization.authorization_id,
    )
    assert parents.freeze.v207_stage_integrity == "VALID_NEGATIVE_INDEPENDENT_AUDIT"
    assert parents.freeze.v207_online_readiness == "FAILED"
    assert len(parents.source_catalog.packages) == 32
    assert len(parents.source_manifest.jobs) == 192
    assert len(parents.v193_evidence.rows) == 792


def test_source_has_one_shared_transport_route() -> None:
    path = REPOSITORY_ROOT / subject.IMPLEMENTATION_FILES[0]
    tree = ast.parse(path.read_text(encoding="utf-8"))
    shared = subject._method(
        tree,
        "ExecutableRepairedFullConditionRunner",
        "_invoke_current_state",
    )
    assert len(subject._call_lines(shared, "_compile_authoritative_messages")) == 1
    assert len(subject._call_lines(shared, "_build_canonical_request_body")) == 1
    assert len(subject._call_lines(shared, "_validate_request_and_certificate")) == 1
    assert len(subject._call_lines(shared, "_pre_transport_receipt")) == 1
    assert len(subject._call_lines(shared, "send")) == 1
    for name in ("invoke_action", "invoke_correction", "invoke_final"):
        wrapper = subject._method(tree, "ExecutableRepairedFullConditionRunner", name)
        assert len(subject._call_lines(wrapper, "_invoke_current_state")) == 1


def test_formal_route_closure_counts() -> None:
    if not FORMAL_ROOT.is_dir():
        pytest.skip("v26.208 formal directory has not been materialized")
    census = models.ExecutableInvocationCensus.model_validate_json(
        (FORMAL_ROOT / "executable_invocation_census.json").read_bytes()
    )
    control = models.FullConditionExecutionControlAudit.model_validate_json(
        (FORMAL_ROOT / "full_condition_execution_control_audit.json").read_bytes()
    )
    no_bypass = models.SourceAndDynamicNoBypassAudit.model_validate_json(
        (FORMAL_ROOT / "source_dynamic_no_bypass_audit.json").read_bytes()
    )
    assert census.dynamic_invocation_count == 792
    assert census.action_and_correction_count == 600
    assert census.final_count == 192
    assert control.terminal_reference_path_count == 192
    assert control.correction_count == 120
    assert no_bypass.gate_passed


def test_formal_failure_and_dynamic_branch_controls() -> None:
    if not FORMAL_ROOT.is_dir():
        pytest.skip("v26.208 formal directory has not been materialized")
    failures = models.TypedFailureControlAudit.model_validate_json(
        (FORMAL_ROOT / "typed_failure_control_audit.json").read_bytes()
    )
    dynamic = models.DynamicNonReferenceBranchAudit.model_validate_json(
        (FORMAL_ROOT / "dynamic_nonreference_branch_audit.json").read_bytes()
    )
    assert tuple(item.observed_terminal for item in failures.controls) == (
        "first_response_abi_invalid",
        "first_action_reference_invalid",
        "correction_response_abi_invalid",
        "final_response_abi_invalid",
        "instrument_failure",
    )
    assert dynamic.next_states_differ
    assert dynamic.second_invocation_matches_nonreference_prefix


def test_formal_gate_and_transition_keep_online_blocked() -> None:
    if not FORMAL_ROOT.is_dir():
        pytest.skip("v26.208 formal directory has not been materialized")
    gate = models.RouteClosureGateAudit.model_validate_json(
        (FORMAL_ROOT / "route_closure_gate_audit.json").read_bytes()
    )
    transition = models.ProspectiveTransition.model_validate_json(
        (FORMAL_ROOT / "prospective_transition.json").read_bytes()
    )
    report = models.RouteClosurePreflightReport.model_validate_json(
        (FORMAL_ROOT / "report.json").read_bytes()
    )
    assert gate.all_gates_passed
    assert transition.next_stage == models.NEXT_STAGE
    assert not transition.online_execution_authorization_issued
    assert report.decision == models.DECISION
    assert report.provider_calls == 0


def test_complete_formal_directory_rebuilds_byte_for_byte(tmp_path: Path) -> None:
    if not FORMAL_ROOT.is_dir():
        pytest.skip("v26.208 formal directory has not been materialized")
    source = models.SourceIdentity.model_validate_json(
        (FORMAL_ROOT / "source_identity.json").read_bytes()
    )
    rebuilt = tmp_path / "rebuilt"
    subject.build(
        repository_root=REPOSITORY_ROOT,
        output_dir=rebuilt,
        external_review_path=FORMAL_ROOT / "external_review.txt",
        source_identity=(source.source_commit, source.source_tree),
    )
    expected = tuple(sorted(path.name for path in FORMAL_ROOT.iterdir() if path.is_file()))
    actual = tuple(sorted(path.name for path in rebuilt.iterdir() if path.is_file()))
    assert actual == expected
    for name in expected:
        assert (rebuilt / name).read_bytes() == (FORMAL_ROOT / name).read_bytes()
