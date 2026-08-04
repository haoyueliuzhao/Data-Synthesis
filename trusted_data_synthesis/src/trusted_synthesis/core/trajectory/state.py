from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.trajectory.attributes import (
    TrajectoryAttributes,
    extract_trajectory_attributes,
)
from trusted_synthesis.core.trajectory.schema import ActionType, Trajectory, TrajectoryStep
from trusted_synthesis.core.trajectory.specification import (
    OmegaComponentManifest,
    TrajectoryVerificationContext,
    make_omega_component_manifest,
)
from trusted_synthesis.hashing import canonical_hash

TRAJECTORY_STATE_SCHEMA_VERSION = "trajectory_quotient_state.v5"
TRAJECTORY_CANONICALIZER_VERSION = "dependency_wl_canonicalizer.v6"
TRAJECTORY_DECISION_TRACE_VERSION = "trajectory_decision_trace.v2"

NodeClassKind = Literal["action", "evidence"]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class CanonicalNodeClass(FrozenModel):
    """One color class in the dependency-preserving canonical graph."""

    signature: str = Field(min_length=1)
    kind: NodeClassKind
    semantic_label: str = Field(min_length=1)
    semantic_payload_hash: str = Field(min_length=1)
    multiplicity: int = Field(ge=1)


class CanonicalEdgeClass(FrozenModel):
    source_signature: str = Field(min_length=1)
    relation: str = Field(min_length=1)
    target_signature: str = Field(min_length=1)
    multiplicity: int = Field(ge=1)


class CanonicalTrajectoryGraph(FrozenModel):
    """Order-invariant graph approximation to Can_Omega(trajectory)."""

    graph_id: str = Field(min_length=1)
    node_classes: tuple[CanonicalNodeClass, ...] = Field(min_length=1)
    edge_classes: tuple[CanonicalEdgeClass, ...] = ()
    canonicalization_method: str = "dependency_wl_multiset"
    schema_version: str = TRAJECTORY_STATE_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_identity(self) -> CanonicalTrajectoryGraph:
        signatures = [item.signature for item in self.node_classes]
        if len(signatures) != len(set(signatures)):
            raise ValueError("canonical graph contains duplicate node classes")
        known = set(signatures)
        if any(
            edge.source_signature not in known or edge.target_signature not in known
            for edge in self.edge_classes
        ):
            raise ValueError("canonical graph contains a dangling edge class")
        if self.graph_id != canonical_trajectory_graph_id(self):
            raise ValueError("canonical trajectory graph identity is invalid")
        return self


class TrajectoryState(FrozenModel):
    """Finite structural approximation to z = [trajectory]_{~ Omega_x}."""

    state_id: str = Field(min_length=1)
    task_condition_id: str = Field(min_length=1)
    omega_context_id: str = Field(min_length=1)
    omega_component_manifest: OmegaComponentManifest
    canonicalizer_version: str = TRAJECTORY_CANONICALIZER_VERSION
    canonical_graph: CanonicalTrajectoryGraph
    operation_graph_hash: str = Field(min_length=1)
    evidence_lineage_hash: str = Field(min_length=1)
    result_semantics_hash: str = Field(min_length=1)
    schema_version: str = TRAJECTORY_STATE_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_identity(self) -> TrajectoryState:
        if self.canonicalizer_version != TRAJECTORY_CANONICALIZER_VERSION:
            raise ValueError("trajectory state uses another canonicalizer version")
        if self.canonical_graph.schema_version != self.schema_version:
            raise ValueError("trajectory state and canonical graph schemas disagree")
        if self.state_id != trajectory_state_id(self):
            raise ValueError("trajectory state identity is invalid")
        return self


class TrajectoryStateAssignment(FrozenModel):
    """Auditable push-forward assignment phi_x(trajectory) = state."""

    assignment_id: str = Field(min_length=1)
    task_condition_id: str = Field(min_length=1)
    trajectory_id: str = Field(min_length=1)
    trajectory_hash: str = Field(min_length=1)
    state: TrajectoryState
    attributes: TrajectoryAttributes
    schema_version: str = TRAJECTORY_STATE_SCHEMA_VERSION

    @model_validator(mode="after")
    def validate_identity(self) -> TrajectoryStateAssignment:
        if self.task_condition_id != self.state.task_condition_id:
            raise ValueError("state assignment crosses task conditions")
        if self.assignment_id != trajectory_state_assignment_id(self):
            raise ValueError("trajectory state assignment identity is invalid")
        return self


