
"""v25.24 static direction design for capability-sensitive submechanisms.

This stage is intentionally model-free.  It replaces label-level mechanism balance with a
typed, mechanically derived structural demand audit.  Flash remains blocked until every selected
submechanism has a real Host/Materializer implementation as well as passing structural geometry.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_mechanism_information_geometry import (  # noqa: E501
    CONFIRMED_MECHANISM_IDS,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_capability_sensitive_frontier import (
    CAPABILITY_AXES,
)
from trusted_synthesis.hashing import canonical_hash

SUBMECHANISM_DIRECTION_DESIGN_VERSION = "finance_capability_submechanism_direction_design.v1"
SUBMECHANISM_GRAPH_VERSION = "finance_capability_submechanism_action_graph.v1"
SUBMECHANISM_SPEC_VERSION = "finance_capability_submechanism_spec.v1"
SUBMECHANISM_REPORT_VERSION = "finance_capability_submechanism_direction_report.v1"

CapabilityPrimitive = Literal[
    "read_task",
    "retrieve",
    "retrieve_missing",
    "select_tool",
    "construct_arguments",
    "execute_tool",
    "observe_failure",
    "localize_failure",
    "repair_argument",
    "switch_tool",
    "calculate",
    "replay_calculation",
    "repair_operation_ref",
    "normalize_semantics",
    "compare_definition",
    "verify_candidate",
    "repair_candidate",
    "verify_evidence",
    "resolve_conflict",
    "assess_completeness",
    "assess_risk",
    "assess_cost",
    "continue_work",
    "stop",
]

EvidenceRelation = Literal[
    "selector_binding",
    "required_support",
    "prerequisite",
    "operation_lineage",
    "semantic_compatibility",
    "provenance",
    "conflict",
    "completeness",
    "alternative_tool_path",
]

DiagnosticOutcome = Literal["tool", "verification", "recovery", "stopping"]
RuntimeStatus = Literal["host_and_materializer_implemented", "requires_new_runtime_support"]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SubmechanismActionNode(FrozenModel):
    node_id: str = Field(min_length=1)
    primitive: CapabilityPrimitive
    depends_on: tuple[str, ...] = ()
    observation_dependencies: tuple[str, ...] = ()
    tool_id: str | None = None
    evidence_inputs: tuple[str, ...] = ()
    evidence_outputs: tuple[str, ...] = ()


class SubmechanismActionGraph(FrozenModel):
    graph_id: str = Field(min_length=1)
    nodes: tuple[SubmechanismActionNode, ...] = Field(min_length=3)
    terminal_node_id: str
    graph_depth: int = Field(ge=2)
    schema_version: str = SUBMECHANISM_GRAPH_VERSION

    @model_validator(mode="after")
    def validate_graph(self) -> SubmechanismActionGraph:
        known: set[str] = set()
        for node in self.nodes:
            if node.node_id in known:
                raise ValueError("submechanism graph duplicates a node")
            if not set(node.depends_on) <= known:
                raise ValueError("submechanism graph is not topologically ordered")
            if node.node_id in node.depends_on:
                raise ValueError("submechanism graph contains a self dependency")
            known.add(node.node_id)
        terminal = next(
            (node for node in self.nodes if node.node_id == self.terminal_node_id), None
        )
        if terminal is None or terminal.primitive != "stop":
            raise ValueError("submechanism graph lacks its typed terminal stop")
        if self.graph_depth != _graph_depth(self.nodes):
            raise ValueError("submechanism graph depth is inconsistent")
        if self.graph_id != _graph_id(self):
            raise ValueError("submechanism graph identity is invalid")
        return self


class EvidenceDependency(FrozenModel):
    dependency_id: str = Field(min_length=1)
    upstream_role: str = Field(min_length=1)
    downstream_role: str = Field(min_length=1)
    relation: EvidenceRelation
    observation_bound: bool = True

    @model_validator(mode="after")
    def validate_dependency(self) -> EvidenceDependency:
        if self.upstream_role == self.downstream_role:
            raise ValueError("Evidence dependency cannot be reflexive")
        if self.dependency_id != _dependency_id(self):
            raise ValueError("Evidence dependency identity is invalid")
        return self


class SubmechanismRuntimeContract(FrozenModel):
    intervention_kind: str = Field(min_length=1)
    trigger_node_id: str = Field(min_length=1)
    resolution_node_id: str = Field(min_length=1)
    required_host_events: tuple[str, ...] = Field(min_length=2)
    implementation_status: RuntimeStatus
    implementation_id: str | None = None

    @model_validator(mode="after")
    def validate_runtime(self) -> SubmechanismRuntimeContract:
        implemented = self.implementation_status == "host_and_materializer_implemented"
        if implemented != (self.implementation_id is not None):
            raise ValueError("submechanism runtime implementation identity is inconsistent")
        if len(set(self.required_host_events)) != len(self.required_host_events):
            raise ValueError("submechanism runtime contract duplicates a Host event")
        return self


class CapabilitySubmechanismSpec(FrozenModel):
    submechanism_id: str = Field(min_length=1)
    parent_mechanism_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    action_graph: SubmechanismActionGraph
    evidence_dependencies: tuple[EvidenceDependency, ...] = Field(min_length=1)
    runtime_contract: SubmechanismRuntimeContract
    diagnostic_outcomes: tuple[DiagnosticOutcome, ...] = Field(min_length=1)
    raw_capability_demand: dict[str, float]
    capability_witnesses: dict[str, tuple[str, ...]]
    backbone_signature: str = Field(min_length=1)
    spec_hash: str = Field(min_length=1)
    schema_version: str = SUBMECHANISM_SPEC_VERSION

    @model_validator(mode="after")
    def validate_spec(self) -> CapabilitySubmechanismSpec:
        if self.parent_mechanism_id not in CONFIRMED_MECHANISM_IDS:
            raise ValueError("submechanism belongs to an unconfirmed parent mechanism")
        node_ids = {node.node_id for node in self.action_graph.nodes}
        if {
            self.runtime_contract.trigger_node_id,
            self.runtime_contract.resolution_node_id,
        } - node_ids:
            raise ValueError("submechanism runtime contract points outside its action graph")
        expected_demand, expected_witnesses = _derive_capability_demand(
            self.action_graph, self.evidence_dependencies
        )
        if self.raw_capability_demand != expected_demand:
            raise ValueError("submechanism demand is not mechanically derived")
        if self.capability_witnesses != expected_witnesses:
            raise ValueError("submechanism capability witnesses are inconsistent")
        if self.backbone_signature != _backbone_signature(self.action_graph):
            raise ValueError("submechanism backbone signature is invalid")
        if self.spec_hash != _spec_hash(self):
            raise ValueError("submechanism identity is invalid")
        return self


class StructuralDirectionThresholds(FrozenModel):
    candidates_per_parent: int = Field(default=6, ge=5)
    selected_per_parent: int = Field(default=5, ge=3)
    minimum_residual_rank: int = Field(default=5, ge=1, le=6)
    minimum_residual_effective_rank: float = Field(default=4.0, ge=1, le=6)
    maximum_residual_condition_number: float = Field(default=100.0, gt=1)
    maximum_high_cosine_fraction: float = Field(default=0.35, ge=0, le=1)
    high_cosine_threshold: float = Field(default=0.90, ge=0, le=1)
    minimum_parent_support_per_axis: int = Field(default=2, ge=1, le=4)
    minimum_distinct_backbones: int = Field(default=10, ge=2)
    maximum_backbone_share: float = Field(default=0.20, gt=0, le=1)
    regularization: float = Field(default=1e-6, gt=0)


class StructuralDirectionGeometry(FrozenModel):
    task_count: int = Field(ge=1)
    raw_matrix: tuple[tuple[float, ...], ...]
    residual_matrix: tuple[tuple[float, ...], ...]
    raw_eigenvalues: tuple[float, ...]
    residual_eigenvalues: tuple[float, ...]
    residual_numerical_rank: int = Field(ge=0)
    residual_effective_rank: float = Field(ge=0)
    residual_condition_number: float = Field(ge=1)
    regularized_log_determinant: float
    minimum_positive_eigenvalue: float = Field(ge=0)
    pairwise_cosine_mean: float = Field(ge=-1, le=1)
    high_cosine_fraction: float = Field(ge=0, le=1)
    parent_support_per_axis: dict[str, int]
    distinct_backbone_count: int = Field(ge=1)
    maximum_backbone_share: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def validate_geometry(self) -> StructuralDirectionGeometry:
        size = len(CAPABILITY_AXES)
        for matrix in (self.raw_matrix, self.residual_matrix):
            if len(matrix) != size or any(len(row) != size for row in matrix):
                raise ValueError("submechanism structural matrix shape is invalid")
        if set(self.parent_support_per_axis) != set(CAPABILITY_AXES):
            raise ValueError("submechanism axis support is incomplete")
        return self


class StructuralDirectionGate(FrozenModel):
    gate_id: str = Field(min_length=1)
    observed: float
    requirement: str = Field(min_length=1)
    passed: bool


class CapabilitySubmechanismDirectionReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_geometry_report_path: str = Field(min_length=1)
    source_geometry_report_sha256: str = Field(min_length=64, max_length=64)
    source_geometry_report_id: str = Field(min_length=1)
    candidate_specs: tuple[CapabilitySubmechanismSpec, ...] = Field(min_length=1)
    selected_submechanism_ids: tuple[str, ...] = Field(min_length=1)
    selected_geometry: StructuralDirectionGeometry
    executable_selected_submechanism_ids: tuple[str, ...]
    gates: tuple[StructuralDirectionGate, ...] = Field(min_length=8)
    structural_geometry_ready: bool
    runtime_population_ready: bool
    multi_output_diagnostic_preregistered: bool
    api_calls: Literal[0] = 0
    model_tokens: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    failure_codes: tuple[str, ...]
    next_permitted_stage: Literal[
        "flash_submechanism_development",
        "submechanism_runtime_implementation_only",
        "submechanism_direction_redesign_only",
    ]
    implementation_manifest: dict[str, str]
    implementation_manifest_hash: str = Field(min_length=1)
    schema_version: str = SUBMECHANISM_REPORT_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> CapabilitySubmechanismDirectionReport:
        selected = tuple(
            item
            for item in self.candidate_specs
            if item.submechanism_id in set(self.selected_submechanism_ids)
        )
        if len(selected) != len(self.selected_submechanism_ids):
            raise ValueError("submechanism selection contains an unknown or duplicate identity")
        structural = all(gate.passed for gate in self.gates)
        if self.structural_geometry_ready != structural:
            raise ValueError("submechanism structural readiness is inconsistent")
        executable = tuple(
            item.submechanism_id
            for item in selected
            if item.runtime_contract.implementation_status
            == "host_and_materializer_implemented"
        )
        if self.executable_selected_submechanism_ids != executable:
            raise ValueError("submechanism executable selection is inconsistent")
        runtime_ready = structural and len(executable) == len(selected)
        if self.runtime_population_ready != runtime_ready:
            raise ValueError("submechanism Runtime readiness is inconsistent")
        expected_stage = (
            "flash_submechanism_development"
            if runtime_ready
            else (
                "submechanism_runtime_implementation_only"
                if structural
                else "submechanism_direction_redesign_only"
            )
        )
        if self.next_permitted_stage != expected_stage:
            raise ValueError("submechanism stage transition is not fail-closed")
        expected_manifest_hash = canonical_hash(
            self.implementation_manifest,
            prefix="finance_capability_submechanism_implementation:",
        )
        if self.implementation_manifest_hash != expected_manifest_hash:
            raise ValueError("submechanism implementation manifest hash is invalid")
        if self.report_id != _report_id(self):
            raise ValueError("submechanism direction report identity is invalid")
        return self


# Frozen, domain-level ontology.  Values describe structural demand witnesses, not outcomes.
_PRIMITIVE_WEIGHTS: dict[str, dict[str, float]] = {
    "read_task": {},
    "retrieve": {"retrieval": 1.0},
    "retrieve_missing": {"retrieval": 0.9, "planning": 0.2, "recovery": 0.5},
    "select_tool": {"retrieval": 0.2, "planning": 1.0},
    "construct_arguments": {"planning": 0.8},
    "execute_tool": {"retrieval": 0.25, "planning": 0.1},
    "observe_failure": {"verification": 0.25, "recovery": 0.55},
    "localize_failure": {"planning": 0.25, "verification": 0.25, "recovery": 0.75},
    "repair_argument": {"planning": 0.35, "recovery": 1.0},
    "switch_tool": {"retrieval": 0.25, "planning": 0.65, "recovery": 0.85},
    "calculate": {"calculation": 1.0, "planning": 0.1},
    "replay_calculation": {"calculation": 0.75, "verification": 0.8},
    "repair_operation_ref": {"planning": 0.35, "calculation": 0.65, "recovery": 0.9},
    "normalize_semantics": {"reconciliation": 1.0, "verification": 0.2},
    "compare_definition": {"reconciliation": 0.9, "verification": 0.55},
    "verify_candidate": {"calculation": 0.15, "verification": 1.0},
    "repair_candidate": {"verification": 0.3, "recovery": 0.65},
    "verify_evidence": {"verification": 1.0},
    "resolve_conflict": {"reconciliation": 1.0, "verification": 0.4, "recovery": 0.45},
    "assess_completeness": {"verification": 0.5, "stopping": 0.9},
    "assess_risk": {"verification": 0.35, "stopping": 1.0},
    "assess_cost": {"planning": 0.25, "stopping": 1.0},
    "continue_work": {"planning": 0.35, "stopping": 0.4},
    "stop": {},
}

_EVIDENCE_RELATION_WEIGHTS: dict[str, dict[str, float]] = {
    "selector_binding": {"retrieval": 0.1, "planning": 0.2},
    "required_support": {"retrieval": 0.15, "verification": 0.25},
    "prerequisite": {"planning": 0.2, "calculation": 0.3, "recovery": 0.15},
    "operation_lineage": {"calculation": 0.35, "verification": 0.1},
    "semantic_compatibility": {"reconciliation": 0.4, "verification": 0.1},
    "provenance": {"retrieval": 0.15, "verification": 0.2},
    "conflict": {"reconciliation": 0.4, "verification": 0.2, "recovery": 0.15},
    "completeness": {"verification": 0.15, "stopping": 0.4},
    "alternative_tool_path": {"retrieval": 0.1, "planning": 0.3, "recovery": 0.2},
}


def _graph_depth(nodes: Sequence[SubmechanismActionNode]) -> int:
    depth: dict[str, int] = {}
    for node in nodes:
        depth[node.node_id] = 1 + max((depth[item] for item in node.depends_on), default=0)
    return max(depth.values())


def _graph_id(value: SubmechanismActionGraph) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"graph_id"}),
        prefix="finance_capability_submechanism_action_graph:",
    )


def _dependency_id(value: EvidenceDependency) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"dependency_id"}),
        prefix="finance_capability_submechanism_evidence_dependency:",
    )


def _spec_hash(value: CapabilitySubmechanismSpec) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"spec_hash"}),
        prefix="finance_capability_submechanism_spec:",
    )


def _report_id(value: CapabilitySubmechanismDirectionReport) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_capability_submechanism_direction_report:",
    )


def _node(
    node_id: str,
    primitive: CapabilityPrimitive,
    depends_on: tuple[str, ...] = (),
    *,
    tool_id: str | None = None,
    observations: tuple[str, ...] = (),
    inputs: tuple[str, ...] = (),
    outputs: tuple[str, ...] = (),
) -> SubmechanismActionNode:
    return SubmechanismActionNode(
        node_id=node_id,
        primitive=primitive,
        depends_on=depends_on,
        tool_id=tool_id,
        observation_dependencies=observations,
        evidence_inputs=inputs,
        evidence_outputs=outputs,
    )


def _graph(nodes: Sequence[SubmechanismActionNode]) -> SubmechanismActionGraph:
    values = {
        "nodes": tuple(nodes),
        "terminal_node_id": "stop",
        "graph_depth": _graph_depth(nodes),
    }
    provisional = SubmechanismActionGraph.model_construct(graph_id="pending", **values)
    return SubmechanismActionGraph(graph_id=_graph_id(provisional), **values)


def _dependency(
    upstream: str,
    downstream: str,
    relation: EvidenceRelation,
    *,
    observation_bound: bool = True,
) -> EvidenceDependency:
    values = {
        "upstream_role": upstream,
        "downstream_role": downstream,
        "relation": relation,
        "observation_bound": observation_bound,
    }
    provisional = EvidenceDependency.model_construct(dependency_id="pending", **values)
    return EvidenceDependency(dependency_id=_dependency_id(provisional), **values)


def _derive_capability_demand(
    graph: SubmechanismActionGraph,
    dependencies: Sequence[EvidenceDependency],
) -> tuple[dict[str, float], dict[str, tuple[str, ...]]]:
    values = {axis: 0.0 for axis in CAPABILITY_AXES}
    witnesses: dict[str, list[str]] = {axis: [] for axis in CAPABILITY_AXES}
    for node in graph.nodes:
        for axis, weight in _PRIMITIVE_WEIGHTS[node.primitive].items():
            values[axis] += weight
            witnesses[axis].append(f"action:{node.node_id}:{node.primitive}")
        if len(node.depends_on) > 1:
            values["planning"] += 0.25 * (len(node.depends_on) - 1)
            witnesses["planning"].append(f"join:{node.node_id}")
        if node.observation_dependencies:
            values["planning"] += 0.08 * len(node.observation_dependencies)
            witnesses["planning"].append(f"observation:{node.node_id}")
    for dependency in dependencies:
        for axis, weight in _EVIDENCE_RELATION_WEIGHTS[dependency.relation].items():
            values[axis] += weight
            witnesses[axis].append(
                f"evidence:{dependency.upstream_role}->{dependency.downstream_role}:"
                f"{dependency.relation}"
            )
        if dependency.observation_bound:
            values["planning"] += 0.05
            witnesses["planning"].append(f"observation_bound:{dependency.dependency_id}")
    rounded = {axis: round(values[axis], 9) for axis in CAPABILITY_AXES}
    frozen_witnesses = {axis: tuple(sorted(set(witnesses[axis]))) for axis in CAPABILITY_AXES}
    if any(not frozen_witnesses[axis] for axis, value in rounded.items() if value > 0):
        raise AssertionError("positive structural demand lacks a typed witness")
    return rounded, frozen_witnesses


def _backbone_signature(graph: SubmechanismActionGraph) -> str:
    payload = {
        "primitives": tuple(
            node.primitive for node in graph.nodes if node.primitive not in {"read_task", "stop"}
        ),
        "tools": tuple(node.tool_id for node in graph.nodes if node.tool_id is not None),
        "dependency_arities": tuple(len(node.depends_on) for node in graph.nodes),
    }
    return canonical_hash(payload, prefix="finance_capability_submechanism_backbone:")


def _runtime(
    kind: str,
    trigger: str,
    resolution: str,
    events: tuple[str, ...],
    *,
    implementation_id: str | None = None,
) -> SubmechanismRuntimeContract:
    return SubmechanismRuntimeContract(
        intervention_kind=kind,
        trigger_node_id=trigger,
        resolution_node_id=resolution,
        required_host_events=events,
        implementation_status=(
            "host_and_materializer_implemented"
            if implementation_id is not None
            else "requires_new_runtime_support"
        ),
        implementation_id=implementation_id,
    )


def _spec(
    parent: str,
    key: str,
    title: str,
    graph: SubmechanismActionGraph,
    dependencies: tuple[EvidenceDependency, ...],
    runtime: SubmechanismRuntimeContract,
    diagnostics: tuple[DiagnosticOutcome, ...],
) -> CapabilitySubmechanismSpec:
    demand, witnesses = _derive_capability_demand(graph, dependencies)
    values = {
        "submechanism_id": f"{parent}.{key}",
        "parent_mechanism_id": parent,
        "title": title,
        "action_graph": graph,
        "evidence_dependencies": dependencies,
        "runtime_contract": runtime,
        "diagnostic_outcomes": diagnostics,
        "raw_capability_demand": demand,
        "capability_witnesses": witnesses,
        "backbone_signature": _backbone_signature(graph),
    }
    provisional = CapabilitySubmechanismSpec.model_construct(spec_hash="pending", **values)
    return CapabilitySubmechanismSpec(spec_hash=_spec_hash(provisional), **values)



def _linear_graph(
    steps: Sequence[tuple[str, CapabilityPrimitive, str | None]],
) -> SubmechanismActionGraph:
    nodes = [_node("read_task", "read_task")]
    anchor = "read_task"
    observation_primitives = {
        "observe_failure",
        "localize_failure",
        "repair_argument",
        "switch_tool",
        "repair_operation_ref",
        "repair_candidate",
        "resolve_conflict",
        "assess_completeness",
        "assess_risk",
        "assess_cost",
        "continue_work",
    }
    for node_id, primitive, tool_id in steps:
        nodes.append(
            _node(
                node_id,
                primitive,
                (anchor,),
                tool_id=tool_id,
                observations=("previous Host observation",)
                if primitive in observation_primitives
                else (),
            )
        )
        anchor = node_id
    nodes.append(_node("stop", "stop", (anchor,)))
    return _graph(nodes)


def _two_source_graph(
    *,
    resolution_primitive: CapabilityPrimitive,
    post_resolution_primitive: CapabilityPrimitive,
) -> SubmechanismActionGraph:
    nodes = (
        _node("read_task", "read_task"),
        _node(
            "retrieve_primary",
            "retrieve",
            ("read_task",),
            tool_id="query_structured_fact",
        ),
        _node(
            "retrieve_alternative",
            "retrieve",
            ("read_task",),
            tool_id="search_archive",
        ),
        _node(
            "resolve_two_sources",
            resolution_primitive,
            ("retrieve_primary", "retrieve_alternative"),
            tool_id="normalize_metric_unit_period",
            observations=("both source observations",),
        ),
        _node(
            "post_resolution_check",
            post_resolution_primitive,
            ("resolve_two_sources",),
            tool_id="cross_check_evidence",
            observations=("source resolution",),
        ),
        _node("stop", "stop", ("post_resolution_check",)),
    )
    return _graph(nodes)


def _dep(key: str, relation: EvidenceRelation) -> EvidenceDependency:
    return _dependency(f"{key}_input", f"{key}_output", relation)
