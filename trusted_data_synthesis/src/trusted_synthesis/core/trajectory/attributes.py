from __future__ import annotations

from collections import Counter
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.task.program import TaskProgram
from trusted_synthesis.core.trajectory.schema import ActionType, StepStatus, Trajectory
from trusted_synthesis.hashing import canonical_hash

TRAJECTORY_ATTRIBUTE_SCHEMA_VERSION = "trajectory_attributes.v1"

CapabilityTag = Literal[
    "retrieval",
    "evidence_selection",
    "multi_step_reasoning",
    "verification",
    "citation",
]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class TrajectoryAttributes(FrozenModel):
    """Observable behavior descriptors; they are not a trajectory template."""

    attribute_id: str = Field(min_length=1)
    tool_call_count: int = Field(ge=0)
    tool_depth: int = Field(ge=0)
    reasoning_depth: int = Field(ge=0)
    evidence_dependency_count: int = Field(ge=0)
    verification_degree: float = Field(ge=0, le=1)
    branching_factor: int = Field(ge=0)
    operation_count: int = Field(ge=0)
    capability_tags: tuple[CapabilityTag, ...] = ()
    schema_version: str = TRAJECTORY_ATTRIBUTE_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_identity(self) -> TrajectoryAttributes:
        if len(self.capability_tags) != len(set(self.capability_tags)):
            raise ValueError("trajectory capability tags must be unique")
        if self.attribute_id != trajectory_attribute_id(self):
            raise ValueError("trajectory attribute identity is invalid")
        return self

    @property
    def profile(self) -> TrajectoryAttributeProfile:
        return make_trajectory_attribute_profile(self)


class TrajectoryAttributeProfile(FrozenModel):
    """A finite, auditable bucketization used by the synthesis policy."""

    profile_id: str = Field(min_length=1)
    tool_depth_bucket: str = Field(min_length=1)
    reasoning_depth_bucket: str = Field(min_length=1)
    evidence_dependency_bucket: str = Field(min_length=1)
    verification_degree_bucket: str = Field(min_length=1)
    branching_factor_bucket: str = Field(min_length=1)
    operation_count_bucket: str = Field(min_length=1)
    capability_tags: tuple[CapabilityTag, ...] = ()
    schema_version: str = TRAJECTORY_ATTRIBUTE_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_identity(self) -> TrajectoryAttributeProfile:
        if len(self.capability_tags) != len(set(self.capability_tags)):
            raise ValueError("trajectory profile capability tags must be unique")
        if self.profile_id != trajectory_attribute_profile_id(self):
            raise ValueError("trajectory attribute profile identity is invalid")
        return self


def extract_trajectory_attributes(
    trajectory: Trajectory,
    program: TaskProgram,
) -> TrajectoryAttributes:
    """Measure a realized trajectory without prescribing how it must be written."""

    successful = tuple(step for step in trajectory.steps if step.status == StepStatus.SUCCEEDED)
    tool_steps = tuple(step for step in successful if step.tool_name is not None)
    verification_steps = tuple(
        step for step in trajectory.steps if step.action == ActionType.VERIFY
    )
    selected_ids = {
        evidence_id
        for step in successful
        if step.action in {ActionType.SELECT_EVIDENCE, ActionType.CALCULATE, ActionType.VERIFY}
        for evidence_id in step.evidence_ids
    }
    reasoning_depth = _program_depth(program)
    operation_count = sum(
        step.program_node_id is not None
        and step.action in {ActionType.SELECT_EVIDENCE, ActionType.CALCULATE}
        for step in successful
    )
    if operation_count == 0:
        operation_count = len(program.nodes)
    verification_degree = (
        sum(step.status == StepStatus.SUCCEEDED for step in verification_steps)
        / len(verification_steps)
        if verification_steps
        else 0.0
    )
    actions = {step.action for step in successful}
    capability_tags: list[CapabilityTag] = []
    if ActionType.SEARCH in actions:
        capability_tags.append("retrieval")
    if ActionType.SELECT_EVIDENCE in actions:
        capability_tags.append("evidence_selection")
    if reasoning_depth > 1 or operation_count > 1:
        capability_tags.append("multi_step_reasoning")
    if verification_degree > 0:
        capability_tags.append("verification")
    if trajectory.final_answer.get("citations"):
        capability_tags.append("citation")
    values = {
        "tool_call_count": len(tool_steps),
        "tool_depth": _tool_depth(trajectory, reasoning_depth),
        "reasoning_depth": reasoning_depth,
        "evidence_dependency_count": len(selected_ids),
        "verification_degree": verification_degree,
        "branching_factor": _branching_factor(program),
        "operation_count": operation_count,
        "capability_tags": tuple(sorted(capability_tags)),
        "schema_version": TRAJECTORY_ATTRIBUTE_SCHEMA_VERSION,
    }
    provisional = TrajectoryAttributes.model_construct(attribute_id="pending", **values)
    return TrajectoryAttributes(attribute_id=trajectory_attribute_id(provisional), **values)


