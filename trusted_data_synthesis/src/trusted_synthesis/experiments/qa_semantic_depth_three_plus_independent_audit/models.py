from __future__ import annotations

from typing import Any, Final

from pydantic import BaseModel, ConfigDict

STAGE: Final = (
    "qa_semantic_operation_depth_three_plus_constructibility_and_coverage_"
    "preflight_independent_audit_only"
)
DECISION: Final = (
    "qa_semantic_operation_depth_three_plus_constructibility_and_two_topology_"
    "coverage_preflight_independently_confirmed"
)
PROSPECTIVE_NEXT_STAGE: Final = (
    "qa_semantic_operation_depth_three_plus_registered_catalog_integration_preflight_only"
)

EXTERNAL_REVIEW_SHA256: Final = "1c0c189157b5d1cbcbbbf4801c55053520558d789ce9bc981c20d58e0ab7d3c8"
EXTERNAL_REVIEW_BYTE_COUNT: Final = 14_928
OPERATOR_DIRECTIVE: Final = "参照审计执行QA链路后续实验"
OPERATOR_DIRECTIVE_SHA256: Final = (
    "c992e9fe84c3c7a54aff22c7c0ea0229c0d8001943cf5abb0c37cf24bafcd373"
)
OPERATOR_DIRECTIVE_BYTE_COUNT: Final = 38

