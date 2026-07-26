from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash


class TaskLevel(str, Enum):
    FACT_RETRIEVAL = "fact_retrieval"
    EVIDENCE_INTEGRATION = "evidence_integration"
    RESEARCH_WORKFLOW = "research_workflow"


class TaskRequirement(str, Enum):
    RETRIEVE_EVIDENCE = "retrieve_evidence"
    SELECT_EVIDENCE = "select_evidence"
    CALCULATE = "calculate"
    CITE_SOURCE = "cite_source"
    VERIFY_RESULT = "verify_result"


class OperationSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    operator_id: str = Field(min_length=1)
    input_evidence_ids: tuple[str, ...] = Field(min_length=1)
    parameters: dict[str, Any] = Field(default_factory=dict)
    output_schema: str = Field(min_length=1)


class TaskSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    task_id: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    level: TaskLevel
    instruction: str = Field(min_length=1)
    requirements: tuple[TaskRequirement, ...] = Field(min_length=1)
    operation: OperationSpec
    evidence_bundle_id: str = Field(min_length=1)
    hidden_evidence_ids: tuple[str, ...] = Field(min_length=1)
    answer_schema: dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_inputs(self) -> TaskSpec:
        if not set(self.operation.input_evidence_ids).issubset(self.hidden_evidence_ids):
            raise ValueError("operation inputs must be present in hidden evidence IDs")
        return self

    @property
    def task_hash(self) -> str:
        return canonical_hash(self, prefix="task:")
