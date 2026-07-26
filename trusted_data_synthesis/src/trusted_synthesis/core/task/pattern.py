from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evidence.payloads import EvidenceKind
from trusted_synthesis.core.task.schema import (
    PlanningTrack,
    RetrievalTrack,
    TaskLevel,
    VerifierRequirement,
)
from trusted_synthesis.hashing import canonical_hash


class PatternInputKind(str, Enum):
    EVIDENCE_ROLE = "evidence_role"
    CURRENT_EVIDENCE = "current_evidence"
    OPERATION_NODE = "operation_node"
    OPERATION_GROUP = "operation_group"


class EvidenceRoleSpec(BaseModel):
    """A typed, cardinality-bounded evidence slot declared by a task pattern."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    role_id: str = Field(min_length=1)
    accepted_kinds: tuple[EvidenceKind, ...] = Field(min_length=1)
    min_count: int = Field(default=1, ge=1)
    max_count: int | None = Field(default=1, ge=1)
    semantic_constraints: tuple[str, ...] = ()
    temporal_constraints: tuple[str, ...] = ()
    scope_constraints: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_cardinality(self) -> EvidenceRoleSpec:
        if self.max_count is not None and self.max_count < self.min_count:
            raise ValueError("evidence role max_count must be at least min_count")
        if len(set(self.accepted_kinds)) != len(self.accepted_kinds):
            raise ValueError("evidence role contains duplicate accepted kinds")
        return self


class PatternInputRef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: PatternInputKind
    ref_id: str = Field(min_length=1)
    selector: str | None = None


class ProgramNodeTemplate(BaseModel):
    """A declarative operation node, optionally expanded once per role binding."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    node_role_id: str = Field(min_length=1)
    operator_id: str = Field(min_length=1)
    input_refs: tuple[PatternInputRef, ...] = Field(min_length=1)
    parameters: dict[str, Any] = Field(default_factory=dict)
    output_schema: str = Field(min_length=1)
    foreach_evidence_role: str | None = None


class TaskPatternSpec(BaseModel):
    """Versioned domain declaration compiled into a concrete universal task package."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    pattern_id: str = Field(min_length=1)
    pattern_version: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    task_type: str = Field(min_length=1)
    level: TaskLevel
    evidence_roles: tuple[EvidenceRoleSpec, ...] = Field(min_length=1)
    program_template: tuple[ProgramNodeTemplate, ...] = Field(min_length=1)
    output_node_role_id: str = Field(min_length=1)
    answer_schema: dict[str, Any]
    instruction_renderer_id: str = Field(min_length=1)
    quality_profile_id: str = Field(min_length=1)
    retrieval_track: RetrievalTrack = RetrievalTrack.RESOLVED
    planning_track: PlanningTrack = PlanningTrack.PLAN_GIVEN
    source_grounding_requirement: VerifierRequirement = VerifierRequirement.NOT_APPLICABLE
    allow_structured_claims: bool = False
    cross_role_constraints: tuple[str, ...] = ()
    difficulty_base: str = Field(default="medium", pattern="^(easy|medium|hard|expert|research)$")
    difficulty_base_cost: float = Field(default=2.0, ge=0)
    allow_shared_evidence: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
    schema_version: str = "task_pattern.v1"

    @model_validator(mode="after")
    def validate_pattern(self) -> TaskPatternSpec:
        role_ids = [role.role_id for role in self.evidence_roles]
        if len(role_ids) != len(set(role_ids)):
            raise ValueError("task pattern contains duplicate evidence role IDs")
        node_role_ids = [node.node_role_id for node in self.program_template]
        if len(node_role_ids) != len(set(node_role_ids)):
            raise ValueError("task pattern contains duplicate program node role IDs")
        known_roles = set(role_ids)
        seen_nodes: dict[str, ProgramNodeTemplate] = {}
        for node in self.program_template:
            if node.foreach_evidence_role is not None:
                if node.foreach_evidence_role not in known_roles:
                    raise ValueError(
                        f"foreach role is not declared: {node.foreach_evidence_role}"
                    )
            for ref in node.input_refs:
                if ref.kind == PatternInputKind.CURRENT_EVIDENCE:
                    if node.foreach_evidence_role is None:
                        raise ValueError(
                            "current_evidence inputs are only valid on foreach nodes"
                        )
                    if ref.ref_id != node.foreach_evidence_role:
                        raise ValueError(
                            "current_evidence must refer to the node foreach role"
                        )
                elif ref.kind == PatternInputKind.EVIDENCE_ROLE:
                    if ref.ref_id not in known_roles:
                        raise ValueError(f"unknown evidence role reference: {ref.ref_id}")
                elif ref.kind == PatternInputKind.OPERATION_NODE:
                    target = seen_nodes.get(ref.ref_id)
                    if target is None:
                        raise ValueError(f"operation node reference is not prior: {ref.ref_id}")
                    if target.foreach_evidence_role is not None:
                        raise ValueError(
                            "operation_node cannot refer to a foreach template; use operation_group"
                        )
                elif ref.kind == PatternInputKind.OPERATION_GROUP:
                    target = seen_nodes.get(ref.ref_id)
                    if target is None:
                        raise ValueError(f"operation group reference is not prior: {ref.ref_id}")
                    if target.foreach_evidence_role is None:
                        raise ValueError(
                            "operation_group must refer to a foreach program template"
                        )
            seen_nodes[node.node_role_id] = node
        output = seen_nodes.get(self.output_node_role_id)
        if output is None:
            raise ValueError("task pattern output node role is missing")
        if output.foreach_evidence_role is not None:
            raise ValueError("task pattern output must resolve to one operation node")
        return self

    @property
    def pattern_hash(self) -> str:
        return canonical_hash(self, prefix="task_pattern:")

    @property
    def semantic_constraint_count(self) -> int:
        return len(self.cross_role_constraints) + sum(
            len(role.semantic_constraints)
            + len(role.temporal_constraints)
            + len(role.scope_constraints)
            for role in self.evidence_roles
        )


class PatternBindingValidationReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    passed: bool
    checks: dict[str, bool]
    issues: tuple[str, ...] = ()
    semantic_alignment_cost: float = Field(default=0.0, ge=0)


class TaskPatternMaterialization(BaseModel):
    """Domain-owned language and public/oracle packaging around a compiled program."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    instruction: str = Field(min_length=1)
    retrieval_scope: dict[str, Any]
    answer_schema: dict[str, Any] = Field(default_factory=dict)
    oracle_selection_contract: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    quality_rubric: dict[str, Any] = Field(default_factory=dict)

