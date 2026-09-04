from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

STAGE: Final = (
    "finance_qa_vnext_reasoning_bearing_scientific_object_and_contract_freeze_"
    "independent_audit_only"
)
DECISION: Final = (
    "finance_qa_vnext_reasoning_bearing_scientific_object_and_contract_freeze_"
    "independently_confirmed"
)
PROSPECTIVE_NEXT_STAGE: Final = (
    "finance_qa_vnext_reasoning_bearing_fixed_fixture_constructibility_preflight_only"
)

EXTERNAL_REVIEW_SHA256: Final = "c322942a7d67decc705d133850a0f7f53ccc7dae82185a45654d43183cd790e4"
EXTERNAL_REVIEW_BYTE_COUNT: Final = 24_106
OPERATOR_DIRECTIVE: Final = "参照审计继续实验修订"
OPERATOR_DIRECTIVE_SHA256: Final = (
    "d7f0a7b9c625edb3ec4d53a21418dd0b11ec7291a0ae934b98364ea651f9d3ca"
)
OPERATOR_DIRECTIVE_BYTE_COUNT: Final = 30

CANDIDATE_DIRECTORY: Final = (
    "trusted_data_synthesis/artifacts/qa_reasoning_contract_freeze/"
    "finance_qa_vnext_reasoning_bearing_scientific_object_and_contract_freeze_"
    "v1_20260905"
)
CANDIDATE_SOURCE_COMMIT: Final = "0a908909f27b75b41085062e2673abcfaa29dda7"
CANDIDATE_SOURCE_TREE: Final = "a56d9e374cc8d15b1e49e78a3c953362db61ca88"
CANDIDATE_FILE_COUNT: Final = 30
CANDIDATE_TOTAL_BYTES: Final = 77_840
CANDIDATE_MEMBER_COUNT: Final = 29
CANDIDATE_MEMBER_BYTES: Final = 73_415
CANDIDATE_MANIFEST_BYTE_COUNT: Final = 4_425
CANDIDATE_MANIFEST_SHA256: Final = (
    "779c4c13d2addc943c919d181b86edf5f0ec2753e830b14ab7cd2bb3828df6be"
)
CANDIDATE_MANIFEST_ID: Final = (
    "finance_qa_reasoning_contract_artifact_manifest:"
    "cab74a9bdf3cbe762145c41cdafab89dc59df02b7d9a42fe4230295658324793"
)
CANDIDATE_ARTIFACT_ROOT: Final = (
    "finance_qa_reasoning_contract_artifact_root:"
    "d805427b5212edd40833a6c58ad835d3280d812dedf279c53360f252c98e6230"
)
CANDIDATE_AUTHORIZATION_ID: Final = (
    "finance_qa_reasoning_contract_freeze_authorization:"
    "696de35e6ecd6a7200051e3a0ebb8e19ea2dc81b26cb88f227d4d2ddc21912b3"
)
CANDIDATE_PREDECESSOR_FREEZE_ID: Final = (
    "finance_qa_reasoning_contract_predecessor_freeze:"
    "dbff88352da9ff7cc72d62b635a819e03a384ae28f46fc6ce12971b9d71a6790"
)
CANDIDATE_SCOPE_CLARIFICATION_ID: Final = (
    "finance_qa_archive_negative_result_scope_clarification:"
    "07b2209fc833e6714caf353b5526e5937b0bff33e3f34d6a6d1ae24637633478"
)
CANDIDATE_SOURCE_BINDING_ID: Final = (
    "finance_qa_reasoning_contract_source_binding:"
    "9bfe21421cc18584482c62d6a611eb99c12aa713640bf00e881a630e5dbd6baa"
)
CANDIDATE_CONFORMANCE_AUDIT_ID: Final = (
    "finance_qa_reasoning_contract_conformance_audit:"
    "a57695a88c0f4a88302422bb22ab4760595d7ead49e989cacd2a2327f51a9ade"
)
CANDIDATE_NEGATIVE_AUDIT_ID: Final = (
    "finance_qa_reasoning_contract_negative_audit:"
    "c6e87f0a211dc84a43fc4f1c0615becbf5aa02eb8b5310f14cf95720832155a7"
)
CANDIDATE_SCOPE_AUDIT_ID: Final = (
    "finance_qa_reasoning_contract_scope_audit:"
    "4ca1033dc8accf36f0aae0833d8380347f0519f31cf0a0995badcbc6ecc8f0b9"
)
CANDIDATE_GATE_ID: Final = (
    "finance_qa_reasoning_contract_gate:"
    "b63f8cb0c7a16df4144b8a17ef2efc95c951f002d94cc02f473ba2b268eb4e84"
)
CANDIDATE_DECISION_ID: Final = (
    "finance_qa_reasoning_contract_decision:"
    "773234d9bf52df79b38362a620a27c2c1b337a85521a92df5c50787fee38141f"
)
CANDIDATE_TRANSITION_ID: Final = (
    "finance_qa_reasoning_contract_transition:"
    "5ce5224b79071c6da6d7dc61caf266eed746159711a8cbf1e051619dbf936fb2"
)
CANDIDATE_REPORT_ID: Final = (
    "finance_qa_reasoning_contract_report:"
    "90958782d99c16c1223ac979bc22a66d8a5ad3c40762b2fed35b855fe331193d"
)
CANDIDATE_TARGET_CONTRACT_ID: Final = (
    "target_evidence_authority_contract:"
    "623f90e7e093ddb5d70b0beaa2fe21c3c532cdecc79fb4a42a1b230c599d3ba0"
)
CANDIDATE_COVERAGE_MATRIX_ID: Final = (
    "qa_task_and_reasoning_coverage_matrix:"
    "d71c5db703a245a2463141a58ae0b379615ceff30c15cc2d2d89a43b70aeb169"
)