@dataclass(frozen=True)
class _RawNode:
    key: str
    kind: NodeClassKind
    semantic_label: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class _RawEdge:
    source: str
    relation: str
    target: str


def map_trajectory_to_state(
    context: TrajectoryVerificationContext,
    trajectory: Trajectory,
    *,
    task_condition_id: str | None = None,
    program_node_aliases: Mapping[str, str] | None = None,
    tool_equivalence: Mapping[str, str] | None = None,
) -> TrajectoryStateAssignment:
    """Map one linear execution to an order-invariant structural state.

    Program aliases map candidate node IDs to the pinned Oracle node IDs. Tool aliases
    may collapse deployment-specific names only when the caller has frozen their semantic
    equivalence. Neither mapping is inferred from surface text.
    """

    if trajectory.task_id != context.task.task_id:
        raise ValueError("trajectory state mapping received another task")
    condition_id = task_condition_id or context.task.task_id
    aliases = dict(program_node_aliases or {})
    tools = dict(tool_equivalence or {})
    raw_nodes, raw_edges = _dependency_graph(
        context,
        trajectory,
        aliases=aliases,
        tool_equivalence=tools,
    )
    canonical_graph = _canonicalize(raw_nodes, raw_edges)
    operation_graph_hash = _subgraph_hash(
        canonical_graph,
        node_kinds={"action"},
        label_prefixes=(
            ActionType.SELECT_EVIDENCE.value,
            ActionType.CALCULATE.value,
            ActionType.VERIFY.value,
        ),
    )
    evidence_lineage_hash = _subgraph_hash(
        canonical_graph,
        node_kinds={"evidence"},
        include_incident_edges=True,
    )
    result_hash = canonical_hash(
        _semantic_result(trajectory.final_answer, aliases=aliases),
        prefix="trajectory_result_semantics:",
    )
    values = {
        "task_condition_id": condition_id,
        "omega_context_id": context.context_id,
        "omega_component_manifest": make_omega_component_manifest(context),
        "canonicalizer_version": TRAJECTORY_CANONICALIZER_VERSION,
        "canonical_graph": canonical_graph,
        "operation_graph_hash": operation_graph_hash,
        "evidence_lineage_hash": evidence_lineage_hash,
        "result_semantics_hash": result_hash,
        "schema_version": TRAJECTORY_STATE_SCHEMA_VERSION,
    }
    provisional_state = TrajectoryState.model_construct(state_id="pending", **values)
    state = TrajectoryState(state_id=trajectory_state_id(provisional_state), **values)
    assignment_values = {
        "task_condition_id": condition_id,
        "trajectory_id": trajectory.trajectory_id,
        "trajectory_hash": trajectory.trajectory_hash,
        "state": state,
        "attributes": extract_trajectory_attributes(
            trajectory,
            context.task.oracle.task_program,
        ),
        "schema_version": TRAJECTORY_STATE_SCHEMA_VERSION,
    }
    provisional_assignment = TrajectoryStateAssignment.model_construct(
        assignment_id="pending",
        **assignment_values,
    )
    return TrajectoryStateAssignment(
        assignment_id=trajectory_state_assignment_id(provisional_assignment),
        **assignment_values,
    )


def canonical_trajectory_graph_id(value: CanonicalTrajectoryGraph) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"graph_id"}),
        prefix="canonical_trajectory_graph:",
    )


def trajectory_state_id(value: TrajectoryState) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"state_id"}),
        prefix="trajectory_state:",
    )


def trajectory_state_assignment_id(value: TrajectoryStateAssignment) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"assignment_id"}),
        prefix="trajectory_state_assignment:",
    )


def trajectory_decision_trace_hash(
    trajectory: Trajectory,
    *,
    program_node_aliases: Mapping[str, str] | None = None,
    tool_equivalence: Mapping[str, str] | None = None,
) -> str:
    """Hash executable decisions while erasing IDs, timestamps, and rationale text."""

    aliases = dict(program_node_aliases or {})
    tools = dict(tool_equivalence or {})
    decisions = []
    for step in trajectory.steps:
        tool = step.tool_name
        if tool is not None:
            tool = tools.get(tool, tool)
        if step.operator_id is not None:
            tool = f"operator:{step.operator_id}"
        decisions.append(
            {
                "action": step.action.value,
                "tool_capability": tool,
                "tool_parameters": _strip_execution_metadata(step.tool_input),
                "evidence_ids": tuple(sorted(step.evidence_ids)),
                "program_role": _canonical_program_role(step.program_node_id, aliases),
                "operator_id": step.operator_id,
                "input_refs": tuple(
                    sorted(
                        item
                        for item in (_normalize_ref(ref, aliases) for ref in step.input_refs)
                        if item is not None
                    )
                ),
                "output_ref": _normalize_ref(step.output_ref, aliases),
                "status": step.status.value,
            }
        )
    ordered = tuple(
        sorted(
            decisions,
            key=lambda item: canonical_hash(item, prefix="trajectory_decision_node:"),
        )
    )
    return canonical_hash(
        {
            "task_id": trajectory.task_id,
            "decisions": ordered,
            "version": TRAJECTORY_DECISION_TRACE_VERSION,
        },
        prefix="trajectory_decision_trace:",
    )


