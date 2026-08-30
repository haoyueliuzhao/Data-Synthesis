from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evaluation.schema import QualityAssessment
from trusted_synthesis.core.evidence.corpus import EvidenceCorpus
from trusted_synthesis.core.task.realization import (
    RealizationPortfolio,
    RealizedTaskPackage,
)
from trusted_synthesis.core.trajectory.schema import Trajectory
from trusted_synthesis.hashing import canonical_hash


class TrajectoryExecutionDescriptor(BaseModel):
    """Exact, replayable generator input/output identity for one realization."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    descriptor_id: str = Field(min_length=1)
    realized_package_id: str = Field(min_length=1)
    public_task_hash: str = Field(min_length=1)
    evidence_corpus_id: str = Field(min_length=1)
    evidence_corpus_hash: str = Field(min_length=1)
    generation_input_hash: str = Field(min_length=1)
    generator_contract_id: str = Field(min_length=1)
    generated_trajectory: Trajectory
    generated_trajectory_hash: str = Field(min_length=1)
    bound_trajectory_id: str = Field(min_length=1)
    bound_trajectory_hash: str = Field(min_length=1)
    schema_version: str = "trajectory_execution_descriptor.v1"

    @model_validator(mode="after")
    def validate_identity(self) -> TrajectoryExecutionDescriptor:
        Trajectory.model_validate(
            self.generated_trajectory.model_dump(mode="python", warnings=False)
        )
        if self.generated_trajectory_hash != self.generated_trajectory.trajectory_hash:
            raise ValueError("generated trajectory hash is not derived")
        expected_bound_id = canonical_hash(
            {
                "realized_package_id": self.realized_package_id,
                "generation_input_hash": self.generation_input_hash,
                "generator_contract_id": self.generator_contract_id,
                "generated_trajectory_hash": self.generated_trajectory_hash,
                "schema_version": "realized_candidate_trajectory.v2",
            },
            prefix="realized_candidate_trajectory:",
        )
        if self.bound_trajectory_id != expected_bound_id:
            raise ValueError("bound trajectory identity is not derived")
        rebound = self.generated_trajectory.model_copy(
            update={"trajectory_id": self.bound_trajectory_id}
        )
        if self.bound_trajectory_hash != rebound.trajectory_hash:
            raise ValueError("bound trajectory hash is not derived")
        expected = canonical_hash(
            self.model_dump(mode="json", exclude={"descriptor_id"}),
            prefix="trajectory_execution_descriptor:",
        )
        if self.descriptor_id != expected:
            raise ValueError("trajectory execution descriptor identity is invalid")
        return self


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
    execution_descriptor: TrajectoryExecutionDescriptor
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
        TrajectoryExecutionDescriptor.model_validate(
            self.execution_descriptor.model_dump(mode="python", warnings=False)
        )
        if self.execution_descriptor.realized_package_id != self.realized_package_id:
            raise ValueError("execution descriptor crosses its realized package")
        if (
            self.execution_descriptor.bound_trajectory_id != self.trajectory_id
            or self.execution_descriptor.bound_trajectory_hash != self.trajectory_hash
        ):
            raise ValueError("execution descriptor crosses its bound trajectory")
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
    execution_descriptor: TrajectoryExecutionDescriptor,
) -> RealizationExecutionBinding:
    RealizedTaskPackage.model_validate(realized.model_dump(mode="python", warnings=False))
    RealizationPortfolio.model_validate(portfolio.model_dump(mode="python", warnings=False))
    Trajectory.model_validate(trajectory.model_dump(mode="python", warnings=False))
    QualityAssessment.model_validate(assessment.model_dump(mode="python", warnings=False))
    TrajectoryExecutionDescriptor.model_validate(
        execution_descriptor.model_dump(mode="python", warnings=False)
    )
    if trajectory.task_id != realized.task.task_id:
        raise ValueError("trajectory task identity mismatch")
    if assessment.task_id != realized.task.task_id:
        raise ValueError("quality assessment task identity mismatch")
    if assessment.trajectory_id != trajectory.trajectory_id:
        raise ValueError("quality assessment trajectory identity mismatch")
    expected_public_task_hash = canonical_hash(
        realized.task.public,
        prefix="generation_public_task:",
    )
    if execution_descriptor.public_task_hash != expected_public_task_hash:
        raise ValueError("execution descriptor crosses its public task")
    if execution_descriptor.realized_package_id != realized.realized_package_id:
        raise ValueError("execution descriptor crosses its realized package")
    rebound = execution_descriptor.generated_trajectory.model_copy(
        update={"trajectory_id": execution_descriptor.bound_trajectory_id}
    )
    if trajectory != rebound:
        raise ValueError("trajectory is not the exact descriptor-bound generator output")
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
        "execution_descriptor": execution_descriptor,
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


def describe_generated_trajectory(
    realized: RealizedTaskPackage,
    corpus: EvidenceCorpus,
    generated_trajectory: Trajectory,
    *,
    generator_contract_id: str,
) -> tuple[Trajectory, TrajectoryExecutionDescriptor]:
    """Bind a deterministic generator output to its exact realization and corpus."""

    RealizedTaskPackage.model_validate(realized.model_dump(mode="python", warnings=False))
    EvidenceCorpus.model_validate(corpus.model_dump(mode="python", warnings=False))
    Trajectory.model_validate(generated_trajectory.model_dump(mode="python", warnings=False))
    if generated_trajectory.task_id != realized.task.task_id:
        raise ValueError("generated trajectory task identity mismatch")
    public_task_hash = canonical_hash(
        realized.task.public,
        prefix="generation_public_task:",
    )
    generation_input_hash = canonical_hash(
        {
            "realized_package_id": realized.realized_package_id,
            "public_task_hash": public_task_hash,
            "evidence_corpus_id": corpus.corpus_id,
            "evidence_corpus_hash": corpus.corpus_hash,
            "generator_contract_id": generator_contract_id,
            "schema_version": "trajectory_generation_input.v1",
        },
        prefix="trajectory_generation_input:",
    )
    bound_trajectory_id = canonical_hash(
        {
            "realized_package_id": realized.realized_package_id,
            "generation_input_hash": generation_input_hash,
            "generator_contract_id": generator_contract_id,
            "generated_trajectory_hash": generated_trajectory.trajectory_hash,
            "schema_version": "realized_candidate_trajectory.v2",
        },
        prefix="realized_candidate_trajectory:",
    )
    bound = generated_trajectory.model_copy(update={"trajectory_id": bound_trajectory_id})
    payload = {
        "realized_package_id": realized.realized_package_id,
        "public_task_hash": public_task_hash,
        "evidence_corpus_id": corpus.corpus_id,
        "evidence_corpus_hash": corpus.corpus_hash,
        "generation_input_hash": generation_input_hash,
        "generator_contract_id": generator_contract_id,
        "generated_trajectory": generated_trajectory,
        "generated_trajectory_hash": generated_trajectory.trajectory_hash,
        "bound_trajectory_id": bound.trajectory_id,
        "bound_trajectory_hash": bound.trajectory_hash,
        "schema_version": "trajectory_execution_descriptor.v1",
    }
    provisional = TrajectoryExecutionDescriptor.model_construct(
        descriptor_id="pending",
        **payload,
    )
    descriptor_id = canonical_hash(
        provisional.model_dump(mode="json", exclude={"descriptor_id"}),
        prefix="trajectory_execution_descriptor:",
    )
    return bound, TrajectoryExecutionDescriptor(descriptor_id=descriptor_id, **payload)
