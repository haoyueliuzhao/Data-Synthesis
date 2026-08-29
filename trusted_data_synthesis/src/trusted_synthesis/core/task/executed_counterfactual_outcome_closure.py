from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash

EXECUTED_COUNTERFACTUAL_OUTCOME_VERSION: Final = (
    "executed_counterfactual_valid_control_outcome_row_closure.v1"
)

REQUIRED_CAPABILITY_OUTCOME_FIELDS: Final = (
    "job_eligible",
    "eligibility_exclusion_reason",
    "first_response_abi_valid",
    "first_action_state_precondition_valid",
    "first_action_accepted",
    "first_attempt_base_valid",
    "first_attempt_mechanism_qualified",
    "first_attempt_qualified_valid",
    "correction_invoked",
    "correction_feedback_id",
    "corrected_action_accepted",
    "correction_terminal_reason",
    "final_base_valid",
    "final_mechanism_qualified",
    "final_qualified_valid",
)

OutcomeFixtureKind = Literal[
    "reference_valid_correction",
    "nonreference_valid_correction",
    "same_current_invalid_terminal",
    "different_current_invalid_terminal",
    "stale_or_foreign_action_terminal",
]
CorrectionTerminalReason = Literal[
    "correction_attempt_typed_invalid",
    "correction_action_reference_invalid",
]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _identity(value: BaseModel, field: str, prefix: str) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={field}, warnings=False),
        prefix=prefix,
    )


class CapabilityOutcomeRow(FrozenModel):
    row_id: str = Field(min_length=1)
    fixture_kind: OutcomeFixtureKind
    fixture_only: Literal[True] = True
    job_eligible: Literal[True] = True
    eligibility_exclusion_reason: Literal[None] = None
    first_response_abi_valid: bool
    first_action_state_precondition_valid: bool
    first_action_accepted: bool
    first_attempt_base_valid: bool
    first_attempt_mechanism_qualified: bool
    first_attempt_qualified_valid: bool
    correction_invoked: bool
    correction_feedback_id: str | None = None
    corrected_action_accepted: bool | None = None
    correction_terminal_reason: CorrectionTerminalReason | None = None
    final_base_valid: bool
    final_mechanism_qualified: bool
    final_qualified_valid: bool
    schema_version: str = EXECUTED_COUNTERFACTUAL_OUTCOME_VERSION

    @model_validator(mode="after")
    def validate_row(self) -> CapabilityOutcomeRow:
        first_conjunction = bool(
            self.first_action_accepted
            and self.first_attempt_base_valid
            and self.first_attempt_mechanism_qualified
        )
        if self.first_attempt_qualified_valid != first_conjunction:
            raise ValueError("first-attempt Qualified validity is not its exact conjunction")
        if self.final_qualified_valid != bool(
            self.final_base_valid and self.final_mechanism_qualified
        ):
            raise ValueError("final Qualified validity is not its exact conjunction")
        if self.first_action_accepted and not self.first_action_state_precondition_valid:
            raise ValueError("accepted first Action is State-precondition-invalid")
        if self.correction_invoked:
            if (
                not self.first_response_abi_valid
                or self.first_action_accepted
                or self.first_action_state_precondition_valid
                or self.correction_feedback_id is None
                or self.corrected_action_accepted is None
            ):
                raise ValueError("bounded correction invocation has invalid first-response parents")
            if self.corrected_action_accepted:
                if self.correction_terminal_reason is not None:
                    raise ValueError("accepted correction also contains a terminal reason")
            elif (
                self.correction_terminal_reason is None
                or self.final_base_valid
                or self.final_mechanism_qualified
                or self.final_qualified_valid
            ):
                raise ValueError("failed correction does not end in an exact invalid terminal")
        elif (
            self.correction_feedback_id is not None
            or self.corrected_action_accepted is not None
            or self.correction_terminal_reason is not None
            or self.final_base_valid != self.first_attempt_base_valid
            or self.final_mechanism_qualified != self.first_attempt_mechanism_qualified
            or self.final_qualified_valid != self.first_attempt_qualified_valid
        ):
            raise ValueError("non-correction outcome changes the first-attempt terminal")
        if self.row_id != _identity(
            self,
            "row_id",
            "capability_first_bounded_outcome_fixture_row:",
        ):
            raise ValueError("Capability Outcome row identity is invalid")
        return self


