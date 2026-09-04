from __future__ import annotations

from typing import Any, Final

from pydantic import BaseModel, ConfigDict

STAGE: Final = (
    "qa_semantic_operation_depth_three_plus_archive_grounded_parameter_space_"
    "constructibility_preflight_only"
)
DECISION: Final = (
    "qa_semantic_operation_depth_three_plus_archive_grounded_parameter_space_"
    "constructibility_failed_registered_margin_target_evidence_absent"
)
PROSPECTIVE_NEXT_STAGE: Final = (
    "qa_registered_margin_target_gap_authoritative_target_evidence_archive_expansion_preflight_only"
)

EXTERNAL_REVIEW_SHA256: Final = "e3564ae8610b5f38624f2bd72d32b4f989ff455a23a4b3f60d999e2517f1f9c1"
EXTERNAL_REVIEW_BYTE_COUNT: Final = 11_253
OPERATOR_DIRECTIVE: Final = "参照审计继续QA链路实验"
OPERATOR_DIRECTIVE_SHA256: Final = (
    "5ac54319faf77fd28b5da88716880cb094373e1cf96322f8646960521605ee45"
)
OPERATOR_DIRECTIVE_BYTE_COUNT: Final = 32

PREDECESSOR_DIRECTORY: Final = (
    "trusted_data_synthesis/artifacts/"
    "qa_semantic_depth_three_catalog_integration_independent_audit/"
    "qa_semantic_operation_depth_three_plus_registered_catalog_integration_"
    "preflight_independent_audit_v1_20260904"
)
PREDECESSOR_SOURCE_COMMIT: Final = "cbc85fc1d66d46e58bf679f6825172b51ac27819"
PREDECESSOR_SOURCE_TREE: Final = "415abb224c6070d29ccb91c5ad2747bdd38455c2"
PREDECESSOR_FILE_COUNT: Final = 17
PREDECESSOR_TOTAL_BYTES: Final = 48_465
PREDECESSOR_MEMBER_COUNT: Final = 16
PREDECESSOR_MEMBER_BYTES: Final = 45_866
PREDECESSOR_MANIFEST_BYTES: Final = 2_599
PREDECESSOR_MANIFEST_SHA256: Final = (
    "1f05c868fd88b11008ca38d07017c1b6349ab17d5f14f2c49b1e9313068d7bc3"
)
PREDECESSOR_MANIFEST_ID: Final = (
    "qa_registered_catalog_independent_artifact_manifest:"
    "c7f36c18aa46e5456e1b1cb3693344d4d4f9fc040a6d27491d4bbd60e20a9ed8"
)
PREDECESSOR_ROOT_ID: Final = (
    "qa_registered_catalog_independent_artifact_root:"
    "dd8c66bfd5374871d1ed96311aa042a612308696a7cf0f01e53e4c465ca926cb"
)
PREDECESSOR_REPORT_ID: Final = (
    "qa_registered_catalog_independent_report:"
    "93b4b12fb32936bc767c135b2897a0d020ea4fbb794595216cb20d43628f9eda"
)
PREDECESSOR_GATE_ID: Final = (
    "qa_registered_catalog_independent_gate:"
    "857cc64a51101e52c61dc575ce1d4f81721c3511aa346d4e84bc622eb89330f2"
)
PREDECESSOR_DECISION_ID: Final = (
    "qa_registered_catalog_independent_decision:"
    "9878eb311f4f50cbe1e4c7b67364d0023a5fbae44f3b458697124bd3aa3f27fe"
)
PREDECESSOR_TRANSITION_ID: Final = (
    "qa_registered_catalog_independent_transition:"
    "1ed6e00744475f3f9efa0e3f6a70a7da4ec6eaaf166cc2edd020e41d69099daf"
)

CATALOG_DIRECTORY: Final = (
    "trusted_data_synthesis/artifacts/qa_semantic_depth_three_catalog_integration/"
    "qa_semantic_operation_depth_three_plus_registered_catalog_integration_"
    "preflight_v1_20260904"
)
CATALOG_DESCRIPTOR_SHA256: Final = (
    "b598c8f4f6f2374d515894083d9ae7aa1f3d452ec544cddfbb53ed471659eb56"
)
CATALOG_DESCRIPTOR_BYTE_COUNT: Final = 20_728
CATALOG_ID: Final = (
    "finance_qa_registered_catalog:4761c0dace3f2f87169c6f10db76043fc250ff03f584e7466e21b10e13b63268"
)

ARCHIVE_PATH: Final = "trusted_data_synthesis/benchmarks/finqa/frozen/test.json"
ARCHIVE_SHA256: Final = "831dbfb2e785dbc227f895ce3f24046433467aec67b09db2bd6ac7692a8a30dc"
ARCHIVE_BYTE_COUNT: Final = 14_395_143
ARCHIVE_RECORD_COUNT: Final = 1_147
SOURCE_RECORD_IDS: Final = (
    "CDW/2017/page_38.pdf-1",
    "HII/2015/page_121.pdf-1",
)
EXTENSION_TASK_TYPES: Final = (
    "derived_growth_absolute_spread",
    "registered_margin_target_gap",
)

SOURCE_PATHS: Final = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "qa_semantic_depth_three_archive_grounding/__init__.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "qa_semantic_depth_three_archive_grounding/models.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "qa_semantic_depth_three_archive_grounding/archive.py",
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "qa_semantic_depth_three_archive_grounding/preflight.py",
)

NEGATIVE_CONTROL_NAMES: Final = (
    "archive_byte_mutation",
    "source_record_substitution",
    "source_cell_mutation",
    "cross_entity_binding",
    "reversed_period_binding",
    "fabricated_target_constant",
    "derived_margin_relabelled_as_target",
    "fixed_aggregate_injection",
    "failed_serial_rows_omitted",
)


class Products(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    authorization: dict[str, Any]
    external_review_bytes: bytes
    operator_directive_bytes: bytes
    predecessor_freeze: dict[str, Any]
    source_binding: dict[str, Any]
    archive_binding: dict[str, Any]
    archive_records: tuple[dict[str, Any], ...]
    catalog_freeze: dict[str, Any]
    case_rows: tuple[dict[str, Any], ...]
    parameter_space_audit: dict[str, Any]
    negative_audit: dict[str, Any]
    scope_audit: dict[str, Any]
    gate: dict[str, Any]
    decision: dict[str, Any]
    transition: dict[str, Any]
    report: dict[str, Any]
    bundles: tuple[Any, ...]
    discovery_receipts: tuple[dict[str, Any], ...]
    packages: tuple[Any, ...]
    executions: tuple[Any, ...]
    verification_reports: tuple[Any, ...]
    assessments: tuple[Any, ...]
    depth_metrics: tuple[Any, ...]