def _strip_execution_metadata(value: Any) -> Any:
    volatile = {
        "call_id",
        "execution_id",
        "request_id",
        "timestamp",
        "trace_id",
    }
    if isinstance(value, Mapping):
        return {
            str(key): _strip_execution_metadata(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            if str(key).casefold() not in volatile
        }
    if isinstance(value, (list, tuple)):
        return tuple(_strip_execution_metadata(item) for item in value)
    return value


def _public_corpus_size(context: TrajectoryVerificationContext) -> int | None:
    count = len(context.public_corpus.evidence)
    return count if count > 0 else None


def _retrieval_context_class(
    *,
    returned_evidence_ids: set[str],
    retained_evidence_ids: set[str],
    corpus_size: int | None,
) -> Literal["required_only", "contextual", "full_corpus"]:
    if not returned_evidence_ids - retained_evidence_ids:
        return "required_only"
    if corpus_size is not None and len(returned_evidence_ids) >= corpus_size:
        return "full_corpus"
    return "contextual"


def _dependency_graph(
    context: TrajectoryVerificationContext,
    trajectory: Trajectory,
    *,
    aliases: Mapping[str, str],
    tool_equivalence: Mapping[str, str],
) -> tuple[tuple[_RawNode, ...], tuple[_RawEdge, ...]]:
    action_nodes: list[_RawNode] = []
    evidence_ids = {
        evidence_id
        for step in trajectory.steps
        if step.action != ActionType.SEARCH
        for evidence_id in step.evidence_ids
    }
    evidence_ids.update(_citation_evidence_ids(trajectory.final_answer))
    corpus_size = _public_corpus_size(context)
    retrieval_contexts = {
        step.step_index: _retrieval_context_class(
            returned_evidence_ids=set(step.evidence_ids),
            retained_evidence_ids=evidence_ids,
            corpus_size=corpus_size,
        )
        for step in trajectory.steps
        if step.action == ActionType.SEARCH
    }
    evidence_nodes = [
        _RawNode(
            key=f"evidence:{evidence_id}",
            kind="evidence",
            semantic_label=f"evidence:{evidence_id}",
            payload={"evidence_id": evidence_id},
        )
        for evidence_id in sorted(evidence_ids)
    ]
    retrieval_context_nodes = [
        _RawNode(
            key=f"retrieval_context:{step_index}",
            kind="evidence",
            semantic_label=f"retrieval_context:{context_class}",
            payload={"retrieval_context_class": context_class},
        )
        for step_index, context_class in sorted(retrieval_contexts.items())
        if context_class != "required_only"
    ]
    step_keys: dict[int, str] = {}
    role_to_step: dict[str, str] = {}
    output_to_step: dict[str, str] = {}
    for step in trajectory.steps:
        key = f"step:{step.step_index}"
        step_keys[step.step_index] = key
        role = _canonical_program_role(step.program_node_id, aliases)
        if role is not None and step.action in {
            ActionType.SELECT_EVIDENCE,
            ActionType.CALCULATE,
        }:
            if role in role_to_step:
                raise ValueError(f"trajectory executes program role more than once: {role}")
            role_to_step[role] = key
        normalized_output = _normalize_ref(step.output_ref, aliases)
        if normalized_output is not None:
            if normalized_output in output_to_step:
                raise ValueError(
                    f"trajectory publishes the same output more than once: {normalized_output}"
                )
            output_to_step[normalized_output] = key
        payload = _step_semantics(
            step,
            trajectory,
            aliases=aliases,
            tool_equivalence=tool_equivalence,
            retained_evidence_ids=evidence_ids,
            retrieval_context_class=retrieval_contexts.get(step.step_index),
        )
        action_nodes.append(
            _RawNode(
                key=key,
                kind="action",
                semantic_label=f"{step.action.value}:{role or 'lifecycle'}",
                payload=payload,
            )
        )
    edges: set[_RawEdge] = set()
    for step in trajectory.steps:
        target = step_keys[step.step_index]
        for evidence_id in sorted(set(step.evidence_ids) & evidence_ids):
            edges.add(_RawEdge(f"evidence:{evidence_id}", "uses_evidence", target))
        context_class = retrieval_contexts.get(step.step_index)
        if context_class is not None and context_class != "required_only":
            edges.add(_RawEdge(f"retrieval_context:{step.step_index}", "retrieval_context", target))
        for raw_ref in step.input_refs:
            normalized = _normalize_ref(raw_ref, aliases)
            if normalized is None:
                continue
            if normalized.startswith("evidence:"):
                evidence_id = normalized.split(":", 1)[1].split("#", 1)[0]
                if evidence_id in evidence_ids:
                    edges.add(
                        _RawEdge(
                            f"evidence:{evidence_id}",
                            "input_binding",
                            target,
                        )
                    )
            producer = output_to_step.get(normalized)
            if producer is None and normalized.startswith("operation:"):
                producer = role_to_step.get(normalized.split(":", 1)[1].split("#", 1)[0])
            if producer is not None:
                edges.add(_RawEdge(producer, "depends_on_output", target))
    program = context.task.oracle.task_program
    for node in program.nodes:
        operation_target = role_to_step.get(node.node_id)
        if operation_target is None:
            continue
        for dependency in node.dependencies:
            source = role_to_step.get(dependency)
            if source is not None:
                edges.add(_RawEdge(source, "program_dependency", operation_target))
    _add_lifecycle_edges(trajectory, step_keys, role_to_step, program.output_node_id, edges)
    return tuple((*evidence_nodes, *retrieval_context_nodes, *action_nodes)), tuple(
        sorted(edges, key=lambda item: (item.source, item.relation, item.target))
    )


def _add_lifecycle_edges(
    trajectory: Trajectory,
    step_keys: Mapping[int, str],
    role_to_step: Mapping[str, str],
    output_node_id: str,
    edges: set[_RawEdge],
) -> None:
    by_action: dict[ActionType, list[TrajectoryStep]] = defaultdict(list)
    for step in trajectory.steps:
        by_action[step.action].append(step)
    plans = by_action[ActionType.PLAN]
    searches = by_action[ActionType.SEARCH]
    selections = by_action[ActionType.SELECT_EVIDENCE]
    operations = [
        step
        for step in trajectory.steps
        if step.program_node_id is not None
        and step.action in {ActionType.SELECT_EVIDENCE, ActionType.CALCULATE}
    ]
    for search in searches:
        for plan in plans:
            edges.add(
                _RawEdge(
                    step_keys[plan.step_index],
                    "enables_retrieval",
                    step_keys[search.step_index],
                )
            )
    for selection in selections:
        compatible = [
            search
            for search in searches
            if not selection.evidence_ids
            or set(selection.evidence_ids).issubset(search.evidence_ids)
        ]
        for source in compatible or searches or plans:
            edges.add(
                _RawEdge(
                    step_keys[source.step_index],
                    "retrieval_selection",
                    step_keys[selection.step_index],
                )
            )
    for operation in operations:
        if not operation.input_refs:
            for selection in selections:
                edges.add(
                    _RawEdge(
                        step_keys[selection.step_index],
                        "selection_execution",
                        step_keys[operation.step_index],
                    )
                )
    output_step = role_to_step.get(output_node_id)
    verifications = by_action[ActionType.VERIFY]
    answers = by_action[ActionType.ANSWER]
    for verification in verifications:
        if output_step is not None:
            edges.add(
                _RawEdge(
                    output_step,
                    "verification_target",
                    step_keys[verification.step_index],
                )
            )
    answer_sources = verifications or (
        [next(step for step in trajectory.steps if step_keys[step.step_index] == output_step)]
        if output_step is not None
        else selections or searches or plans
    )
    for answer in answers:
        for source in answer_sources:
            edges.add(
                _RawEdge(
                    step_keys[source.step_index],
                    "answer_dependency",
                    step_keys[answer.step_index],
                )
            )


def _canonicalize(
    raw_nodes: tuple[_RawNode, ...],
    raw_edges: tuple[_RawEdge, ...],
) -> CanonicalTrajectoryGraph:
    nodes = {item.key: item for item in raw_nodes}
    if len(nodes) != len(raw_nodes):
        raise ValueError("trajectory dependency graph contains duplicate raw nodes")
    colors = {
        key: canonical_hash(
            {"kind": item.kind, "payload": item.payload},
            prefix="trajectory_state_initial_color:",
        )
        for key, item in nodes.items()
    }
    incoming: dict[str, list[tuple[str, str]]] = defaultdict(list)
    outgoing: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for edge in raw_edges:
        if edge.source not in nodes or edge.target not in nodes:
            raise ValueError("trajectory dependency graph contains a dangling raw edge")
        outgoing[edge.source].append((edge.relation, edge.target))
        incoming[edge.target].append((edge.relation, edge.source))
    for _ in range(max(1, len(nodes))):
        colors = {
            key: canonical_hash(
                {
                    "base": canonical_hash(
                        {"kind": node.kind, "payload": node.payload},
                        prefix="trajectory_state_node_base:",
                    ),
                    "incoming": sorted(
                        (relation, colors[source]) for relation, source in incoming.get(key, ())
                    ),
                    "outgoing": sorted(
                        (relation, colors[target]) for relation, target in outgoing.get(key, ())
                    ),
                },
                prefix="trajectory_state_refined_color:",
            )
            for key, node in nodes.items()
        }
    node_counter: Counter[tuple[str, str, str, str]] = Counter()
    for key, node in nodes.items():
        payload_hash = canonical_hash(
            node.payload,
            prefix="trajectory_state_semantic_payload:",
        )
        node_counter[(colors[key], node.kind, node.semantic_label, payload_hash)] += 1
    node_classes = tuple(
        CanonicalNodeClass(
            signature=signature,
            kind=kind,
            semantic_label=label,
            semantic_payload_hash=payload_hash,
            multiplicity=multiplicity,
        )
        for (signature, kind, label, payload_hash), multiplicity in sorted(node_counter.items())
    )
    edge_counter = Counter(
        (colors[edge.source], edge.relation, colors[edge.target]) for edge in raw_edges
    )
    edge_classes = tuple(
        CanonicalEdgeClass(
            source_signature=source,
            relation=relation,
            target_signature=target,
            multiplicity=multiplicity,
        )
        for (source, relation, target), multiplicity in sorted(edge_counter.items())
    )
    values = {
        "node_classes": node_classes,
        "edge_classes": edge_classes,
        "canonicalization_method": "dependency_wl_multiset",
        "schema_version": TRAJECTORY_STATE_SCHEMA_VERSION,
    }
    provisional = CanonicalTrajectoryGraph.model_construct(graph_id="pending", **values)
    return CanonicalTrajectoryGraph(
        graph_id=canonical_trajectory_graph_id(provisional),
        **values,
    )


def _step_semantics(
    step: TrajectoryStep,
    trajectory: Trajectory,
    *,
    aliases: Mapping[str, str],
    tool_equivalence: Mapping[str, str],
    retained_evidence_ids: set[str],
    retrieval_context_class: str | None,
) -> dict[str, Any]:
    role = _canonical_program_role(step.program_node_id, aliases)
    tool = step.tool_name
    if tool is not None:
        tool = tool_equivalence.get(tool, tool)
    if step.operator_id is not None:
        tool = f"operator:{step.operator_id}"
    semantic_evidence_ids = set(step.evidence_ids)
    if step.action == ActionType.SEARCH:
        semantic_evidence_ids &= retained_evidence_ids
    payload: dict[str, Any] = {
        "action": step.action.value,
        "tool_semantics": tool,
        "program_role": role,
        "operator_id": step.operator_id,
        "input_refs": tuple(
            sorted(
                item
                for item in (_normalize_ref(ref, aliases) for ref in step.input_refs)
                if item is not None
            )
        ),
        "output_ref": _normalize_ref(step.output_ref, aliases),
        "evidence_ids": tuple(sorted(semantic_evidence_ids)),
        "status": step.status.value,
    }
    if step.action == ActionType.SEARCH:
        payload["retrieval_context_class"] = retrieval_context_class or "required_only"
    if step.action in {ActionType.SELECT_EVIDENCE, ActionType.CALCULATE}:
        payload["result"] = _normalize_semantic_value(
            step.observation.get("result"),
            aliases=aliases,
        )
    elif step.action == ActionType.VERIFY:
        payload["verified_output_ref"] = _normalize_ref(
            step.observation.get("verified_output_ref"), aliases
        )
        payload["verified_result"] = _normalize_semantic_value(
            step.observation.get("verified_result"),
            aliases=aliases,
        )
    elif step.action == ActionType.ANSWER:
        payload["answer"] = _semantic_result(trajectory.final_answer, aliases=aliases)
    return payload


def _canonical_program_role(
    role: str | None,
    aliases: Mapping[str, str],
) -> str | None:
    return aliases.get(role, role) if role is not None else None


def _normalize_ref(
    value: object,
    aliases: Mapping[str, str],
) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    prefix, separator, remainder = value.partition(":")
    if not separator or prefix != "operation":
        return value
    node_id, selector_separator, selector = remainder.partition("#")
    normalized = f"operation:{aliases.get(node_id, node_id)}"
    return f"{normalized}#{selector}" if selector_separator else normalized


def _semantic_result(
    answer: Mapping[str, Any],
    *,
    aliases: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    citations = answer.get("citations")
    normalized_citations: tuple[tuple[str, str], ...] = ()
    if isinstance(citations, list):
        normalized_citations = tuple(
            sorted(
                (
                    str(item.get("evidence_id", "")),
                    str(item.get("source_id", "")),
                )
                for item in citations
                if isinstance(item, dict)
            )
        )
    return {
        "result": _normalize_semantic_value(answer.get("result"), aliases=aliases),
        "citation_bindings": normalized_citations,
    }


def _normalize_semantic_value(
    value: Any,
    *,
    aliases: Mapping[str, str] | None = None,
) -> Any:
    """Erase representation-only numeric differences from quotient semantics.

    Plain digit strings remain untouched because they may be identifiers. Decimal or
    exponent notation is unambiguous enough to canonicalize, while typed numbers are
    always numeric by construction.
    """

    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (int, float, Decimal)):
        return _canonical_decimal(value)
    if isinstance(value, str):
        alias_map = aliases or {}
        value = alias_map.get(value, value)
        if value.startswith("execution:"):
            node_id, separator, selector = value.removeprefix("execution:").partition("#")
            translated = alias_map.get(node_id)
            if translated is not None:
                value = f"{translated}#{selector}" if separator else translated
        candidate = value.strip()
        if "." not in candidate and "e" not in candidate.casefold():
            return value
        try:
            decimal_value = Decimal(candidate)
        except InvalidOperation:
            return value
        return _canonical_decimal(decimal_value)
    if isinstance(value, Mapping):
        return {
            key: _normalize_semantic_value(item, aliases=aliases)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_normalize_semantic_value(item, aliases=aliases) for item in value]
    if isinstance(value, tuple):
        return tuple(_normalize_semantic_value(item, aliases=aliases) for item in value)
    return value


def _canonical_decimal(value: int | float | Decimal) -> str | int | float | Decimal:
    try:
        decimal_value = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError, OverflowError):
        return value
    if not decimal_value.is_finite():
        return value
    if decimal_value == 0:
        return "0"
    normalized = format(decimal_value.normalize(), "f")
    if "." in normalized:
        normalized = normalized.rstrip("0").rstrip(".")
    return normalized


