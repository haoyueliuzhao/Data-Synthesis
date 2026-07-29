from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from typing import Any

from trusted_synthesis.core.evidence.epistemic import EpistemicStatus
from trusted_synthesis.core.evidence.schema import EvidenceItem, SourceAuthority
from trusted_synthesis.core.plugins import TaskPatternRuntimeProtocol
from trusted_synthesis.core.refinement import SynthesisCell, build_synthesis_cell
from trusted_synthesis.core.refinement.materialization import (
    SynthesisBindingCandidate,
    SynthesisCellRequest,
)
from trusted_synthesis.core.task.binding import EvidenceBinding, make_evidence_binding
from trusted_synthesis.core.task.pattern import TaskPatternSpec
from trusted_synthesis.domains.finance.pattern_runtime import FinanceTaskPatternRuntime
from trusted_synthesis.domains.finance.tasks import FinanceTaskPlugin
from trusted_synthesis.domains.legal.pattern_runtime import LegalTaskPatternRuntime
from trusted_synthesis.domains.legal.tasks import LegalTaskPlugin
from trusted_synthesis.domains.science.pattern_runtime import ScienceTaskPatternRuntime
from trusted_synthesis.domains.science.tasks import ScienceTaskPlugin
from trusted_synthesis.experiments.counterfactual_finance_fixture import (
    build_finance_counterfactual_case,
)
from trusted_synthesis.experiments.cross_domain_contract_suite.fixtures import (
    ContractCase,
    build_legal_contract_case,
    build_science_contract_case,
)
from trusted_synthesis.hashing import canonical_hash

from .schema import V09RefinementConfig

V09_BINDING_PROVIDER_ID = "training_utility_v09_fixture_binding_provider"
V09_BINDING_PROVIDER_VERSION = "v09_binding_provider.v1"


