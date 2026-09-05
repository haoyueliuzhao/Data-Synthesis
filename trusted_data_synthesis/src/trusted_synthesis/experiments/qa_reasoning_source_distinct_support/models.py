"""Exact external boundary and non-substitutable source-uninstantiated decision."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from trusted_synthesis.canonical_json import strict_canonical_hash

STAGE = (
    "finance_qa_vnext_source_distinct_support_route_constructibility_"
    "and_finite_separation_preflight_only"
)
REVIEW_BYTES = 24_654
REVIEW_SHA256 = "e279cc6ee587766a87b430588fe1632a0d48a3c84f6b9c97a86908523e768dce"
DIRECTIVE = "参照审计继续实验"
DIRECTIVE_SHA256 = "b2dc80634c27edf4db128ad352e77776e2dfe3242a450bfa62783d426b298fcb"
PREDECESSOR = (
    "trusted_data_synthesis/artifacts/qa_reasoning_finite_comparison/"
    "finance_qa_vnext_finite_own_qualified_candidate_semantic_equivalence_comparison_v1_20260905"
)
PREDECESSOR_MANIFEST = (
    "qa_reasoning_finite_comparison_manifest:"
    "3e612e9d6937ff6169ce9a88f284ef55cb9a8e3c81d91dcecad56ce170dce047"
)
PREDECESSOR_ROOT = (
    "qa_reasoning_finite_comparison_root:"
    "ef93a3154167c8c739d557066e49078e5b6564c7ece8f3afa0fa8a3cbc00ec00"
)
PREDECESSOR_COMMIT = "b1e43da622c7fc10823c3d40d02d9b6445fdfe38"
PREDECESSOR_TREE = "b33869265ee66faa25b997c1029bae8f6f7115c9"
REFERENCE_COMMIT = "4ee09da62f3dc873758f2641a96c7cb4dce5bc7d"
REFERENCE_TREE = "8decf14e2c82f331b6d27c5152afccb953d5020e"


class SupportSourceError(ValueError):
    def __init__(self, stage: str, message: str) -> None:
        super().__init__(message)
        self.stage = stage


def require(condition: bool, stage: str, message: str) -> None:
    if not condition:
        raise SupportSourceError(stage, message)


def identified(payload: dict[str, Any], kind: str, field: str = "audit_id") -> dict[str, Any]:
    require(field not in payload, "identity.input", "caller may not provide new object identity")
    result = {"schema_version": f"qa_source_distinct_support_{kind}.v1", **payload}
    result[field] = strict_canonical_hash(result, prefix=f"qa_source_distinct_support_{kind}:")
    return result


class UninstantiatedDecision(BaseModel):
    """A source gap is neither W=0 nor failed/existing candidate validity."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    status: Literal["source_not_instantiated"] = "source_not_instantiated"
    scientific_witness: None = None
    formal_semantic_class_count: None = None
    same_task_finite_relation: None = None
    new_task_instances: Literal[0] = 0
    new_candidate_declarations: Literal[0] = 0
    candidate_runtime_executions: Literal[0] = 0
    own_route_validations: Literal[0] = 0
    finite_comparisons: Literal[0] = 0
    supported_revenue_partition_pages: int
    missing_required_roles: tuple[str, ...]
    scope_qualified_missing_fact: str
    proof_of_global_nonexistence: Literal[False] = False
    source_inspection_complete: Literal[True] = True
    two_route_constructibility_passed: Literal[False] = False
    model_or_training_result: Literal[False] = False
