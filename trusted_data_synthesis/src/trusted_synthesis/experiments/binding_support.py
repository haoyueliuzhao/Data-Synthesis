from __future__ import annotations

from typing import Any

from trusted_synthesis.core.evidence.epistemic import EpistemicStatus
from trusted_synthesis.core.evidence.schema import EvidenceItem, SourceAuthority
from trusted_synthesis.core.refinement import SynthesisCell
from trusted_synthesis.core.task.binding import EvidenceBinding, make_evidence_binding
from trusted_synthesis.core.task.pattern import TaskPatternSpec
from trusted_synthesis.experiments.cross_domain_contract_suite.fixtures import ContractCase


def same_structural_cell(left: SynthesisCell, right: SynthesisCell) -> bool:
    return (
        left.pattern_id == right.pattern_id
        and left.binding_stratum_id == right.binding_stratum_id
        and left.difficulty_bucket == right.difficulty_bucket
        and left.distractor_profile_id == right.distractor_profile_id
    )


def reconstruct_binding(case: ContractCase, pattern: TaskPatternSpec) -> EvidenceBinding:
    """Reconstruct an immutable binding from a compiled task and frozen pattern."""

    identity = case.task.oracle.selection_contract.get("pattern_binding")
    if not isinstance(identity, dict):
        raise ValueError("task does not expose a Pattern Binding identity")
    role_bindings = identity.get("role_bindings")
    source_graph_id = identity.get("source_graph_id")
    if not isinstance(role_bindings, dict) or not isinstance(source_graph_id, str):
        raise ValueError("Pattern Binding identity is incomplete")
    binding = make_evidence_binding(
        pattern_id=pattern.pattern_id,
        pattern_version=pattern.pattern_version,
        pattern_hash=pattern.pattern_hash,
        role_bindings={
            str(role_id): tuple(str(value) for value in evidence_ids)
            for role_id, evidence_ids in role_bindings.items()
        },
        source_graph_id=source_graph_id,
        domain_snapshot_id=(
            str(identity["domain_snapshot_id"])
            if identity.get("domain_snapshot_id") is not None
            else None
        ),
        node_parameters=_reconstruct_node_parameters(case, pattern),
        binding_features={
            "reconstructed_from_task_id": case.task.task_id,
            "source_binding_id": identity.get("binding_id"),
        },
    )
    if set(binding.role_bindings) != {role.role_id for role in pattern.evidence_roles}:
        raise ValueError("reconstructed Binding roles do not match the frozen Pattern")
    return binding


def exclude_forecast(evidence: tuple[EvidenceItem, ...]) -> bool:
    return all(not bool(item.domain_context.get("is_forecast")) for item in evidence)


def require_current_version(evidence: tuple[EvidenceItem, ...]) -> bool:
    return all(item.epistemic_status != EpistemicStatus.SUPERSEDED for item in evidence)


def require_official_source(evidence: tuple[EvidenceItem, ...]) -> bool:
    return all(item.source.authority == SourceAuthority.OFFICIAL for item in evidence)


def require_same_definition(evidence: tuple[EvidenceItem, ...]) -> bool:
    values = {item.definition.definition_id for item in evidence}
    return len(values) == 1 and None not in values


def require_same_frequency(evidence: tuple[EvidenceItem, ...]) -> bool:
    values = {item.temporal_context.frequency for item in evidence}
    return len(values) == 1 and None not in values


def require_same_scope(evidence: tuple[EvidenceItem, ...]) -> bool:
    values = {
        (item.scope.scope_type, item.scope.scope_id) if item.scope is not None else None
        for item in evidence
    }
    return len(values) == 1 and None not in values


def _reconstruct_node_parameters(
    case: ContractCase,
    pattern: TaskPatternSpec,
) -> dict[str, dict[str, Any]]:
    program_nodes = {node.node_id: node for node in case.task.oracle.task_program.nodes}
    reconstructed: dict[str, dict[str, Any]] = {}
    for template in pattern.program_template:
        if template.foreach_evidence_role is None:
            node = program_nodes.get(template.node_role_id)
            if node is None:
                raise ValueError(
                    f"compiled Program is missing a Pattern node: {template.node_role_id}"
                )
            if node.parameters:
                reconstructed[template.node_role_id] = dict(node.parameters)
            continue

        prefix = f"{template.node_role_id}_"
        expanded = sorted(
            (
                node
                for node in program_nodes.values()
                if node.node_id.startswith(prefix)
                and node.node_id[len(prefix) :].isdigit()
            ),
            key=lambda node: int(node.node_id[len(prefix) :]),
        )
        if not expanded:
            raise ValueError(
                f"compiled Program is missing foreach nodes: {template.node_role_id}"
            )
        parameter_maps = [dict(node.parameters) for node in expanded]
        first = parameter_maps[0]
        shared = {
            key: value
            for key, value in first.items()
            if all(parameters.get(key) == value for parameters in parameter_maps[1:])
        }
        if shared:
            reconstructed[template.node_role_id] = shared
        for node, parameters in zip(expanded, parameter_maps, strict=True):
            specific = {key: value for key, value in parameters.items() if key not in shared}
            if specific:
                reconstructed[node.node_id] = specific
    return reconstructed