class V09FixtureBindingProvider:
    """Cross-domain Provider that creates fresh fixture bindings for requested Cells."""

    provider_id = V09_BINDING_PROVIDER_ID
    provider_version = V09_BINDING_PROVIDER_VERSION

    def __init__(
        self,
        *,
        namespace: str,
        start_index: int,
        maximum_scan_multiplier: int = 12,
    ) -> None:
        if not namespace:
            raise ValueError("binding Provider namespace cannot be empty")
        if start_index < 1 or maximum_scan_multiplier < 4:
            raise ValueError("binding Provider index and scan multiplier are invalid")
        self._namespace = namespace
        self._maximum_scan_multiplier = maximum_scan_multiplier
        self._next_indexes = {
            "finance": start_index,
            "legal": start_index + 2_000_000,
            "science": start_index + 4_000_000,
        }
        finance = FinanceTaskPlugin(allow_structured_claims=True)
        legal = LegalTaskPlugin()
        science = ScienceTaskPlugin()
        manifests = {
            "finance": finance.pattern_manifest,
            "legal": legal.pattern_manifest,
            "science": science.pattern_manifest,
        }
        self._patterns: dict[str, TaskPatternSpec] = {}
        self._pattern_domains: dict[str, str] = {}
        for domain, patterns in manifests.items():
            for pattern in patterns:
                if pattern.pattern_id in self._patterns:
                    raise ValueError("Pattern IDs must be globally unique for synthesis")
                self._patterns[pattern.pattern_id] = pattern
                self._pattern_domains[pattern.pattern_id] = domain
        self._runtimes: dict[str, TaskPatternRuntimeProtocol] = {
            "finance": FinanceTaskPatternRuntime(),
            "legal": LegalTaskPatternRuntime(),
            "science": ScienceTaskPatternRuntime(),
        }
        self._case_factories: dict[str, Callable[[int], ContractCase]] = {
            "finance": build_finance_counterfactual_case,
            "legal": build_legal_contract_case,
            "science": build_science_contract_case,
        }
        self._constraint_validators: dict[
            str,
            Callable[[tuple[EvidenceItem, ...]], bool],
        ] = {
            "exclude_forecast": _exclude_forecast,
            "require_current_version": _require_current_version,
            "require_official_source": _require_official_source,
            "require_same_definition": _require_same_definition,
            "require_same_frequency": _require_same_frequency,
            "require_same_scope": _require_same_scope,
        }
        self.provider_contract_hash = canonical_hash(
            {
                "provider_id": self.provider_id,
                "provider_version": self.provider_version,
                "patterns": {
                    key: value.pattern_hash for key, value in sorted(self._patterns.items())
                },
                "runtimes": {
                    domain: (runtime.runtime_id, runtime.runtime_version)
                    for domain, runtime in sorted(self._runtimes.items())
                },
                "constraint_ids": tuple(sorted(self._constraint_validators)),
            },
            prefix="v09_binding_provider_contract:",
        )

    def domain_for_pattern(self, pattern_id: str) -> str:
        try:
            return self._pattern_domains[pattern_id]
        except KeyError as exc:
            raise ValueError(
                f"Pattern is absent from the Provider catalog: {pattern_id}"
            ) from exc

    def iter_candidates(
        self,
        request: SynthesisCellRequest,
    ) -> Iterable[SynthesisBindingCandidate]:
        domain = self._pattern_domains.get(request.cell.pattern_id)
        if domain is None:
            raise ValueError(
                f"requested Pattern is absent from the Provider catalog: {request.cell.pattern_id}"
            )
        unknown_constraints = set(request.cell.active_binding_constraints) - set(
            self._constraint_validators
        )
        if unknown_constraints:
            raise ValueError(
                f"binding Provider cannot apply unknown constraints: {sorted(unknown_constraints)}"
            )
        scan_limit = max(
            120,
            request.requested_count * self._maximum_scan_multiplier,
        )
        yielded = 0
        for _ in range(scan_limit):
            index = self._next_indexes[domain]
            self._next_indexes[domain] += 1
            case = self._case_factories[domain](index)
            pattern_identity = case.task.public.metadata.get("task_pattern") or {}
            if pattern_identity.get("pattern_id") != request.cell.pattern_id:
                continue
            source_cell = build_synthesis_cell(
                case.task.public,
                case.corpus,
                case.task.oracle.gold_evidence_ids,
            )
            if not _same_structural_cell(source_cell, request.cell):
                continue
            binding = _reconstruct_binding(
                case,
                self._patterns[request.cell.pattern_id],
            )
            evidence_by_id = {item.evidence_id: item for item in case.bundle.evidence}
            required = tuple(evidence_by_id[item] for item in binding.evidence_ids)
            if not all(
                self._constraint_validators[constraint](required)
                for constraint in request.cell.active_binding_constraints
            ):
                continue
            candidate_id = canonical_hash(
                {
                    "namespace": self._namespace,
                    "request_id": request.request_id,
                    "fixture_task_id": case.task.task_id,
                    "source_binding_id": binding.binding_id,
                    "applied_constraints": request.cell.active_binding_constraints,
                },
                prefix="v09_synthesis_binding_candidate:",
            )
            yielded += 1
            yield SynthesisBindingCandidate(
                candidate_id=candidate_id,
                pattern=self._patterns[request.cell.pattern_id],
                binding=binding,
                bundle=case.bundle,
                corpus=case.corpus,
                proof_graph=case.proof_graph,
                operation_registry=case.registry,
                pattern_runtime=self._runtimes[domain],
                semantic_policy=case.semantic_policy,
                quality_clause_provider=case.quality_clause_provider,
                domain_plugin_set=case.plugin_set,
                applied_binding_constraints=request.cell.active_binding_constraints,
            )
            if yielded >= request.requested_count:
                return


def project_policy_counts_to_domain_quotas(
    policy_allocated_counts: Mapping[str, int],
    policy_probabilities: Mapping[str, float],
    cell_domains: Mapping[str, str],
    domain_quotas: Mapping[str, int],
) -> dict[str, int]:
    """Project policy allocation onto frozen domain totals without changing within-domain order."""

    expected_cells = set(policy_allocated_counts)
    if set(policy_probabilities) != expected_cells or set(cell_domains) != expected_cells:
        raise ValueError("policy projection requires complete Cell metadata")
    if set(domain_quotas) != set(cell_domains.values()):
        raise ValueError("domain quotas must cover every Cell domain")
    projected = {cell_id: 0 for cell_id in expected_cells}
    for domain, quota in sorted(domain_quotas.items()):
        cells = sorted(
            cell_id for cell_id, cell_domain in cell_domains.items() if cell_domain == domain
        )
        weights = {cell_id: float(policy_allocated_counts[cell_id]) for cell_id in cells}
        if sum(weights.values()) <= 0:
            weights = {cell_id: policy_probabilities[cell_id] for cell_id in cells}
        allocation = _largest_remainder(weights, quota)
        projected.update(allocation)
    if sum(projected.values()) != sum(domain_quotas.values()):
        raise ValueError("domain-constrained projection did not preserve the cohort budget")
    return dict(sorted(projected.items()))


