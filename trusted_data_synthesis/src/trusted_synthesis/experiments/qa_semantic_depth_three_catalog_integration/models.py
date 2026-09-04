from __future__ import annotations

from typing import Any, Final

from pydantic import BaseModel, ConfigDict

STAGE: Final = (
    "qa_semantic_operation_depth_three_plus_registered_catalog_integration_preflight_only"
)
DECISION: Final = (
    "qa_semantic_operation_depth_three_plus_registered_catalog_integration_"
    "preflight_passed_independent_audit_required"
)
NEXT_STAGE: Final = (
    "qa_semantic_operation_depth_three_plus_registered_catalog_integration_"
    "preflight_independent_audit_only"
)

EXTERNAL_REVIEW_SHA256: Final = "2b95605826bac2da00f67e3264d0d6cb6c72081473963a10a7939417a7cd917d"
EXTERNAL_REVIEW_BYTE_COUNT: Final = 13_342
OPERATOR_DIRECTIVE: Final = "参照审计报告继续QA合成链实验"
OPERATOR_DIRECTIVE_SHA256: Final = (
    "a476c8224f869ecf8de596d936faec0de22b7cbbdf968a1db7f94c40c46ca8bd"
)
OPERATOR_DIRECTIVE_BYTE_COUNT: Final = 41

PREDECESSOR_DIRECTORY: Final = (
    "trusted_data_synthesis/artifacts/qa_semantic_depth_three_plus_independent_audit/"
    "qa_semantic_operation_depth_three_plus_constructibility_and_coverage_preflight_"
    "independent_audit_v1_20260904"
)
PREDECESSOR_SOURCE_COMMIT: Final = "4eb2f87e90e72c4748d37fdea2d0e98fea13d6f8"
PREDECESSOR_SOURCE_TREE: Final = "d2554444ae90350804a73add64c70f48d6367ebc"
PREDECESSOR_FILE_COUNT: Final = 17
PREDECESSOR_TOTAL_BYTES: Final = 49_551
PREDECESSOR_MEMBER_COUNT: Final = 16
PREDECESSOR_MEMBER_BYTES: Final = 46_959
PREDECESSOR_MANIFEST_BYTES: Final = 2_592
PREDECESSOR_MANIFEST_SHA256: Final = (
    "b2a28200e1f555ec58afaa4f24a88e561600248401da010036a0dda3059ea182"
)
PREDECESSOR_MANIFEST_ID: Final = (
    "qa_semantic_depth_three_independent_artifact_manifest:"
    "1499a9ca7f7d31187d5424d3e589209a3f42cfdc070b077fb33cde11c68ab717"
)
PREDECESSOR_ROOT_ID: Final = (
    "qa_semantic_depth_three_independent_artifact_root:"
    "a8463e016a7f85d2b7d9772ce89e2ad801aeedb38accdb6eab55ad73f1526b55"
)
PREDECESSOR_REPORT_ID: Final = (
    "qa_semantic_depth_three_independent_report:"
    "38cf48aa35a705812d1eaed3c0180a56194fbf5ef77a3dd675aa44f130d12d48"
)
PREDECESSOR_GATE_ID: Final = (
    "qa_semantic_depth_three_independent_gate:"
    "046a342f45dbf54808f5356b00ff2c0e26b6921b8c91e01125cde414986d6f69"
)
PREDECESSOR_DECISION_ID: Final = (
    "qa_semantic_depth_three_independent_decision:"
    "7cdd0ae2d3df43c8fb20e130a0551ab374af12825e3d7716fafcafae42ecb5b9"
)
PREDECESSOR_TRANSITION_ID: Final = (
    "qa_semantic_depth_three_independent_transition:"
    "a0be77a5a9411baa83bcb3deca0a99f979bb6c43c04089df0730fad30c1432c3"
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

SOURCE_PATHS: Final = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "qa_semantic_depth_three_catalog_integration/__init__.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "qa_semantic_depth_three_catalog_integration/models.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "qa_semantic_depth_three_catalog_integration/catalog.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "qa_semantic_depth_three_catalog_integration/preflight.py",
)

NEGATIVE_CONTROL_NAMES: Final = (
    "task_type_alias",
    "missing_task_registration",
    "duplicate_task_registration",
    "missing_operation_registration",
    "duplicate_operation_registration",
    "wrong_operation_role",
    "catalog_bypass_without_resolution_receipt",
    "crossed_pattern_registration",
)


class Products(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    authorization: dict[str, Any]
    external_review_bytes: bytes
    operator_directive_bytes: bytes
    predecessor_freeze: dict[str, Any]
    source_binding: dict[str, Any]
    historical_catalog_freeze: dict[str, Any]
    catalog_descriptor: dict[str, Any]
    discovery_receipts: tuple[dict[str, Any], ...]
    integration_rows: tuple[dict[str, Any], ...]
    integration_audit: dict[str, Any]
    negative_audit: dict[str, Any]
    scope_audit: dict[str, Any]
    gate: dict[str, Any]
    decision: dict[str, Any]
    transition: dict[str, Any]
    report: dict[str, Any]
    bundles: tuple[Any, ...]
    packages: tuple[Any, ...]
    executions: tuple[Any, ...]
    verification_reports: tuple[Any, ...]
    assessments: tuple[Any, ...]
    depth_metrics: tuple[Any, ...]
