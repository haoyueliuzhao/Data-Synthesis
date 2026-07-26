from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash


class ActionType(str, Enum):
    PLAN = "plan"
    SEARCH = "search"
    SELECT_EVIDENCE = "select_evidence"
    CALCULATE = "calculate"
    VERIFY = "verify"
    ANSWER = "answer"


class StepStatus(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class TrajectoryStep(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    step_index: int = Field(ge=1)
    action: ActionType
    tool_name: str | None = None
    tool_input: dict[str, Any] = Field(default_factory=dict)
    observation: dict[str, Any] = Field(default_factory=dict)
    evidence_ids: tuple[str, ...] = ()
    rationale_summary: str = Field(min_length=1)
    status: StepStatus


class Trajectory(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    trajectory_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    steps: tuple[TrajectoryStep, ...] = Field(min_length=1)
    final_answer: dict[str, Any]
    generator_version: str

    @model_validator(mode="after")
    def validate_step_order(self) -> Trajectory:
        indexes = [step.step_index for step in self.steps]
        if indexes != list(range(1, len(indexes) + 1)):
            raise ValueError("trajectory step indexes must be contiguous and one-based")
        if self.steps[0].action != ActionType.PLAN:
            raise ValueError("trajectory must begin with a plan")
        if self.steps[-1].action != ActionType.ANSWER:
            raise ValueError("trajectory must end with an answer")
        return self

    @property
    def trajectory_hash(self) -> str:
        return canonical_hash(self, prefix="trajectory:")
