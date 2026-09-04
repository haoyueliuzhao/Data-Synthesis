from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.canonical_json import strict_canonical_hash
from trusted_synthesis.core.operations.registry import OperationRegistry
from trusted_synthesis.core.task.program import TaskProgram


class ProgramDepthMetrics(BaseModel):
    """Four non-interchangeable depth measures for one exact public Program."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    metrics_id: str = Field(min_length=1)
    program_id: str = Field(min_length=1)
    program_hash: str = Field(min_length=1)
    registry_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_node_id: str = Field(min_length=1)
    node_count: int = Field(ge=1)
    output_ancestor_node_count: int = Field(ge=1)
    transparent_projection_node_count: int = Field(ge=0)
    semantic_operation_node_count: int = Field(ge=0)
    structural_dependency_depth: int = Field(ge=1)
    semantic_operation_depth: int = Field(ge=0)
    workflow_interaction_depth: int = Field(ge=2)
    evidence_resolution_stage_count: int = Field(default=1, ge=1, le=1)
    independent_verification_stage_count: int = Field(default=1, ge=1, le=1)
    structural_depth_by_node: dict[str, int] = Field(min_length=1)
    semantic_depth_by_node: dict[str, int] = Field(min_length=1)
    output_dependency_closed: bool = True
    plan_template_stage_counted: bool = False
    answer_template_stage_counted: bool = False
    schema_version: str = "program_depth_metrics.v1"

    @model_validator(mode="after")
    def validate_metrics(self) -> ProgramDepthMetrics:
        if (
            not self.output_dependency_closed
            or self.output_ancestor_node_count != self.node_count
            or self.transparent_projection_node_count + self.semantic_operation_node_count
            != self.node_count
            or set(self.structural_depth_by_node) != set(self.semantic_depth_by_node)
            or len(self.structural_depth_by_node) != self.node_count
            or self.structural_dependency_depth
            != self.structural_depth_by_node[self.output_node_id]
            or self.semantic_operation_depth != self.semantic_depth_by_node[self.output_node_id]
            or self.workflow_interaction_depth
            != self.evidence_resolution_stage_count
            + self.semantic_operation_depth
            + self.independent_verification_stage_count
            or self.plan_template_stage_counted
            or self.answer_template_stage_counted
        ):
            raise ValueError("Program depth metrics are internally inconsistent")
        expected = strict_canonical_hash(
            self.model_dump(mode="python", exclude={"metrics_id"}),
            prefix="program_depth_metrics:",
        )
        if self.metrics_id != expected:
            raise ValueError("Program depth metrics identity differs")
        return self


def derive_program_depth_metrics(
    program: TaskProgram,
    registry: OperationRegistry,
) -> ProgramDepthMetrics:
    """Derive source-program depth without treating lookup projections as reasoning."""

    nodes = {node.node_id: node for node in program.nodes}
    ancestors = _output_ancestors(program)
    if ancestors != set(nodes):
        extras = tuple(sorted(set(nodes) - ancestors))
        raise ValueError(f"Program contains nodes outside output dependency closure: {extras}")

    structural: dict[str, int] = {}
    semantic: dict[str, int] = {}
    transparent_count = 0
    semantic_count = 0
    for node in program.nodes:
        definition = registry.require(node.operator_id)
        structural[node.node_id] = 1 + max(
            (structural[parent] for parent in node.dependencies), default=0
        )
        if definition.program_role == "transparent_projection":
            role_weight = 0
            transparent_count += 1
        elif definition.program_role == "semantic":
            role_weight = 1
            semantic_count += 1
        else:
            raise ValueError(
                f"Program operation has unsupported depth role: {definition.program_role}"
            )
        semantic[node.node_id] = role_weight + max(
            (semantic[parent] for parent in node.dependencies), default=0
        )

    registry_manifest_sha256 = strict_canonical_hash(
        registry.manifest(), prefix="program_depth_registry_manifest:"
    ).rsplit(":", maxsplit=1)[-1]
    values = {
        "program_id": program.program_id,
        "program_hash": program.program_hash,
        "registry_manifest_sha256": registry_manifest_sha256,
        "output_node_id": program.output_node_id,
        "node_count": len(program.nodes),
        "output_ancestor_node_count": len(ancestors),
        "transparent_projection_node_count": transparent_count,
        "semantic_operation_node_count": semantic_count,
        "structural_dependency_depth": structural[program.output_node_id],
        "semantic_operation_depth": semantic[program.output_node_id],
        "workflow_interaction_depth": 1 + semantic[program.output_node_id] + 1,
        "evidence_resolution_stage_count": 1,
        "independent_verification_stage_count": 1,
        "structural_depth_by_node": structural,
        "semantic_depth_by_node": semantic,
        "output_dependency_closed": True,
        "plan_template_stage_counted": False,
        "answer_template_stage_counted": False,
        "schema_version": "program_depth_metrics.v1",
    }
    return ProgramDepthMetrics(
        metrics_id=strict_canonical_hash(values, prefix="program_depth_metrics:"),
        **values,
    )


def admit_program_depth_metrics(
    *,
    expected_program: TaskProgram,
    candidate_program: TaskProgram,
    candidate_metrics: ProgramDepthMetrics,
    registry: OperationRegistry,
) -> ProgramDepthMetrics:
    """Require an exact source Program and independently rederive its four metrics."""

    derived = derive_program_depth_metrics(candidate_program, registry)
    if (
        candidate_program != expected_program
        or candidate_program.program_id != expected_program.program_id
        or candidate_program.program_hash != expected_program.program_hash
    ):
        raise ValueError("candidate Program differs from exact source Program")
    if candidate_metrics != derived:
        raise ValueError("candidate depth metrics differ from independent derivation")
    return derived


def _output_ancestors(program: TaskProgram) -> set[str]:
    nodes = {node.node_id: node for node in program.nodes}
    ancestors: set[str] = set()
    pending = [program.output_node_id]
    while pending:
        node_id = pending.pop()
        if node_id in ancestors:
            continue
        ancestors.add(node_id)
        pending.extend(nodes[node_id].dependencies)
    return ancestors
