from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.task.program import InputRefKind, TaskProgram
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
    SEMI_OPEN = "semi_open"
    OPEN = "open"


class PlanningTrack(str, Enum):
    PLAN_GIVEN = "plan_given"
    PLAN_HIDDEN = "plan_hidden"


class VerifierRequirement(str, Enum):
    REQUIRED = "required"
    NOT_APPLICABLE = "not_applicable"


_ORACLE_ONLY_PUBLIC_KEYS = frozenset(
    {
        "evidence_ids",
        "gold_evidence_ids",
        "evidence_version_ids",
        "source_ids",
        "required_build_ids",
        "domain_context_hashes",
        "payload_context_hashes",
        "bundle_id",
        "proof_graph_id",
        "proof_graph_hash",
        "program_id",
    }
)


class PublicProgramInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: InputRefKind
    role_id: str = Field(min_length=1)
    selector: str | None = None
    semantic_constraints: dict[str, Any] = Field(default_factory=dict)


class PublicProgramNode(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    public_node_id: str = Field(min_length=1)
    operator_id: str = Field(min_length=1)
    inputs: tuple[PublicProgramInput, ...] = Field(min_length=1)
    parameters: dict[str, Any] = Field(default_factory=dict)
    output_schema: str = Field(min_length=1)
    dependencies: tuple[str, ...] = ()
    tool_capability: str | None = None


class PublicProgramSkeleton(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    skeleton_version: str = "public_program_skeleton.v1"
    nodes: tuple[PublicProgramNode, ...] = Field(min_length=1)
    output_node_id: str = Field(min_length=1)


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
    planning_track: PlanningTrack = PlanningTrack.PLAN_GIVEN
    program_skeleton: PublicProgramSkeleton | None = None
    retrieval_scope: dict[str, Any]
    answer_schema: dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_retrieval_contract(self) -> TaskPublicSpec:
        if self.planning_track == PlanningTrack.PLAN_GIVEN and self.program_skeleton is None:
            raise ValueError("plan-given tasks require a public program skeleton")
        if self.planning_track == PlanningTrack.PLAN_HIDDEN and self.program_skeleton is not None:
            raise ValueError("plan-hidden tasks cannot expose a program skeleton")
        if self.retrieval_track == RetrievalTrack.SEMI_OPEN:
            has_partial = bool(
                self.retrieval_scope.get("aliases")
                or self.retrieval_scope.get("partial_constraints")
            )
            if not has_partial or not self.retrieval_scope.get("corpus_boundary"):
                raise ValueError(
                    "semi-open retrieval requires partial constraints and a corpus boundary"
                )
        if self.retrieval_track == RetrievalTrack.OPEN and not self.retrieval_scope.get(
            "corpus_boundary"
        ):
            raise ValueError("open retrieval requires a corpus boundary")
        public_contract = {
            "retrieval_scope": self.retrieval_scope,
            "answer_schema": self.answer_schema,
            "metadata": self.metadata,
            "program_skeleton": (
                self.program_skeleton.model_dump(mode="json")
                if self.program_skeleton is not None
                else None
            ),
        }
        leaked_keys = _find_keys(public_contract) & _ORACLE_ONLY_PUBLIC_KEYS
        if leaked_keys:
            raise ValueError(
                f"public contract contains oracle-only keys: {sorted(leaked_keys)}"
            )
        return self


class TaskOracleContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    task_id: str = Field(min_length=1)
    gold_evidence_ids: tuple[str, ...] = Field(min_length=1)
    task_program: TaskProgram
    selection_contract: dict[str, Any] = Field(default_factory=dict)
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


def _find_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return {
            *(str(key) for key in value),
            *(item for nested in value.values() for item in _find_keys(nested)),
        }
    if isinstance(value, (list, tuple)):
        return {item for nested in value for item in _find_keys(nested)}
    return set()
