from __future__ import annotations

import json
from pathlib import Path

import pytest

from trusted_synthesis.core.evaluation.answer_semantics import (
    compare_answer_by_schema,
    make_answer_semantic_schema,
)
from trusted_synthesis.core.evaluation.trajectory_validity import (
    BaseValidityChecks,
    RecoveryMechanismEvidence,
    make_base_validity_report,
    make_mechanism_qualification_report,
    make_noninterference_artifact_binding,
    make_qualified_validity_report,
    make_validity_eligibility,
    qualify_recovery_mechanism,
)
from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_verifier_vnext_contract_freeze as freeze,
)
from trusted_synthesis.runtime.agent.prospective_qualified_final_response_grammar import (
    compile_qualified_final_response_grammar,
    make_qualified_final_host_envelope,
    parse_qualified_final_response,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
FORMAL_DIR = PACKAGE_ROOT / freeze.OUTPUT_DIR


@pytest.fixture(scope="session")
def rebuilt_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    output_dir = tmp_path_factory.mktemp("v26_148_rebuild")
    freeze.build_verifier_vnext_contract_freeze(
        package_root=PACKAGE_ROOT,
        implementation_root=PACKAGE_ROOT,
        output_dir=output_dir,
    )
    return output_dir


def _load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_v26_148_rebuild_is_byte_identical(rebuilt_dir: Path) -> None:
    formal = tuple(sorted(path for path in FORMAL_DIR.iterdir() if path.is_file()))
    rebuilt = tuple(sorted(path for path in rebuilt_dir.iterdir() if path.is_file()))
    assert tuple(path.name for path in formal) == tuple(path.name for path in rebuilt)
    assert len(formal) == 12
    for path in formal:
        assert path.read_bytes() == (rebuilt_dir / path.name).read_bytes()


def test_v26_148_exact_decimal_and_model_owned_final_language() -> None:
    schema = make_answer_semantic_schema(
        required_result_fields=("difference", "higher_ref"),
        decimal_field_paths=(("difference",),),
    )
    equivalent = compare_answer_by_schema(
        {"difference": 0.35, "higher_ref": "A"},
        {"difference": "0.350", "higher_ref": "A"},
        schema,
    )
    incorrect = compare_answer_by_schema(
        {"difference": "0.351", "higher_ref": "A"},
        {"difference": "0.350", "higher_ref": "A"},
        schema,
    )
    assert equivalent.answer_exact_json_match is False
    assert equivalent.answer_canonical_semantic_match is True
    assert equivalent.reference_identity_match is True
    assert incorrect.answer_canonical_semantic_match is False
    grammar = compile_qualified_final_response_grammar()
    envelope = make_qualified_final_host_envelope(
        grammar=grammar,
        terminal_state_id="state",
        terminal_commit_id="commit",
    )
    parsed = parse_qualified_final_response(
        {
            "answer": {
                "result": {"difference": "0.35", "higher_ref": "A"},
                "citations": [{"evidence_id": "E1"}],
            },
            "rationale_summary": "public rationale",
        },
        grammar=grammar,
        envelope=envelope,
    )
    assert parsed.answer.citations[0].evidence_id == "E1"
    with pytest.raises(ValueError):
        parse_qualified_final_response(
            {
                "answer": {"difference": "0.35", "higher_ref": "A"},
                "rationale_summary": "flat alias",
            },
            grammar=grammar,
            envelope=envelope,
        )


def test_v26_148_validity_eligibility_reports_and_recovery_boundary() -> None:
    eligible = make_validity_eligibility(
        measurement_support_available=True,
        model_endpoint_observed=True,
        instrument_integrity=True,
        privacy_compliant=True,
    )
    support_exit = make_validity_eligibility(
        measurement_support_available=False,
        model_endpoint_observed=False,
        instrument_integrity=True,
        privacy_compliant=True,
    )
    binding = make_noninterference_artifact_binding(
        noninterference_contract_id="contract",
        noninterference_audit_id="audit",
        task_package_id="task",
    )
    checks = BaseValidityChecks(
        action_abi_complete=True,
        program_closed=True,
        operation_lineage_complete=True,
        required_evidence_support_complete=True,
        runtime_selected_support_complete=True,
        model_citation_complete=True,
        terminal_verification_complete=True,
        final_abi_complete=True,
        answer_schema_complete=True,
        answer_canonical_semantic_match=True,
        reference_identity_match=True,
        verification_support_complete=True,
        no_postcompletion_violation=True,
        noninterference_artifact_bound=True,
    )
    base = make_base_validity_report(
        verifier_contract_id="verifier",
        trajectory_id="trajectory",
        eligibility=eligible,
        checks=checks,
        noninterference_binding=binding,
    )
    recovery_events = qualify_recovery_mechanism(
        RecoveryMechanismEvidence(
            typed_failure_observation_index=0,
            revised_action_observation_index=1,
            later_success_observation_index=2,
            failed_action_signature="A",
            revised_action_signature="B",
        )
    )
    mechanism = make_mechanism_qualification_report(
        verifier_contract_id="verifier",
        trajectory_id="trajectory",
        eligibility=eligible,
        mechanism_id="failure_recovery",
        required_event_ids=freeze.MECHANISM_REQUIRED_EVENTS["failure_recovery"],
        observed_event_ids=recovery_events,
    )
    qualified = make_qualified_validity_report(
        verifier_contract_id="verifier",
        trajectory_id="trajectory",
        eligibility=eligible,
        base=base,
        mechanism=mechanism,
    )
    assert base.valid is True
    assert mechanism.success is True
    assert qualified.valid is True
    assert qualified.state_mapping_eligible is True
    null_base = make_base_validity_report(
        verifier_contract_id="verifier",
        trajectory_id="support-exit",
        eligibility=support_exit,
        checks=None,
        noninterference_binding=None,
    )
    null_mechanism = make_mechanism_qualification_report(
        verifier_contract_id="verifier",
        trajectory_id="support-exit",
        eligibility=support_exit,
        mechanism_id="failure_recovery",
        required_event_ids=freeze.MECHANISM_REQUIRED_EVENTS["failure_recovery"],
    )
    null_qualified = make_qualified_validity_report(
        verifier_contract_id="verifier",
        trajectory_id="support-exit",
        eligibility=support_exit,
        base=null_base,
        mechanism=null_mechanism,
    )
    assert null_base.valid is null_mechanism.success is null_qualified.valid is None
    assert null_qualified.state_mapping_eligible is False


def test_v26_148_formal_contract_fixture_destructive_and_transition_are_closed() -> None:
    report = freeze.VerifierVNextFreezeReport.model_validate(_load(FORMAL_DIR / "report.json"))
    verifier = freeze.VerifierVNextContract.model_validate(
        _load(FORMAL_DIR / "verifier_vnext_contract.json")
    )
    fixture = freeze.ContractFixtureAudit.model_validate(
        _load(FORMAL_DIR / "contract_fixture_audit.json")
    )
    destructive = freeze.DestructiveAudit.model_validate(
        _load(FORMAL_DIR / "destructive_audit.json")
    )
    transition = freeze.ProspectiveTransitionContract.model_validate(
        _load(FORMAL_DIR / "prospective_transition_contract.json")
    )
    assert report.fixture_count == fixture.fixture_count == fixture.passed_count == 17
    assert verifier.base_check_ids == tuple(sorted(freeze.BASE_CHECK_IDS))
    assert verifier.qualified_expression == "V_base and Q_mech"
    assert verifier.role_state_mapping_requires_qualified_true is True
    assert verifier.historical_rescoring_or_reclassification_allowed is False
    assert destructive.mutation_count == destructive.rejected_count == 24
    assert transition.next_permitted_stage == freeze.NEXT_STAGE
    assert transition.joint_support_verifier_preflight_authorized is True
    assert transition.provider_calls_authorized is False
    assert transition.new_capability_population_or_identity_materialization_authorized is False
    assert transition.state_mapping_authorized is False
