"""Bounds and typed source declarations for the local candidate-family preflight."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.canonical_json import strict_canonical_hash
from trusted_synthesis.core.task.program import TaskProgram, make_program

STAGE = "finance_qa_vnext_reasoning_behavior_typed_candidate_family_constructibility_preflight_only"
NEXT_STAGE = "finance_qa_vnext_finite_own_qualified_candidate_semantic_equivalence_comparison_only"
REVIEW_BYTES = 25_343
REVIEW_SHA256 = "893f9718dca59a1d29b1fe9f993471ff15e9fbfeb86cc570ef1b9b9db670ddcc"
DIRECTIVE = "参照审计报告开展后续实验"
DIRECTIVE_BYTES = 36
DIRECTIVE_SHA256 = "3915f5d4befe661fb2b627ac9b578caa07e860a7c0ab4f70b438f6cd96a65403"
MAX_POSITIVE_EXECUTIONS = 6
MAX_MAIN_CANDIDATES = 4
MAX_REGISTERED_ACTIONS = 10
GROUP_ORDER = ("B", "A", "C")
ROLE_ORDER = ("revenue_earlier", "revenue_later", "income_earlier", "income_later")
ARCHIVE_DIRECTORY = (
    "trusted_data_synthesis/artifacts/qa_semantic_depth_three_archive_grounding/"
    "qa_semantic_operation_depth_three_plus_archive_grounded_parameter_space_"
    "constructibility_preflight_v1_20260904"
)
ARCHIVE_FILE_COUNT = 24
ARCHIVE_TOTAL_BYTES = 784_989
ARCHIVE_MEMBER_COUNT = 23
ARCHIVE_MEMBER_BYTES = 781_444
ARCHIVE_MANIFEST_BYTES = 3_545
ARCHIVE_MANIFEST_SHA256 = "8a86354d574311631e0b38faa6acb79d13602291d4bcac350af0edfdb92b83c2"
ARCHIVE_MANIFEST_ID = (
    "qa_archive_parameter_space_artifact_manifest:"
    "29dbf80f462d7dbf079df99e77d44dc5739b2a9ece8525356b43dc9ddc0f63b7"
)
ARCHIVE_ROOT_ID = (
    "qa_archive_parameter_space_artifact_root:"
    "b24d054bbf6cd5275675636f7a3f69fac127b2ab1a42483911c384c1cae60f98"
)
FROZEN_CATALOG_ID = (
    "finance_qa_registered_catalog:4761c0dace3f2f87169c6f10db76043fc250ff03f584e7466e21b10e13b63268"
)
FIXTURE_SPECS = (
    (
        "F1",
        "branch_hii_2014_q2_2014_q4",
        "qa_archive_parameter_case_row:"
        "4fba9ca1c78dad48c2967342be05775c8da6ae4ed1544aba5d8c4e8fbedd1e62",
        "task:8d0e3d8dd2b5f4f981b72d7c9e600798229e246dd909a15746b5232ad648d2af",
    ),
    (
        "F2",
        "branch_hii_2014_q1_2014_q3",
        "qa_archive_parameter_case_row:"
        "08615e003521da447a78d55af5ac14f1b0cfc69e72eb650cfcb5c87deddcf39e",
        "task:c3c91045437afe06ab99c74655f93989bb9525428e76b14d41f792dfbb595c28",
    ),
)


class CandidateFamilyError(ValueError):
    def __init__(self, stage: str, reason: str) -> None:
        super().__init__(reason)
        self.stage = stage


def identified(values: dict[str, Any], field: str, prefix: str) -> dict[str, Any]:
    """Identify an actual declaration; this is never an execution certificate."""

    if field in values:
        raise ValueError(f"identity field already present: {field}")
    return {**values, field: strict_canonical_hash(values, prefix=prefix)}


class CandidateRoute(BaseModel):
    """A finite, source-checked proposal, whose validity still requires own replay."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate_id: str = Field(min_length=1)
    fixture_id: Literal["F1", "F2"]
    case_id: str
    task_id: str
    task_instance_id: str
    group: Literal["B", "A", "C"]
    route_kind: Literal[
        "registered_lookup_backed_baseline",
        "registered_direct_evidence_projection",
        "baseline_independent_growth_swap_control",
    ]
    program: TaskProgram
    program_json: dict[str, Any]
    schedule: tuple[str, ...]
    scheduled_node_ids: tuple[str, ...]
    source_inventory_id: str
    scope_binding_id: str
    source_rule_bindings: dict[str, Any]
    obligation_specs: tuple[dict[str, Any], ...]
    field_provenance: dict[str, Any]
    source_type_check: dict[str, Any]
    schema_version: str = "qa_reasoning_candidate_route.v1"

    @model_validator(mode="after")
    def validate_declaration(self) -> CandidateRoute:
        nodes = {node.node_id: node for node in self.program.nodes}
        if (
            self.candidate_id
            != strict_canonical_hash(
                self.model_dump(mode="python", exclude={"candidate_id"}),
                prefix="qa_reasoning_candidate_route:",
            )
            or self.program.program_id
            != make_program(self.program.nodes, self.program.output_node_id).program_id
        ):
            raise ValueError("candidate or Program content identity differs")
        if (
            self.task_instance_id != self.task_id
            or len(self.schedule) != len(nodes)
            or len(set(self.schedule)) != len(nodes)
            or set(self.schedule) != set(nodes)
            or self.scheduled_node_ids != self.schedule
            or len(nodes) > MAX_REGISTERED_ACTIONS
            or self.program_json != self.program.model_dump(mode="json")
        ):
            raise ValueError("candidate source declaration has inconsistent bounds or identities")
        seen: set[str] = set()
        for node_id in self.schedule:
            if not set(nodes[node_id].dependencies) <= seen:
                raise ValueError("candidate schedule consumes an unavailable producer")
            seen.add(node_id)
        return self