CANDIDATE_DIRECTORY: Final = (
    "trusted_data_synthesis/artifacts/qa_semantic_depth_three_plus/"
    "qa_semantic_operation_depth_three_plus_constructibility_and_coverage_"
    "preflight_v2_20260904"
)
CANDIDATE_MODULE: Final = "trusted_synthesis.experiments.qa_semantic_depth_three_plus.preflight"
CANDIDATE_SOURCE_COMMIT: Final = "2267de7f59f1ee5ea36377f016c82ae8829697cf"
CANDIDATE_SOURCE_TREE: Final = "b926794c0d1f196156603240c11fcf0b4e6618b8"
CANDIDATE_FILE_COUNT: Final = 21
CANDIDATE_TOTAL_BYTES: Final = 162_669
CANDIDATE_MEMBER_COUNT: Final = 20
CANDIDATE_MEMBER_BYTES: Final = 159_547
CANDIDATE_MANIFEST_BYTES: Final = 3_122
CANDIDATE_MANIFEST_SHA256: Final = (
    "7371a60a5955df24d5142a2d795f5d20260f928f7f20eaf0aa7ab3e929be34fe"
)
CANDIDATE_MANIFEST_ID: Final = (
    "qa_semantic_depth_three_plus_artifact_manifest:"
    "6a3e8126d2052cf0db8f39f0bba8bde65b5a5627222b864ad648f960514d36b0"
)
CANDIDATE_ARTIFACT_ROOT: Final = (
    "qa_semantic_depth_three_plus_artifact_root:"
    "7c7593cf2547588bebbff188e5df4c0816155f6ac1a13c9403cfcfc02f9b77ee"
)
CANDIDATE_AUTHORIZATION_ID: Final = (
    "qa_semantic_depth_three_plus_authorization:"
    "b32091a966ed7988cc8052bfb31c6d505357601f79363665fdacdadb39edde48"
)
CANDIDATE_SOURCE_BINDING_ID: Final = (
    "qa_semantic_depth_three_plus_source_binding:"
    "607405fd772bd0faad8ed6db9b5dcdd290c512681bbba304362d903f5e43e590"
)
CANDIDATE_REGISTRY_BINDING_ID: Final = (
    "qa_semantic_depth_three_plus_registry_binding:"
    "dd2f326284eee0540ab06f74bba098477fd5e2a5905c07dfc950b0869c0a1e01"
)
CANDIDATE_COVERAGE_AUDIT_ID: Final = (
    "qa_semantic_depth_three_plus_coverage_audit:"
    "7f182138bc361310abeb4f514d3e3f110d4812778b2545c871f5bb619219a7ad"
)
CANDIDATE_NEGATIVE_AUDIT_ID: Final = (
    "qa_semantic_depth_three_plus_negative_audit:"
    "5547ba2585819d27ebeef5a463505fbbb9e98af6aa2e7518b151dde5b5860eb9"
)
CANDIDATE_GATE_ID: Final = (
    "qa_semantic_depth_three_plus_gate:"
    "1b04b36efc7f7488734414bc3ee72f9d47f7d75333c49b4a3d49fd9e94cc6289"
)
CANDIDATE_DECISION_ID: Final = (
    "qa_semantic_depth_three_plus_decision:"
    "c9ff6528cc4ac7a6fcb6279d0a741dffbeac8b4a6fc3f1936cc073566f3dccff"
)
CANDIDATE_TRANSITION_ID: Final = (
    "qa_semantic_depth_three_plus_transition:"
    "227a42807358b765fa3a9e00e575a9e3398b63e398b8dd63c9ad50f1f19a5dc4"
)
CANDIDATE_REPORT_ID: Final = (
    "qa_semantic_depth_three_plus_report:"
    "ad6f07ab2d45e3ecc621c387596a091710308bcaef8bee4170d6a120e44521bc"
)
REGISTRY_MANIFEST_SHA256: Final = "36cd46cf8a4b714c22dce965ec0ff8043a07d9c43695ab4432fe318749824bb2"
SOURCE_PATHS: Final = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "qa_semantic_depth_three_plus/__init__.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "qa_semantic_depth_three_plus/models.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "qa_semantic_depth_three_plus/operations.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "qa_semantic_depth_three_plus/patterns.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "qa_semantic_depth_three_plus/preflight.py",
)
AUDIT_SOURCE_PATHS: Final = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "qa_semantic_depth_three_plus_independent_audit/__init__.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "qa_semantic_depth_three_plus_independent_audit/models.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "qa_semantic_depth_three_plus_independent_audit/audit.py",
)
CASE_IDS: Final = ("branch_merge_growth_gap", "serial_margin_target_gap")
TASK_TYPES: Final = ("derived_growth_absolute_spread", "registered_margin_target_gap")
ATTACK_NAMES: Final = (
    "serial_irrelevant_lookup_inflation",
    "serial_semantic_scale_bypass",
    "branch_merge_absolute_bypass",
    "branch_to_serial_topology_substitution",
    "branch_cross_metric_evidence_substitution",
    "fully_rehashed_wrong_answer_and_citation",
    "operation_role_laundering",
)
ATTACK_STAGES: Final = (
    "output_dependency_closure",
    "exact_source_program_admission",
    "exact_source_program_admission",
    "exact_source_program_admission",
    "pattern_source_admission",
    "verifier_evaluator_admission",
    "authoritative_registry_metric_admission",
)
GATE_NAMES: Final = (
    "A0_EXACT_EXTERNAL_SCOPE_AND_CANDIDATE_FREEZE",
    "A1_DETACHED_EXACT_DIRECTORY_REBUILD",
    "A2_INDEPENDENT_GIT_SOURCE_AND_REGISTRY_AUTHORITY",
    "A3_INDEPENDENT_PATTERN_PROGRAM_RECONSTRUCTION",
    "A4_INDEPENDENT_FOURTEEN_NODE_EXECUTION_AND_VERIFICATION",
    "A5_INDEPENDENT_DEPTH_AND_TOPOLOGY_DERIVATION",
    "A6_SEVEN_DIRECT_ATTACKS_REJECT",
    "A7_ZERO_EXTERNAL_EXECUTION_SCOPE",
)


class AuditProducts(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    authorization: dict[str, Any]
    external_review_bytes: bytes
    operator_directive_bytes: bytes
    candidate_freeze: dict[str, Any]
    detached_rebuild: dict[str, Any]
    source_authority: dict[str, Any]
    registry_authority: dict[str, Any]
    case_rows: tuple[dict[str, Any], ...]
    execution_audit: dict[str, Any]
    depth_topology_audit: dict[str, Any]
    negative_audit: dict[str, Any]
    scope_audit: dict[str, Any]
    gate: dict[str, Any]
    decision: dict[str, Any]
    transition: dict[str, Any]
    report: dict[str, Any]
