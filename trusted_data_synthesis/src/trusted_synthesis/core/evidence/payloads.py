from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FrozenPayload(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class EvidenceKind(str, Enum):
    SCALAR = "scalar_observation"
    TEXTUAL_CLAIM = "textual_claim"
    RULE = "rule_statement"
    RELATION = "relation_assertion"
    EXPERIMENTAL_RESULT = "experimental_result"
    DERIVED_RESULT = "derived_result"


class ScalarObservation(FrozenPayload):
    kind: Literal[EvidenceKind.SCALAR] = EvidenceKind.SCALAR
    value: Decimal | int | float
    unit: str | None = None
    currency: str | None = None
    precision: int | None = Field(default=None, ge=0)


class TextualClaim(FrozenPayload):
    kind: Literal[EvidenceKind.TEXTUAL_CLAIM] = EvidenceKind.TEXTUAL_CLAIM
    claim_text: str = Field(min_length=1)
    polarity: Literal["positive", "negative", "mixed", "neutral"] = "neutral"
    qualifiers: tuple[str, ...] = ()


class RuleStatement(FrozenPayload):
    kind: Literal[EvidenceKind.RULE] = EvidenceKind.RULE
    rule_text: str = Field(min_length=1)
    conditions: tuple[str, ...] = ()
    exceptions: tuple[str, ...] = ()
    authority: str = Field(min_length=1)
    legal_effect: str | None = None


class RelationAssertion(FrozenPayload):
    kind: Literal[EvidenceKind.RELATION] = EvidenceKind.RELATION
    relation: str = Field(min_length=1)
    object_id: str = Field(min_length=1)
    object_type: str = Field(min_length=1)
    object_label: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class UncertaintyInterval(FrozenPayload):
    lower: Decimal | float
    upper: Decimal | float
    confidence_level: float | None = Field(default=None, gt=0, le=1)

    @model_validator(mode="after")
    def validate_bounds(self) -> UncertaintyInterval:
        if Decimal(str(self.lower)) > Decimal(str(self.upper)):
            raise ValueError("uncertainty lower bound must not exceed upper bound")
        return self


class ExperimentalResult(FrozenPayload):
    kind: Literal[EvidenceKind.EXPERIMENTAL_RESULT] = EvidenceKind.EXPERIMENTAL_RESULT
    metric: str = Field(min_length=1)
    value: Decimal | int | float
    unit: str | None = None
    dataset: str | None = None
    method: str = Field(min_length=1)
    comparator: str | None = None
    uncertainty: UncertaintyInterval | None = None
    sample_size: int | None = Field(default=None, gt=0)
    protocol: dict[str, Any] = Field(default_factory=dict)


class DerivedResult(FrozenPayload):
    kind: Literal[EvidenceKind.DERIVED_RESULT] = EvidenceKind.DERIVED_RESULT
    operation_id: str = Field(min_length=1)
    input_evidence_ids: tuple[str, ...] = Field(min_length=1)
    output: dict[str, Any]
    formula: str | None = None


EvidencePayload = Annotated[
    ScalarObservation
    | TextualClaim
    | RuleStatement
    | RelationAssertion
    | ExperimentalResult
    | DerivedResult,
    Field(discriminator="kind"),
]