def expected_trajectory_attributes(program: TaskProgram) -> TrajectoryAttributes:
    """Describe the minimum executable behavior implied by an Oracle program."""

    evidence_ids = {
        ref.ref_id
        for node in program.nodes
        for ref in node.input_refs
        if ref.kind.value == "evidence"
    }
    depth = _program_depth(program)
    tags: list[CapabilityTag] = ["evidence_selection", "verification", "citation"]
    if depth > 1 or len(program.nodes) > 1:
        tags.append("multi_step_reasoning")
    values = {
        "tool_call_count": len(program.nodes) + 2,
        "tool_depth": depth + 2,
        "reasoning_depth": depth,
        "evidence_dependency_count": len(evidence_ids),
        "verification_degree": 1.0,
        "branching_factor": _branching_factor(program),
        "operation_count": len(program.nodes),
        "capability_tags": tuple(sorted(tags)),
        "schema_version": TRAJECTORY_ATTRIBUTE_SCHEMA_VERSION,
    }
    provisional = TrajectoryAttributes.model_construct(attribute_id="pending", **values)
    return TrajectoryAttributes(attribute_id=trajectory_attribute_id(provisional), **values)


def make_trajectory_attribute_profile(
    attributes: TrajectoryAttributes,
) -> TrajectoryAttributeProfile:
    values = {
        "tool_depth_bucket": _count_bucket(attributes.tool_depth),
        "reasoning_depth_bucket": _count_bucket(attributes.reasoning_depth),
        "evidence_dependency_bucket": _count_bucket(attributes.evidence_dependency_count),
        "verification_degree_bucket": _verification_bucket(attributes.verification_degree),
        "branching_factor_bucket": _count_bucket(attributes.branching_factor),
        "operation_count_bucket": _count_bucket(attributes.operation_count),
        "capability_tags": attributes.capability_tags,
        "schema_version": attributes.schema_version,
    }
    provisional = TrajectoryAttributeProfile.model_construct(profile_id="pending", **values)
    return TrajectoryAttributeProfile(
        profile_id=trajectory_attribute_profile_id(provisional),
        **values,
    )


def trajectory_attribute_id(value: TrajectoryAttributes) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"attribute_id"}),
        prefix="trajectory_attributes:",
    )


def trajectory_attribute_profile_id(value: TrajectoryAttributeProfile) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"profile_id"}),
        prefix="trajectory_attribute_profile:",
    )


def profile_distribution(
    attributes: tuple[TrajectoryAttributes, ...],
) -> dict[str, int]:
    return dict(sorted(Counter(item.profile.profile_id for item in attributes).items()))


def _program_depth(program: TaskProgram) -> int:
    depths: dict[str, int] = {}
    for node in program.nodes:
        depths[node.node_id] = 1 + max(
            (depths[dependency] for dependency in node.dependencies),
            default=0,
        )
    return max(depths.values(), default=0)


def _branching_factor(program: TaskProgram) -> int:
    child_counts = Counter(
        dependency for node in program.nodes for dependency in node.dependencies
    )
    fan_out = max(child_counts.values(), default=0)
    fan_in = max((len(node.dependencies) for node in program.nodes), default=0)
    return max(fan_in, fan_out)


def _tool_depth(trajectory: Trajectory, reasoning_depth: int) -> int:
    search = any(
        step.action == ActionType.SEARCH
        and step.status == StepStatus.SUCCEEDED
        and step.tool_name is not None
        for step in trajectory.steps
    )
    verify = any(
        step.action == ActionType.VERIFY
        and step.status == StepStatus.SUCCEEDED
        and step.tool_name is not None
        for step in trajectory.steps
    )
    return reasoning_depth + int(search) + int(verify)


def _count_bucket(value: int) -> str:
    if value == 0:
        return "0"
    if value == 1:
        return "1"
    if value <= 3:
        return "2-3"
    if value <= 7:
        return "4-7"
    return "8+"


def _verification_bucket(value: float) -> str:
    if value == 0:
        return "none"
    if value < 1:
        return "partial"
    return "complete"
