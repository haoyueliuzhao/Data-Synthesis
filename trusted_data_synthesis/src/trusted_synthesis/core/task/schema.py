from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.task.program import TaskProgram
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


class RetrievalTrack(str, Enum):
    RESOLVED = "resolved"
    OPEN = "open"


class TaskPublicSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    task_id: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    task_type: str = Field(min_length=1)
    level: TaskLevel
    instruction: str = Field(min_length=1)
    requirements: tuple[TaskRequirement, ...] = Field(min_length=1)
    allowed_tools: tuple[str, ...] = Field(min_length=1)
    retrieval_track: RetrievalTrack = RetrievalTrack.RESOLVED
    retrieval_scope: dict[str, Any]
    answer_schema: dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskOracleContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    task_id: str = Field(min_length=1)
    gold_evidence_ids: tuple[str, ...] = Field(min_length=1)
    task_program: TaskProgram
    proof_graph_id: str = Field(min_length=1)
    proof_graph_hash: str = Field(min_length=1)
    expected_output: dict[str, Any] | None = None
    quality_rubric: dict[str, Any] = Field(default_factory=dict)


class TaskPackage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    task_id: str = Field(min_length=1)
    public: TaskPublicSpec
    oracle: TaskOracleContract

    @model_validator(mode="after")
    def validate_identity(self) -> TaskPackage:
        if self.task_id != self.public.task_id or self.task_id != self.oracle.task_id:
            raise ValueError("public task and oracle contract identities must match")
        return self

    @property
    def task_hash(self) -> str:
        return canonical_hash(self, prefix="task:")
