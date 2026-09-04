from __future__ import annotations

from typing import Any, Final

from pydantic import BaseModel, ConfigDict

STAGE: Final = (
    "qa_semantic_operation_depth_three_plus_registered_catalog_integration_"
    "preflight_independent_audit_only"
)
DECISION: Final = (
    "qa_semantic_operation_depth_three_plus_registered_catalog_integration_"
    "preflight_independently_confirmed"
)
PROSPECTIVE_NEXT_STAGE: Final = (
    "qa_semantic_operation_depth_three_plus_archive_grounded_parameter_space_"
    "constructibility_preflight_only"
)

EXTERNAL_REVIEW_SHA256: Final = "856cafe7a458b1b9784fbe308a75534ec98f0592085871e0e7ccb3dbfd91b696"
EXTERNAL_REVIEW_BYTE_COUNT: Final = 14_751
OPERATOR_DIRECTIVE: Final = "参照审计继续QA链路实验修订"
OPERATOR_DIRECTIVE_SHA256: Final = (
    "dddd96463f4c9ad84ac7f2b8ea4ff99b3f86e5cd55489535dd6c826b888674dc"
)
OPERATOR_DIRECTIVE_BYTE_COUNT: Final = 38

CANDIDATE_DIRECTORY: Final = (
    "trusted_data_synthesis/artifacts/qa_semantic_depth_three_catalog_integration/"
    "qa_semantic_operation_depth_three_plus_registered_catalog_integration_"
    "preflight_v1_20260904"
)
CANDIDATE_MODULE: Final = (
    "trusted_synthesis.experiments.qa_semantic_depth_three_catalog_integration.preflight"
)
CANDIDATE_SOURCE_COMMIT: Final = "13877e14c9e5050eb77f0895c73a686b389a6aaf"
CANDIDATE_SOURCE_TREE: Final = "3067b7aa72d9895f89513c8e68a9a55dd6fbde71"
CANDIDATE_FILE_COUNT: Final = 23
CANDIDATE_TOTAL_BYTES: Final = 183_833
CANDIDATE_MEMBER_COUNT: Final = 22
CANDIDATE_MEMBER_BYTES: Final = 180_424
CANDIDATE_MANIFEST_BYTES: Final = 3_409
CANDIDATE_MANIFEST_SHA256: Final = (
    "821a4e6874aa4205ad391b744e45f4b36ebc58ff26d05fc797794a5a0f803caa"
)
CANDIDATE_MANIFEST_ID: Final = (
    "qa_registered_catalog_artifact_manifest:"
    "2c91dbaaf0007a5542bc5c6297657f6bd11763f9eb79d1f355a24869761824f1"
)
CANDIDATE_ARTIFACT_ROOT: Final = (
    "qa_registered_catalog_artifact_root:"
    "0f16712cb459e29858d2899a355ddfd23bf89dc80f096ad25a8adb71614aa627"
)
CANDIDATE_AUTHORIZATION_ID: Final = (
    "qa_registered_catalog_integration_authorization:"
    "b79862fc59125309b0985d5b34d3c81ed1852d8beb651dedc06595ce289d8b9b"
)
CANDIDATE_PREDECESSOR_FREEZE_ID: Final = (
    "qa_registered_catalog_predecessor_freeze:"
    "88885b1347ee0cc450d31bd537364968685806881d5aad9c9f86652ea6ebbc88"
)
CANDIDATE_SOURCE_BINDING_ID: Final = (
    "qa_registered_catalog_source_binding:"
    "8ce793e70b42ee686fcc930d810a957b3cdea94c330c3425fef3ff4cf0616303"
)
CANDIDATE_HISTORICAL_SNAPSHOT_ID: Final = (
    "finance_qa_historical_catalog_snapshot:"
    "20aa36f41a52df846f41adddd337670ddf00144e40b0710eb873be2f61add4b0"
)
CANDIDATE_CATALOG_ID: Final = (
    "finance_qa_registered_catalog:4761c0dace3f2f87169c6f10db76043fc250ff03f584e7466e21b10e13b63268"
)
CANDIDATE_INTEGRATION_AUDIT_ID: Final = (
    "qa_registered_catalog_integration_audit:"
    "c8bd00534c05eb6686fd8be23af36736b57be6c08ca40a8811ef2941f52af0ec"
)
CANDIDATE_NEGATIVE_AUDIT_ID: Final = (
    "qa_registered_catalog_negative_audit:"
    "7b917313373f5a87da4b70fd175c6a46bc38dca179979a773741af55130a2062"
)
CANDIDATE_GATE_ID: Final = (
    "qa_registered_catalog_gate:2f1fa33d5768b96ff0dce184c90b5ca80d29e7700dd73761eca0ba369b6013d3"
)
CANDIDATE_DECISION_ID: Final = (
    "qa_registered_catalog_decision:"
    "d3fd3c551f0a4c16734058b3c979848a6402d3816b0fe4484f1673695013b548"
)
CANDIDATE_TRANSITION_ID: Final = (
    "qa_registered_catalog_transition:"
    "d160afc4bca85e4a38230be4a444cce4ab4eab108d45dae212a5598b47a4d635"
)
CANDIDATE_REPORT_ID: Final = (
    "qa_registered_catalog_report:86f1608d4f0f76da1a47feba1988d7413678a657afe98e2d4b3d7b2aab4b980f"
)
CANDIDATE_SOURCE_PATHS: Final = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "qa_semantic_depth_three_catalog_integration/__init__.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "qa_semantic_depth_three_catalog_integration/models.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "qa_semantic_depth_three_catalog_integration/catalog.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "qa_semantic_depth_three_catalog_integration/preflight.py",
)
AUDIT_SOURCE_PATHS: Final = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "qa_semantic_depth_three_catalog_integration_independent_audit/__init__.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "qa_semantic_depth_three_catalog_integration_independent_audit/models.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "qa_semantic_depth_three_catalog_integration_independent_audit/audit.py",
)
HISTORICAL_TASK_TYPES: Final = (
    "comparison",
    "derived_growth_comparison",
    "fact_retrieval",
    "registered_cross_metric_comparison",
    "registered_ratio",
    "temporal_absolute_change",
    "temporal_average",
    "temporal_growth",
)
EXTENSION_TASK_TYPES: Final = (
    "derived_growth_absolute_spread",
    "registered_margin_target_gap",
)
EXTENSION_OPERATION_IDS: Final = (
    "absolute_percentage_point_gap",
    "scale_ratio_percent",
    "signed_percentage_point_gap",
)
CASE_IDS: Final = ("branch_merge_growth_gap", "serial_margin_target_gap")
ATTACK_NAMES: Final = (
    "task_type_alias",
    "missing_task_registration",
    "duplicate_task_registration",
    "missing_operation_registration",
    "duplicate_operation_registration",
    "wrong_operation_role",
    "catalog_bypass_without_resolution_receipt",
    "crossed_pattern_registration",
)
ATTACK_STAGES: Final = (
    "catalog.task_lookup",
    "catalog.extension_task_domain",
    "catalog.task_uniqueness",
    "catalog.extension_operation_domain",
    "catalog.operation_uniqueness",
    "catalog.operation_role",
    "catalog.resolution_receipt",
    "catalog.pattern_relation",
)
GATE_NAMES: Final = (
    "A0_EXACT_EXTERNAL_SCOPE_AND_CANDIDATE_FREEZE",
    "A1_DETACHED_EXACT_DIRECTORY_REBUILD",
    "A2_INDEPENDENT_SOURCE_AND_HISTORICAL_CATALOG_AUTHORITY",
    "A3_INDEPENDENT_FRESH_CATALOG_AND_RESOLUTION",
    "A4_INDEPENDENT_BINDING_PROGRAM_PACKAGE_RECONSTRUCTION",
    "A5_INDEPENDENT_FOURTEEN_NODE_EXECUTION_DEPTH_AND_VERIFICATION",
    "A6_EIGHT_DIRECT_CATALOG_ATTACKS_REJECT",
    "A7_ZERO_EXTERNAL_EXECUTION_AND_RELEASE_SCOPE",
)


class AuditProducts(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    authorization: dict[str, Any]
    external_review_bytes: bytes
    operator_directive_bytes: bytes
    candidate_freeze: dict[str, Any]
    detached_rebuild: dict[str, Any]
    candidate_source_authority: dict[str, Any]
    historical_catalog_audit: dict[str, Any]
    catalog_authority_audit: dict[str, Any]
    case_rows: tuple[dict[str, Any], ...]
    execution_audit: dict[str, Any]
    negative_audit: dict[str, Any]
    scope_audit: dict[str, Any]
    gate: dict[str, Any]
    decision: dict[str, Any]
    transition: dict[str, Any]
    report: dict[str, Any]