def _citation_evidence_ids(answer: Mapping[str, Any]) -> set[str]:
    citations = answer.get("citations")
    if not isinstance(citations, list):
        return set()
    return {
        str(item["evidence_id"])
        for item in citations
        if isinstance(item, dict) and item.get("evidence_id")
    }


def _subgraph_hash(
    graph: CanonicalTrajectoryGraph,
    *,
    node_kinds: set[NodeClassKind],
    label_prefixes: tuple[str, ...] = (),
    include_incident_edges: bool = False,
) -> str:
    selected = {
        item.signature
        for item in graph.node_classes
        if item.kind in node_kinds
        and (
            not label_prefixes
            or any(item.semantic_label.startswith(prefix) for prefix in label_prefixes)
        )
    }
    edges = tuple(
        item
        for item in graph.edge_classes
        if (item.source_signature in selected and item.target_signature in selected)
        or (
            include_incident_edges
            and (item.source_signature in selected or item.target_signature in selected)
        )
    )
    incident = selected | {
        signature for edge in edges for signature in (edge.source_signature, edge.target_signature)
    }
    nodes = tuple(item for item in graph.node_classes if item.signature in incident)
    return canonical_hash(
        {"nodes": nodes, "edges": edges},
        prefix="trajectory_state_subgraph:",
    )