class CapabilityEstimandEvaluation(FrozenModel):
    evaluation_id: str = Field(min_length=1)
    eligible_job_count: int = Field(gt=0)
    q_first_numerator: int = Field(ge=0)
    q_bounded_correction_numerator: int = Field(ge=0)
    q_first_fraction: str = Field(pattern=r"^[0-9]+/[1-9][0-9]*$")
    q_bounded_correction_fraction: str = Field(pattern=r"^[0-9]+/[1-9][0-9]*$")
    first_and_final_outcomes_pooled: Literal[False] = False
    schema_version: str = EXECUTED_COUNTERFACTUAL_OUTCOME_VERSION

    @model_validator(mode="after")
    def validate_evaluation(self) -> CapabilityEstimandEvaluation:
        if self.q_first_numerator > self.eligible_job_count:
            raise ValueError("q_first numerator exceeds its fixed denominator")
        if self.q_bounded_correction_numerator > self.eligible_job_count:
            raise ValueError("q_bounded numerator exceeds its fixed denominator")
        if self.q_first_fraction != f"{self.q_first_numerator}/{self.eligible_job_count}":
            raise ValueError("q_first fraction is inconsistent")
        if self.q_bounded_correction_fraction != (
            f"{self.q_bounded_correction_numerator}/{self.eligible_job_count}"
        ):
            raise ValueError("q_bounded fraction is inconsistent")
        if self.evaluation_id != _identity(
            self,
            "evaluation_id",
            "capability_first_bounded_estimand_evaluation:",
        ):
            raise ValueError("Capability estimand evaluation identity is invalid")
        return self


def make_capability_outcome_row(
    fixture_kind: OutcomeFixtureKind,
    values: dict[str, Any],
) -> CapabilityOutcomeRow:
    payload = {"fixture_kind": fixture_kind, **values}
    provisional = CapabilityOutcomeRow.model_construct(row_id="pending", **payload)
    return CapabilityOutcomeRow(
        row_id=_identity(
            provisional,
            "row_id",
            "capability_first_bounded_outcome_fixture_row:",
        ),
        **payload,
    )


def evaluate_capability_estimands(
    rows: Sequence[CapabilityOutcomeRow],
    *,
    expected_eligible_job_count: int,
) -> CapabilityEstimandEvaluation:
    eligible = tuple(item for item in rows if item.job_eligible)
    if len(eligible) != expected_eligible_job_count or len(eligible) != len(rows):
        raise ValueError("Capability estimand denominator is not the exact eligible row set")
    q_first = sum(item.first_attempt_qualified_valid for item in eligible)
    q_bounded = sum(item.final_qualified_valid for item in eligible)
    identity_payload = {
        "eligible_job_count": expected_eligible_job_count,
        "q_first_numerator": q_first,
        "q_bounded_correction_numerator": q_bounded,
        "q_first_fraction": f"{q_first}/{expected_eligible_job_count}",
        "q_bounded_correction_fraction": f"{q_bounded}/{expected_eligible_job_count}",
        "first_and_final_outcomes_pooled": False,
        "schema_version": EXECUTED_COUNTERFACTUAL_OUTCOME_VERSION,
    }
    return CapabilityEstimandEvaluation(
        evaluation_id=canonical_hash(
            identity_payload,
            prefix="capability_first_bounded_estimand_evaluation:",
        ),
        eligible_job_count=expected_eligible_job_count,
        q_first_numerator=q_first,
        q_bounded_correction_numerator=q_bounded,
        q_first_fraction=f"{q_first}/{expected_eligible_job_count}",
        q_bounded_correction_fraction=f"{q_bounded}/{expected_eligible_job_count}",
    )


__all__ = [
    "CapabilityEstimandEvaluation",
    "CapabilityOutcomeRow",
    "CorrectionTerminalReason",
    "EXECUTED_COUNTERFACTUAL_OUTCOME_VERSION",
    "OutcomeFixtureKind",
    "REQUIRED_CAPABILITY_OUTCOME_FIELDS",
    "evaluate_capability_estimands",
    "make_capability_outcome_row",
]
