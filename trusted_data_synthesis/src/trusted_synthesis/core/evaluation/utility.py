from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash

TRAINING_UTILITY_PROTOCOL_VERSION = "training_utility_protocol.v3"


class UtilityCohort(str, Enum):
    RANDOM_SYNTHETIC = "D1_random_synthetic"
    REFERENCE_WORKFLOW = "D2_reference_workflow"
    CONTRACT_FILTERED = "D3_contract_filtered"
    CONTRACT_COUNTERFACTUAL = "D4_contract_counterfactual_calibrated"
    CRITIC_SELECTED = "D5_quality_critic_selected"


class TrainingCohortManifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    cohort: UtilityCohort
    sample_ids: tuple[str, ...]
    negative_sample_ids: tuple[str, ...] = ()
    construction_policy: str = Field(min_length=1)
    materialization_status: Literal["planned", "prepared"]
    selection_manifest_hash: str

    @model_validator(mode="after")
    def validate_materialization(self) -> TrainingCohortManifest:
        if self.materialization_status == "planned" and self.sample_ids:
            raise ValueError("planned cohort cannot claim prepared sample IDs")
        if self.materialization_status == "prepared" and not self.sample_ids:
            raise ValueError("prepared cohort requires sample IDs")
        return self


class TrainingUtilityProtocol(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    protocol_id: str
    base_model: str = Field(min_length=1)
    training_method: str = "sft"
    fixed_hyperparameters: dict[str, str | int | float | bool]
    cohorts: tuple[TrainingCohortManifest, ...]
    evaluation_metrics: tuple[str, ...] = (
        "answer_accuracy",
        "evidence_recall",
        "citation_accuracy",
        "multi_hop_accuracy",
        "tool_success_rate",
        "distractor_robustness",
    )
    held_out_domains: tuple[str, ...] = ()
    status: str = "planned"
    protocol_version: str = TRAINING_UTILITY_PROTOCOL_VERSION

    @model_validator(mode="after")
    def validate_cohorts(self) -> TrainingUtilityProtocol:
        observed = {item.cohort for item in self.cohorts}
        if observed != set(UtilityCohort):
            raise ValueError("training utility protocol must freeze D1 through D5")
        if self.status != "planned":
            raise ValueError("protocol schema cannot claim training completion")
        return self

    @property
    def protocol_hash(self) -> str:
        return canonical_hash(self, prefix="training_utility_protocol:")


class TrainingUtilityResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    result_id: str
    protocol_hash: str
    cohort_metrics: dict[UtilityCohort, dict[str, float]]
    completed_run_ids: dict[UtilityCohort, str]
    status: str

    @model_validator(mode="after")
    def validate_completed_runs(self) -> TrainingUtilityResult:
        if self.status == "completed":
            if set(self.cohort_metrics) != set(UtilityCohort):
                raise ValueError("completed utility result requires metrics for D1 through D5")
            if set(self.completed_run_ids) != set(UtilityCohort):
                raise ValueError("completed utility result requires run IDs for D1 through D5")
        return self


def make_training_utility_protocol(
    *,
    base_model: str,
    fixed_hyperparameters: dict[str, str | int | float | bool],
    cohort_samples: dict[UtilityCohort, tuple[str, ...]],
    cohort_construction_policies: dict[UtilityCohort, str] | None = None,
    counterfactual_ids: tuple[str, ...] = (),
    held_out_domains: tuple[str, ...] = (),
) -> TrainingUtilityProtocol:
    if set(cohort_samples) != set(UtilityCohort):
        raise ValueError("cohort sample mapping must contain D1 through D5")
    policies = cohort_construction_policies or {
        UtilityCohort.RANDOM_SYNTHETIC: (
            "uniform_random_unfiltered_real_agent_outputs_without_counterfactual_injection"
        ),
        UtilityCohort.REFERENCE_WORKFLOW: "deterministic_reference_workflows",
        UtilityCohort.CONTRACT_FILTERED: "contract_accepted_real_agent_candidates",
        UtilityCohort.CONTRACT_COUNTERFACTUAL: (
            "typed_counterfactual_failure_guided_clean_solve_allocation"
        ),
        UtilityCohort.CRITIC_SELECTED: (
            "authoritative_contract_then_quality_aware_selector_with_advisory_critic"
        ),
    }
    if set(policies) != set(UtilityCohort):
        raise ValueError("cohort construction policies must contain D1 through D5")
    cohorts = tuple(
        TrainingCohortManifest(
            cohort=cohort,
            sample_ids=cohort_samples[cohort],
            negative_sample_ids=(
                counterfactual_ids if cohort == UtilityCohort.CONTRACT_COUNTERFACTUAL else ()
            ),
            construction_policy=policies[cohort],
            materialization_status=("prepared" if cohort_samples[cohort] else "planned"),
            selection_manifest_hash=canonical_hash(
                {
                    "cohort": cohort.value,
                    "sample_ids": cohort_samples[cohort],
                    "construction_policy": policies[cohort],
                    "materialization_status": ("prepared" if cohort_samples[cohort] else "planned"),
                    "negative_sample_ids": (
                        counterfactual_ids
                        if cohort == UtilityCohort.CONTRACT_COUNTERFACTUAL
                        else ()
                    ),
                },
                prefix="training_cohort_selection:",
            ),
        )
        for cohort in UtilityCohort
    )
    identity = {
        "base_model": base_model,
        "fixed_hyperparameters": fixed_hyperparameters,
        "cohorts": [item.model_dump(mode="json") for item in cohorts],
        "held_out_domains": held_out_domains,
        "protocol_version": TRAINING_UTILITY_PROTOCOL_VERSION,
    }
    return TrainingUtilityProtocol(
        protocol_id=canonical_hash(identity, prefix="training_utility_protocol:"),
        base_model=base_model,
        fixed_hyperparameters=fixed_hyperparameters,
        cohorts=cohorts,
        held_out_domains=held_out_domains,
    )
