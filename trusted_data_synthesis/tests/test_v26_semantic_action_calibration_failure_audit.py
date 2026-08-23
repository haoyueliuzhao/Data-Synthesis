from __future__ import annotations

import json
from pathlib import Path

from trusted_synthesis.experiments.vtdo_experiment import (
    phase1_v26_semantic_action_calibration_failure_audit as audit,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_ROOT = Path("/home/zhuxinrui/datatmp/projects/Data-Synthesis/trusted_data_synthesis")
EVIDENCE_ROOT = CANONICAL_ROOT if CANONICAL_ROOT.is_dir() else PACKAGE_ROOT
EXECUTION_DIR = EVIDENCE_ROOT / audit.EXECUTION_DIR


def _build(output_dir: Path) -> audit.FailureAuditReport:
    return audit.build(
        package_root=EVIDENCE_ROOT,
        implementation_root=PACKAGE_ROOT,
        execution_dir=EXECUTION_DIR,
        output_dir=output_dir,
    )


def test_v26_121_dual_build_replays_failed_execution_byte_for_byte(
    tmp_path: Path,
) -> None:
    formal_dir = tmp_path / "formal"
    independent_dir = tmp_path / "independent"
    formal = _build(formal_dir)
    independent = _build(independent_dir)
    assert formal == independent
    for path in formal_dir.iterdir():
        assert path.read_bytes() == (independent_dir / path.name).read_bytes()

    lineage = json.loads((formal_dir / "failed_execution_lineage_audit.json").read_text())
    provider = json.loads((formal_dir / "provider_telemetry_audit.json").read_text())
    assert lineage["manifest_job_count"] == 32
    assert lineage["checkpoint_job_count"] == 5
    assert lineage["raw_execution_count"] == 31
    assert lineage["provider_orphan_job_count"] == 1
    assert lineage["exposed_job_count"] == 32
    assert lineage["persisted_provider_artifact_count"] == 256
    assert lineage["raw_bound_provider_artifact_count"] == 250
    assert lineage["orphan_provider_artifact_count"] == 6
    assert lineage["operator_observed_provider_invocation_lower_bound"] == 257
    assert provider["http_success_artifact_count"] == 225
    assert provider["http_400_artifact_count"] == 31
    assert provider["exact_four_field_semantic_payload_count"] == 194
    assert provider["exact_prompt_visible_final_payload_count"] == 31
    assert provider["provider_total_tokens_lower_bound"] == 1_068_881
    assert provider["private_reasoning_content_persisted_count"] == 0
    assert formal.completed_execution_report_materialized is False
    assert formal.exact_empirical_job_denominator_available is False
    assert formal.provider_calls == formal.stage_two_provider_calls == 0


def test_v26_121_localizes_action_final_and_privacy_boundaries(tmp_path: Path) -> None:
    output_dir = tmp_path / "audit"
    report = _build(output_dir)
    outcome = json.loads((output_dir / "public_action_outcome_audit.json").read_text())
    final = json.loads((output_dir / "final_response_interface_audit.json").read_text())
    privacy = json.loads((output_dir / "privacy_persistence_failure_audit.json").read_text())
    transition = json.loads((output_dir / "prospective_transition_contract.json").read_text())

    assert outcome["semantic_choice_count"] == 188
    assert outcome["visible_action_id_match_count"] == 187
    assert outcome["reversible_commit_count"] == 186
    assert outcome["program_closed_job_count"] == 31
    assert outcome["successful_terminal_verification_count"] == 31
    assert outcome["first_action_id_legal_job_count"] == 30
    assert outcome["semantic_rejection_count"] == 2
    assert outcome["semantic_recovery_job_count"] == 2
    assert outcome["recovery_commit_count"] == 2
    assert outcome["legal_no_progress_choice_count"] == 17
    assert outcome["ordinary_replan_count"] == 17
    assert outcome["singleton_choice_count"] == 61
    assert outcome["multi_candidate_choice_count"] == 127
    assert outcome["selected_reference_count"] == 116
    assert outcome["selected_nonreference_count"] == 71
    assert outcome["selected_invisible_action_count"] == 1
    assert outcome["final_answer_count"] == 0
    assert outcome["independent_validity_count"] == 0

    assert final["model_visible_primary_exact_field_set"] == [
        "answer",
        "rationale_summary",
    ]
    assert final["parser_exact_field_set"] == ["answer", "protocol", "stage"]
    assert final["observed_exact_model_visible_primary_payload_count"] == 31
    assert final["observed_primary_parser_rejection_count"] == 31
    assert final["final_rescue_prompt_json_lexical_cue_count"] == 0
    assert final["final_rescue_http_400_count"] == 31
    assert final["provider_http_error_body_absence_prevents_causal_exclusivity"]

    assert privacy["persisted_exact_four_field_payload_count"] == 6
    assert privacy["operator_observed_unjournaled_parsed_response_count"] == 1
    assert privacy["unjournaled_response_telemetry_retained"] is False
    assert privacy["retry_blocked_by_six_orphan_provider_artifacts"]
    assert privacy["private_reasoning_persistence_remains_forbidden"]
    assert transition["all_v26_120_job_identities_retired"]
    assert transition["provider_calls_authorized"] is False
    assert transition["final_response_grammar_must_be_shared_by_prompt_parser_primary_and_rescue"]
    assert report.next_permitted_stage == audit.NEXT_STAGE
