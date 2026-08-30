from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evaluation.schema import QualityAssessment
from trusted_synthesis.core.task.realization import (
    RealizationPortfolio,
    RealizedTaskPackage,
)
from trusted_synthesis.core.trajectory.schema import Trajectory
from trusted_synthesis.hashing import canonical_hash


class RealizationExecutionBinding(BaseModel):
    """Content-addressed link from one selected realization to its exact evaluation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    execution_binding_id: str = Field(min_length=1)
    realized_package_id: str = Field(min_length=1)
    semantic_schema_id: str = Field(min_length=1)
    semantic_instance_id: str = Field(min_length=1)
    binding_snapshot_id: str = Field(min_length=1)
    realization_id: str = Field(min_length=1)
    realized_task_hash: str = Field(min_length=1)
    realization_portfolio_id: str = Field(min_length=1)
    realization_portfolio: RealizationPortfolio
    trajectory_id: str = Field(min_length=1)
    trajectory_hash: str = Field(min_length=1)
    quality_assessment_id: str = Field(min_length=1)
    quality_assessment_hash: str = Field(min_length=1)
    evaluator_contract_id: str = Field(min_length=1)
    schema_version: str = "realization_execution_binding.v1"

    @model_validator(mode="after")
    def validate_identity(self) -> RealizationExecutionBinding:
        RealizationPortfolio.model_validate(
            self.realization_portfolio.model_dump(mode="python", warnings=False)
        )
        if self.realization_portfolio_id != self.realization_portfolio.portfolio_id:
            raise ValueError("execution binding crosses its RealizationPortfolio identity")
        if (
            self.semantic_schema_id != self.realization_portfolio.semantic_schema_id
            or self.semantic_instance_id != self.realization_portfolio.semantic_instance_id
            or self.binding_snapshot_id != self.realization_portfolio.binding_snapshot_id
        ):
            raise ValueError("execution binding crosses its RealizationPortfolio lineage")
        try:
            selected_index = self.realization_portfolio.selected_realized_package_ids.index(
                self.realized_package_id
            )
        except ValueError as exc:
            raise ValueError("execution binding package is not selected by its portfolio") from exc
        if (
            self.realization_portfolio.selected_realization_ids[selected_index]
            != self.realization_id
        ):
            raise ValueError("execution binding package/realization portfolio pair is invalid")
        expected = canonical_hash(
            self.model_dump(mode="json", exclude={"execution_binding_id"}),
            prefix="realization_execution_binding:",
        )
        if self.execution_binding_id != expected:
            raise ValueError("realization execution binding identity is invalid")
        return self


def bind_realization_execution(
    realized: RealizedTaskPackage,
    portfolio: RealizationPortfolio,
    trajectory: Trajectory,
    assessment: QualityAssessment,
) -> RealizationExecutionBinding:
    RealizedTaskPackage.model_validate(realized.model_dump(mode="python", warnings=False))
    RealizationPortfolio.model_validate(portfolio.model_dump(mode="python", warnings=False))
    Trajectory.model_validate(trajectory.model_dump(mode="python", warnings=False))
    QualityAssessment.model_validate(assessment.model_dump(mode="python", warnings=False))
    if trajectory.task_id != realized.task.task_id:
        raise ValueError("trajectory task identity mismatch")
    if assessment.task_id != realized.task.task_id:
        raise ValueError("quality assessment task identity mismatch")
    if assessment.trajectory_id != trajectory.trajectory_id:
        raise ValueError("quality assessment trajectory identity mismatch")
    evaluator_contract_id = canonical_hash(
        {
            "evaluator_version": assessment.evaluator_version,
            "required_check_manifest_hash": assessment.required_check_manifest_hash,
            "quality_assessment_schema_version": assessment.schema_version,
        },
        prefix="evaluator_contract:",
    )
    payload = {
        "realized_package_id": realized.realized_package_id,
        "semantic_schema_id": realized.semantic_plan.semantic_task_id,
        "semantic_instance_id": realized.semantic_instance_id,
        "binding_snapshot_id": realized.binding_snapshot_id,
        "realization_id": realized.realization.realization_id,
        "realized_task_hash": realized.task.task_hash,
        "realization_portfolio_id": portfolio.portfolio_id,
        "realization_portfolio": portfolio,
        "trajectory_id": trajectory.trajectory_id,
        "trajectory_hash": trajectory.trajectory_hash,
        "quality_assessment_id": assessment.assessment_id,
        "quality_assessment_hash": assessment.assessment_hash,
        "evaluator_contract_id": evaluator_contract_id,
        "schema_version": "realization_execution_binding.v1",
    }
    provisional = RealizationExecutionBinding.model_construct(
        execution_binding_id="pending",
        **payload,
    )
    execution_binding_id = canonical_hash(
        provisional.model_dump(mode="json", exclude={"execution_binding_id"}),
        prefix="realization_execution_binding:",
    )
    return RealizationExecutionBinding(
        execution_binding_id=execution_binding_id,
        **payload,
    )
