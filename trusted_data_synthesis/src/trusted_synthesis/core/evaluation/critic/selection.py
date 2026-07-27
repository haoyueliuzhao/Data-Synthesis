from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from trusted_synthesis.core.evaluation.critic.schema import (
    AcceptabilityLabel,
    QualityCriticExample,
    QualityCriticPrediction,
)
from trusted_synthesis.hashing import canonical_hash


class QualitySelectionPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    policy_id: str = "quality_aware_selection.v1"
    target_size: int = Field(ge=1)
    minimum_overall_score: float = Field(default=0.8, ge=0, le=1)
    minimum_dimension_score: float = Field(default=0.6, ge=0, le=1)
    minimum_critic_accept_probability: float = Field(default=0.5, ge=0, le=1)
    maximum_per_stratum: int | None = Field(default=None, ge=1)
    stratum_fields: tuple[str, ...] = (
        "domain",
        "retrieval_track",
        "planning_track",
        "candidate_source",
    )

    @property
    def policy_hash(self) -> str:
        return canonical_hash(self, prefix="quality_selection_policy:")


class QualitySelectionResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    selection_id: str
    policy_hash: str
    selected_example_ids: tuple[str, ...]
    rejected_by_contract_count: int = Field(ge=0)
    rejected_by_vector_count: int = Field(ge=0)
    rejected_by_critic_count: int = Field(ge=0)
    stratum_counts: dict[str, int]
    status: str
    shortfall: int = Field(ge=0)


class QualityAwareSelector:
    """Rank accepted samples; learned critics can advise but never overrule Contract."""

    def select(
        self,
        examples: tuple[QualityCriticExample, ...],
        policy: QualitySelectionPolicy,
        predictions: tuple[QualityCriticPrediction, ...] = (),
    ) -> QualitySelectionResult:
        prediction_by_example = {item.example_id: item for item in predictions}
        rejected_contract = 0
        rejected_vector = 0
        rejected_critic = 0
        eligible: list[tuple[float, str, QualityCriticExample]] = []
        for example in examples:
            if example.contract_annotation.acceptability != AcceptabilityLabel.ACCEPT:
                rejected_contract += 1
                continue
            vector = example.quality_vector
            if (
                vector.overall_score < policy.minimum_overall_score
                or vector.minimum_applicable_score < policy.minimum_dimension_score
            ):
                rejected_vector += 1
                continue
            prediction = prediction_by_example.get(example.example_id)
            if (
                prediction is not None
                and prediction.accept_probability
                < policy.minimum_critic_accept_probability
            ):
                rejected_critic += 1
                continue
            # Missing advisory review is neutral; it must not outrank a reviewed sample
            # merely because the critic budget did not cover it.
            critic_score = prediction.accept_probability if prediction is not None else 0.5
            score = (
                0.55 * vector.overall_score
                + 0.25 * vector.minimum_applicable_score
                + 0.20 * critic_score
            )
            eligible.append((score, _stratum(example, policy), example))
        eligible.sort(key=lambda item: (-item[0], item[2].example_id))
        selected: list[QualityCriticExample] = []
        stratum_counts: dict[str, int] = {}
        for _, stratum, example in eligible:
            if len(selected) >= policy.target_size:
                break
            if (
                policy.maximum_per_stratum is not None
                and stratum_counts.get(stratum, 0) >= policy.maximum_per_stratum
            ):
                continue
            selected.append(example)
            stratum_counts[stratum] = stratum_counts.get(stratum, 0) + 1
        shortfall = max(policy.target_size - len(selected), 0)
        identity = {
            "policy_hash": policy.policy_hash,
            "selected_example_ids": tuple(item.example_id for item in selected),
            "prediction_ids": tuple(sorted(item.prediction_id for item in predictions)),
        }
        return QualitySelectionResult(
            selection_id=canonical_hash(identity, prefix="quality_selection:"),
            policy_hash=policy.policy_hash,
            selected_example_ids=tuple(item.example_id for item in selected),
            rejected_by_contract_count=rejected_contract,
            rejected_by_vector_count=rejected_vector,
            rejected_by_critic_count=rejected_critic,
            stratum_counts=dict(sorted(stratum_counts.items())),
            status="complete" if not shortfall else "partial",
            shortfall=shortfall,
        )


def _stratum(
    example: QualityCriticExample,
    policy: QualitySelectionPolicy,
) -> str:
    values = {
        "domain": example.domain,
        "retrieval_track": example.retrieval_track,
        "planning_track": example.planning_track,
        "candidate_source": example.candidate_source,
    }
    return "|".join(
        str(values.get(field, example.metadata.get(field, "")))
        for field in policy.stratum_fields
    )
