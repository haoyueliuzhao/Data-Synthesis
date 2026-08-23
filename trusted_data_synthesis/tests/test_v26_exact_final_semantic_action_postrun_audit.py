from __future__ import annotations

from collections import Counter
from pathlib import Path

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_exact_final_semantic_action_postrun_audit as audit,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_ROOT = Path("/home/zhuxinrui/datatmp/projects/Data-Synthesis/trusted_data_synthesis")
EVIDENCE_ROOT = CANONICAL_ROOT if CANONICAL_ROOT.is_dir() else PACKAGE_ROOT
EXECUTION_DIR = EVIDENCE_ROOT / audit.EXECUTION_DIR


def test_v26_125_independently_rebuilds_failed_calls_and_final_outcomes(
    tmp_path: Path,
) -> None:
    formal_dir = tmp_path / "formal"
    independent_dir = tmp_path / "independent"
    formal = audit.build(
        package_root=EVIDENCE_ROOT,
        implementation_root=PACKAGE_ROOT,
        execution_dir=EXECUTION_DIR,
        output_dir=formal_dir,
    )
    independent = audit.build(
        package_root=EVIDENCE_ROOT,
        implementation_root=PACKAGE_ROOT,
        execution_dir=EXECUTION_DIR,
        output_dir=independent_dir,
    )

    assert formal == independent
    assert formal.execution_report_id == audit.EXPECTED_EXECUTION_REPORT_ID
    assert formal.complete_raw_count == 32
    assert formal.provider_call_count == 179
    assert formal.complete_model_outcome_count == 22
    assert formal.instrument_failure_count == 10
    assert formal.independently_valid_count == 11
    assert not formal.exact_endpoint_denominator_complete
    assert formal.provider_calls == formal.stage_two_provider_calls == 0
    assert formal.next_permitted_stage == audit.NEXT_STAGE

    lineage = audit.RawLineageReaudit.model_validate(
        audit._load(formal_dir / "raw_lineage_reaudit.json")
    )
    assert lineage.complete_provider_pair_count == 179
    assert lineage.envelope_only_orphan_count == 0
    assert lineage.projection_only_orphan_count == 0
    assert lineage.private_reasoning_payload_count == 0
    assert lineage.completed_verification_match_count == 17

    provider = audit.ProviderFailureAudit.model_validate(
        audit._load(formal_dir / "provider_failure_audit.json")
    )
    assert provider.admitted_complete_success_count == 169
    assert Counter(item.error_type for item in provider.failed_call_recovery_candidates) == {
        "IncompleteRead": 8,
        "URLError": 2,
    }
    assert provider.failed_call_recovery_candidate_count == 10
    assert provider.privacy_rejected_count == 0

    outcome = audit.FinalOutcomeAudit.model_validate(
        audit._load(formal_dir / "final_outcome_audit.json")
    )
    assert outcome.program_closed_model_outcome_count == 22
    assert outcome.final_commit_model_outcome_count == 22
    assert outcome.final_validated_public_payload_count == 27
    assert outcome.exact_two_top_level_field_count == 27
    assert outcome.answer_object_count == 17
    assert outcome.answer_string_count == 10
    assert outcome.final_grammar_failure_job_count == 5
    assert outcome.final_answer_emitted_count == 17
    assert outcome.independently_valid_answer_count == 11
    assert outcome.answer_projection_failure_count == 3
    assert outcome.mechanism_failure_count == 3
    assert outcome.citation_failure_count == 0
    assert outcome.evidence_support_failure_count == 0

    transition = audit.ProspectiveTransitionContract.model_validate(
        audit._load(formal_dir / "prospective_transition_contract.json")
    )
    assert transition.exact_recovery_candidate_count == 10
    assert transition.preserved_model_outcome_job_count == 22
    assert not transition.provider_calls_authorized

    formal_files = tuple(sorted(path.name for path in formal_dir.iterdir()))
    independent_files = tuple(sorted(path.name for path in independent_dir.iterdir()))
    assert formal_files == independent_files
    assert all(
        (formal_dir / name).read_bytes() == (independent_dir / name).read_bytes()
        for name in formal_files
    )
