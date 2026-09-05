"""Typed, unexecuted change requests for public-behavior contract design."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

STAGE = (
    "finance_qa_vnext_public_reasoning_semantics_allowed_behavior_and_quotient_contract_design_only"
)
NEXT_STAGE = (
    "finance_qa_vnext_reasoning_behavior_typed_candidate_family_constructibility_preflight_only"
)
REVIEW_BYTES = 13_357
REVIEW_SHA256 = "5bb6c8fd48bc953be1130d07ce6542320e55d855240f84277fb49c52070e3e38"
DIRECTIVE = "参照审计继续实验"
DIRECTIVE_BYTES = 24
DIRECTIVE_SHA256 = "b2dc80634c27edf4db128ad352e77776e2dfe3242a450bfa62783d426b298fcb"

ChangeDimension = Literal[
    "schedule_order",
    "runtime_identity",
    "wording",
    "numeric_surface",
    "evidence_support",
    "decision_basis",
    "derivation_dependencies",
    "observation_update",
    "task_definition",
    "evidence_universe",
    "oracle_program",
    "answer_schema",
    "unit_contract",
    "rounding_tolerance",
    "citation_contract",
    "validity_obligations",
    "unregistered_equivalence",
    "unsupported_update",
    "external_evidence",
]


class DesignChangeRequest(BaseModel):
    """A proposal, not a trajectory, execution proof, or qualification report.

    Relation fields state hypothetical premises that a future own-trajectory
    replay must establish. They are never accepted as empirical evidence.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    execution_status: Literal["design_unexecuted"]
    changed_dimensions: tuple[ChangeDimension, ...] = Field(min_length=1)
    schedule_relation: Literal["unchanged", "independent_commuting_swap", "dependency_crossing"] = (
        "unchanged"
    )
    evidence_relation: Literal[
        "unchanged", "different_admissible_visible_support", "outside_frozen_visible_universe"
    ] = "unchanged"
    basis_relation: Literal["unchanged", "different_typed_grounded_basis", "unsupported_basis"] = (
        "unchanged"
    )
    derivation_relation: Literal[
        "unchanged", "different_typed_obligation_discharge", "unregistered_route"
    ] = "unchanged"
    update_relation: Literal[
        "unchanged", "observation_grounded_rejection_or_revision", "unsupported_rewrite"
    ] = "unchanged"
    numeric_before: str | None = None
    numeric_after: str | None = None

    @model_validator(mode="after")
    def unique_dimensions(self) -> DesignChangeRequest:
        if len(set(self.changed_dimensions)) != len(self.changed_dimensions):
            raise ValueError("design request repeats a changed dimension")
        return self