def fresh_fixture_start_index(
    config: V09RefinementConfig,
    *,
    cohort_namespace: str,
) -> int:
    """Choose a deterministic range beyond candidate/evaluation fixtures."""

    digest = canonical_hash(
        {
            "config_hash": config.config_hash,
            "cohort_namespace": cohort_namespace,
            "provider_version": V09_BINDING_PROVIDER_VERSION,
        },
        prefix="v09_fresh_fixture_range:",
    ).split(":", 1)[1]
    return 100_000 + int(digest[:8], 16) % 500_000


def _same_structural_cell(left: SynthesisCell, right: SynthesisCell) -> bool:
    return (
        left.pattern_id == right.pattern_id
        and left.binding_stratum_id == right.binding_stratum_id
        and left.difficulty_bucket == right.difficulty_bucket
        and left.distractor_profile_id == right.distractor_profile_id
    )


def _reconstruct_binding(
    case: ContractCase,
    pattern: TaskPatternSpec,
) -> EvidenceBinding:
    """Rebuild the full immutable Binding from a compiled source task.

    Task Oracle artifacts intentionally expose only a compact Binding identity. The
    Pattern and concrete Program remain pinned, so the Provider can reconstruct the
    complete object without trusting mutable generation state.
    """

    identity = case.task.oracle.selection_contract.get("pattern_binding")
    if not isinstance(identity, dict):
        raise ValueError("fixture task does not expose a Pattern Binding identity")
    role_bindings = identity.get("role_bindings")
    source_graph_id = identity.get("source_graph_id")
    if not isinstance(role_bindings, dict) or not isinstance(source_graph_id, str):
        raise ValueError("fixture Pattern Binding identity is incomplete")
    node_parameters = _reconstruct_node_parameters(case, pattern)
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
        node_parameters=node_parameters,
        binding_features={
            "reconstructed_from_task_id": case.task.task_id,
            "source_binding_id": identity.get("binding_id"),
        },
    )
    if set(binding.role_bindings) != {role.role_id for role in pattern.evidence_roles}:
        raise ValueError("reconstructed Binding roles do not match the frozen Pattern")
    return binding


def _reconstruct_node_parameters(
    case: ContractCase,
    pattern: TaskPatternSpec,
) -> dict[str, dict[str, Any]]:
    """Recover logical Pattern parameters from concrete foreach Program nodes."""

    program_nodes = {node.node_id: node for node in case.task.oracle.task_program.nodes}
    reconstructed: dict[str, dict[str, Any]] = {}
    for template in pattern.program_template:
        if template.foreach_evidence_role is None:
            node = program_nodes.get(template.node_role_id)
            if node is None:
                raise ValueError(
                    "compiled Program is missing a logical Pattern node: "
                    f"{template.node_role_id}"
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
                "compiled Program is missing foreach Pattern nodes: "
                f"{template.node_role_id}"
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
            specific = {
                key: value for key, value in parameters.items() if key not in shared
            }
            if specific:
                reconstructed[node.node_id] = specific
    return reconstructed


def _largest_remainder(weights: Mapping[str, float], total: int) -> dict[str, int]:
    if total < 0 or not weights or any(value < 0 for value in weights.values()):
        raise ValueError("allocation weights or total are invalid")
    weight_sum = sum(weights.values())
    if weight_sum <= 0:
        raise ValueError("allocation weights must contain positive mass")
    raw = {key: total * value / weight_sum for key, value in weights.items()}
    output = {key: int(value) for key, value in raw.items()}
    remainder = total - sum(output.values())
    for key in sorted(raw, key=lambda item: (-(raw[item] - output[item]), item))[:remainder]:
        output[key] += 1
    return dict(sorted(output.items()))


def _exclude_forecast(evidence: tuple[EvidenceItem, ...]) -> bool:
    return all(not bool(item.domain_context.get("is_forecast")) for item in evidence)


def _require_current_version(evidence: tuple[EvidenceItem, ...]) -> bool:
    return all(item.epistemic_status != EpistemicStatus.SUPERSEDED for item in evidence)


def _require_official_source(evidence: tuple[EvidenceItem, ...]) -> bool:
    return all(item.source.authority == SourceAuthority.OFFICIAL for item in evidence)


def _require_same_definition(evidence: tuple[EvidenceItem, ...]) -> bool:
    values = {item.definition.definition_id for item in evidence}
    return len(values) == 1 and None not in values


def _require_same_frequency(evidence: tuple[EvidenceItem, ...]) -> bool:
    values = {item.temporal_context.frequency for item in evidence}
    return len(values) == 1 and None not in values


def _require_same_scope(evidence: tuple[EvidenceItem, ...]) -> bool:
    values = {
        (item.scope.scope_type, item.scope.scope_id) if item.scope is not None else None
        for item in evidence
    }
    return len(values) == 1 and None not in values
