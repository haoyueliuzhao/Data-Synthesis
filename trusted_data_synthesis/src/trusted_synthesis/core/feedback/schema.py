from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash

FEEDBACK_SCHEMA_VERSION = "quality_feedback.v1"


class FeedbackRoute(str, Enum):
    INTERFACE_FAILURE = "interface_failure"
    UPSTREAM_DATA_DEFECT = "upstream_data_defect"
    AGENT_CAPABILITY_GAP = "agent_capability_gap"


class FeedbackSignal(BaseModel):
    """One root failure eligible for engineering or synthesis feedback."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    signal_id: str
    task_id: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    pattern_id: str = Field(min_length=1)
    clause_id: str = Field(min_length=1)
    clause_kind: str = Field(min_length=1)
    failure_family: str = Field(min_length=1)
    severity: Literal["fatal", "quarantine", "diagnostic"]
    failure_code: str | None = None
    route: FeedbackRoute
    weight: float = Field(gt=0)
    source_kind: Literal["quality_contract", "failed_action_plan"]
    schema_version: str = FEEDBACK_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_identity(self) -> FeedbackSignal:
        if self.signal_id != feedback_signal_id(self):
            raise ValueError("feedback signal identity is invalid")
        return self


class FeedbackExposure(BaseModel):
    """One task exposure to a Pattern x Clause-family cell."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    task_id: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    pattern_id: str = Field(min_length=1)
    failure_family: str = Field(min_length=1)


class PatternClauseFailure(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    cell_id: str
    pattern_id: str
    failure_family: str
    exposure_count: int = Field(ge=1)
    root_failure_count: int = Field(ge=0)
    weighted_root_failure_sum: float = Field(ge=0)
    weighted_root_failure_rate: float = Field(ge=0)
    contributing_domains: tuple[str, ...]


class AllocationCell(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    cell_id: str
    pattern_id: str
    failure_family: str
    base_probability: float = Field(ge=0, le=1)
    feedback_probability: float = Field(ge=0, le=1)
    final_probability: float = Field(ge=0, le=1)
    allocated_count: int = Field(ge=0)


class RefinementAllocation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    allocation_id: str
    lambda_value: float = Field(ge=0, le=1)
    alpha: float = Field(gt=0)
    epsilon: float = Field(gt=0)
    total_budget: int = Field(ge=1)
    cells: tuple[AllocationCell, ...] = Field(min_length=1)
    capability_signal_count: int = Field(ge=0)
    changed_controls: tuple[str, ...] = ("pattern_clause_weight",)
    schema_version: str = "refinement_allocation.v1"

    @model_validator(mode="after")
    def validate_budget(self) -> RefinementAllocation:
        if sum(item.allocated_count for item in self.cells) != self.total_budget:
            raise ValueError("refinement allocation does not preserve the total budget")
        if abs(sum(item.final_probability for item in self.cells) - 1.0) > 1e-9:
            raise ValueError("refinement allocation probabilities must sum to one")
        return self


def feedback_signal_id(value: FeedbackSignal) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"signal_id"}),
        prefix="quality_feedback_signal:",
    )


def make_feedback_signal(
    *,
    task_id: str,
    domain: str,
    pattern_id: str,
    clause_id: str,
    clause_kind: str,
    failure_family: str,
    severity: Literal["fatal", "quarantine", "diagnostic"],
    route: FeedbackRoute,
    source_kind: Literal["quality_contract", "failed_action_plan"],
    failure_code: str | None = None,
    weight: float,
) -> FeedbackSignal:
    values = {
        "task_id": task_id,
        "domain": domain,
        "pattern_id": pattern_id,
        "clause_id": clause_id,
        "clause_kind": clause_kind,
        "failure_family": failure_family,
        "severity": severity,
        "failure_code": failure_code,
        "route": route.value,
        "weight": weight,
        "source_kind": source_kind,
        "schema_version": FEEDBACK_SCHEMA_VERSION,
    }
    return FeedbackSignal(
        signal_id=canonical_hash(values, prefix="quality_feedback_signal:"),
        task_id=task_id,
        domain=domain,
        pattern_id=pattern_id,
        clause_id=clause_id,
        clause_kind=clause_kind,
        failure_family=failure_family,
        severity=severity,
        failure_code=failure_code,
        route=route,
        weight=weight,
        source_kind=source_kind,
        schema_version=FEEDBACK_SCHEMA_VERSION,
    )