PREDECESSOR_DIRECTORY: Final = (
    "trusted_data_synthesis/artifacts/qa_semantic_depth_three_archive_grounding/"
    "qa_semantic_operation_depth_three_plus_archive_grounded_parameter_space_"
    "constructibility_preflight_v1_20260904"
)
PREDECESSOR_MANIFEST_ID: Final = (
    "qa_archive_parameter_space_artifact_manifest:"
    "29dbf80f462d7dbf079df99e77d44dc5739b2a9ece8525356b43dc9ddc0f63b7"
)
PREDECESSOR_ROOT_ID: Final = (
    "qa_archive_parameter_space_artifact_root:"
    "b24d054bbf6cd5275675636f7a3f69fac127b2ab1a42483911c384c1cae60f98"
)
PREDECESSOR_GATE_ID: Final = (
    "qa_archive_parameter_space_gate:"
    "3ceda0d6f3c8c003fb0aaf0413088ad53453cb3e13b2ad148275752c93c42a17"
)
PREDECESSOR_DECISION_ID: Final = (
    "qa_archive_parameter_space_decision:"
    "71454455586f36d36a1bd6edfddd2ce2cd00cf078caa45d92a382ec14b143ab6"
)

CANDIDATE_SOURCE_PATHS: Final = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "qa_reasoning_contract_freeze/__init__.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "qa_reasoning_contract_freeze/models.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "qa_reasoning_contract_freeze/contracts.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "qa_reasoning_contract_freeze/preflight.py",
)
AUDIT_SOURCE_PATHS: Final = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "qa_reasoning_contract_freeze_independent_audit/__init__.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "qa_reasoning_contract_freeze_independent_audit/models.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "qa_reasoning_contract_freeze_independent_audit/audit.py",
)

CONTRACT_NAMES: Final = (
    "AnswerOracleProgramBindingContract",
    "CriticalDecisionGraphContract",
    "PublicReasoningStateContract",
    "ReasoningActionEnvelopeContract",
    "ObservationUpdateContract",
    "ReasoningTrajectoryContract",
    "ReasoningValidityContract",
    "TargetEvidenceAuthorityContract",
    "DepthMetricContract",
    "QATaskAndReasoningCoverageMatrixContract",
)
OBJECT_NAMES: Final = (
    "answer_oracle_binding",
    "critical_decision_graph",
    "initial_state",
    "reasoning_action",
    "action_execution",
    "observation",
    "observation_update",
    "next_state",
    "reasoning_trajectory",
    "answer_validity",
    "trajectory_validity",
    "qualification",
    "depth_metrics",
)
ATTACK_NAMES: Final = (
    "post_action_reasoning_backfill",
    "generic_rationale_without_evidence",
    "cross_state_reasoning",
    "reasoning_action_mismatch",
    "future_evidence_reference",
    "observation_claim_update_mismatch",
    "actual_margin_relabelled_as_target",
    "correct_final_with_missing_decision_obligation",
    "valid_reasoning_with_invalid_final_or_citation",
    "paraphrase_only_trajectories_as_distinct_quotient_states",
)
ATTACK_STAGES: Final = (
    "reasoning.preaction_commit",
    "model.validation",
    "reasoning.state_binding",
    "reasoning.action_consistency",
    "reasoning.visible_refs",
    "model.validation",
    "target.modality",
    "reasoning.critical_coverage",
    "reasoning.qualification",
    "reasoning.quotient_state",
)
GATE_NAMES: Final = (
    "A0_EXACT_AUTHORITY_AND_SCOPE_FREEZE",
    "A1_DETACHED_EXACT_SOURCE_AND_DIRECTORY_REPRODUCIBILITY",
    "A2_TEN_CONTRACT_DESCRIPTORS_INDEPENDENTLY_RECONSTRUCTED",
    "A3_THIRTEEN_CONFORMANCE_OBJECTS_INDEPENDENTLY_RECONSTRUCTED",
    "A4_EXACT_PARENT_ORDER_AND_CROSS_OBJECT_RELATIONS",
    "A5_VALIDITY_TARGET_DEPTH_AND_COVERAGE_INDEPENDENT_DERIVATION",
    "A6_TEN_ATTACKS_INDEPENDENTLY_REJECT",
    "A7_CANDIDATE_SELF_AUDIT_NON_ORACLE_AND_ZERO_EXTERNAL_SCOPE",
)


@dataclass(frozen=True)
class Products:
    authorization: dict[str, Any]
    external_review_bytes: bytes
    operator_directive_bytes: bytes
    candidate_freeze: dict[str, Any]
    detached_rebuild: dict[str, Any]
    audit_source_binding: dict[str, Any]
    contract_descriptors: tuple[dict[str, Any], ...]
    contract_reconstruction_audit: dict[str, Any]
    scientific_objects: dict[str, dict[str, Any]]
    object_reconstruction_audit: dict[str, Any]
    parent_relation_audit: dict[str, Any]
    semantic_derivation_audit: dict[str, Any]
    negative_control_audit: dict[str, Any]
    candidate_final_comparison_audit: dict[str, Any]
    scope_audit: dict[str, Any]
    gate: dict[str, Any]
    decision: dict[str, Any]
    transition: dict[str, Any]
    report: dict[str, Any]
