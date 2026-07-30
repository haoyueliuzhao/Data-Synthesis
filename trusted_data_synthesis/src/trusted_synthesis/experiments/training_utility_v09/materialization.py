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
V09_BINDING_PROVIDER_VERSION = "v09_binding_provider.v3"


class V09FixtureBindingProvider:
    """Cross-domain fixture super-pool with deterministic disjoint partitions."""

    provider_id = V09_BINDING_PROVIDER_ID
    provider_version = V09_BINDING_PROVIDER_VERSION
    seed_effective = True

    def __init__(
        self,
        *,
        namespace: str,
        start_index: int,
        candidate_pool_id: str = "v09_fixture_superpool",
        candidate_pool_size: int = 20_000_000,
        sampling_partition_id: str = "A",
        pool_split_seed: int = 20260729,
        maximum_scan_multiplier: int = 48,
    ) -> None:
        if not namespace or not candidate_pool_id:
            raise ValueError("binding Provider namespace and pool ID cannot be empty")
        if start_index < 1 or candidate_pool_size < 10_000:
            raise ValueError("binding Provider candidate pool range is invalid")
        if sampling_partition_id not in {"A", "B"}:
            raise ValueError("fixture super-pool partition must be A or B")
        if maximum_scan_multiplier < 8:
            raise ValueError("binding Provider scan multiplier is too small")
        self._namespace = namespace
        self._start_index = start_index
        self._candidate_pool_size = candidate_pool_size
        self._sampling_partition_id = sampling_partition_id
        self._pool_split_seed = pool_split_seed
        self._maximum_scan_multiplier = maximum_scan_multiplier
        self.candidate_pool_id = candidate_pool_id
        self.sampling_partition_id = sampling_partition_id

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
        self._domain_offsets = {
            domain: ordinal * candidate_pool_size
            for ordinal, domain in enumerate(sorted(self._case_factories))
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
        self.compiler_contract_hash = canonical_hash(
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
            prefix="v09_binding_compiler_contract:",
        )
        self.candidate_pool_contract_hash = canonical_hash(
            {
                "candidate_pool_id": candidate_pool_id,
                "start_index": start_index,
                "per_domain_pool_size": candidate_pool_size,
                "domain_offsets": self._domain_offsets,
                "pool_split_seed": pool_split_seed,
                "partition_count": 2,
            },
            prefix="v09_binding_candidate_pool_contract:",
        )
        self.sampling_contract_hash = canonical_hash(
            {
                "candidate_pool_contract_hash": self.candidate_pool_contract_hash,
                "sampling_partition_id": sampling_partition_id,
                "maximum_scan_multiplier": maximum_scan_multiplier,
                "seed_controls_order": True,
                "enumeration_mode": "bounded_superpool_until_exhausted",
            },
            prefix="v09_binding_sampling_contract:",
        )
        self.provider_contract_hash = canonical_hash(
            {
                "namespace": namespace,
                "compiler_contract_hash": self.compiler_contract_hash,
                "sampling_contract_hash": self.sampling_contract_hash,
            },
            prefix="v09_binding_provider_contract:",
        )

    def domain_for_pattern(self, pattern_id: str) -> str:
        try:
            return self._pattern_domains[pattern_id]
        except KeyError as exc:
            raise ValueError(f"Pattern is absent from the Provider catalog: {pattern_id}") from exc

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
        scan_limit = min(
            self._candidate_pool_size,
            max(512, request.requested_count * self._maximum_scan_multiplier),
        )
        domain_start = self._start_index + self._domain_offsets[domain]
        indexes = [
            domain_start + offset
            for offset in range(scan_limit)
            if self._partition_for_index(domain, domain_start + offset)
            == self._sampling_partition_id
        ]
        indexes.sort(
            key=lambda index: canonical_hash(
                {
                    "request_seed": request.seed,
                    "cell_id": request.cell.cell_id,
                    "candidate_index": index,
                    "candidate_pool_contract_hash": self.candidate_pool_contract_hash,
                },
                prefix="v09_seeded_candidate_order:",
            )
        )
        for index in indexes:
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
                    "candidate_pool_contract_hash": self.candidate_pool_contract_hash,
                    "sampling_partition_id": self._sampling_partition_id,
                    "applied_constraints": request.cell.active_binding_constraints,
                },
                prefix="v09_synthesis_binding_candidate:",
            )
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

    def _partition_for_index(self, domain: str, index: int) -> str:
        digest = canonical_hash(
            {
                "candidate_pool_id": self.candidate_pool_id,
                "domain": domain,
                "candidate_index": index,
                "pool_split_seed": self._pool_split_seed,
            },
            prefix="v09_candidate_pool_partition:",
        ).split(":", 1)[1]
        return "A" if int(digest[:16], 16) % 2 == 0 else "B"


class V09CompositeBindingProvider:
    """Dispatch domain-owned Providers behind one auditable Core protocol."""

    provider_id = "training_utility_v09_composite_binding_provider"
    provider_version = "v09_composite_binding_provider.v1"

    def __init__(
        self,
        providers: Mapping[str, Any],
        *,
        sampling_partition_id: str,
    ) -> None:
        if not providers:
            raise ValueError("composite Provider requires domain Providers")
        if set(providers) != {"finance", "legal", "science"}:
            raise ValueError("v0.9 composite Provider must cover all experiment domains")
        if any(
            provider.sampling_partition_id != sampling_partition_id
            for provider in providers.values()
        ):
            raise ValueError("composite Provider partitions must agree")
        self._providers = dict(providers)
        self.sampling_partition_id = sampling_partition_id
        self.seed_effective = all(provider.seed_effective for provider in providers.values())
        self.candidate_pool_id = canonical_hash(
            {domain: provider.candidate_pool_id for domain, provider in sorted(providers.items())},
            prefix="v09_composite_candidate_pool:",
        )
        self.compiler_contract_hash = canonical_hash(
            {
                domain: provider.compiler_contract_hash
                for domain, provider in sorted(providers.items())
            },
            prefix="v09_composite_compiler_contract:",
        )
        self.candidate_pool_contract_hash = canonical_hash(
            {
                domain: provider.candidate_pool_contract_hash
                for domain, provider in sorted(providers.items())
            },
            prefix="v09_composite_candidate_pool_contract:",
        )
        self.sampling_contract_hash = canonical_hash(
            {
                domain: provider.sampling_contract_hash
                for domain, provider in sorted(providers.items())
            },
            prefix="v09_composite_sampling_contract:",
        )
        self.provider_contract_hash = canonical_hash(
            {
                "compiler_contract_hash": self.compiler_contract_hash,
                "sampling_contract_hash": self.sampling_contract_hash,
            },
            prefix="v09_composite_provider_contract:",
        )

    def domain_for_pattern(self, pattern_id: str) -> str:
        matches = tuple(
            domain
            for domain, provider in self._providers.items()
            if _provider_has_pattern(provider, pattern_id)
        )
        if len(matches) != 1:
            raise ValueError(f"Pattern must resolve to exactly one domain Provider: {pattern_id}")
        return matches[0]

    def iter_candidates(
        self,
        request: SynthesisCellRequest,
    ) -> Iterable[SynthesisBindingCandidate]:
        domain = self.domain_for_pattern(request.cell.pattern_id)
        yield from self._providers[domain].iter_candidates(request)


def _provider_has_pattern(provider: Any, pattern_id: str) -> bool:
    try:
        provider.domain_for_pattern(pattern_id)
    except ValueError:
        return False
    return True


def fresh_fixture_start_index(
    config: V09RefinementConfig,
    *,
    cohort_namespace: str,
) -> int:
    """Choose a deterministic range beyond candidate/evaluation fixtures."""

    digest = canonical_hash(
        {
            "materialization_seed": config.materialization_seed,
            "candidate_pool_id": cohort_namespace,
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
                    f"compiled Program is missing a logical Pattern node: {template.node_role_id}"
                )
            if node.parameters:
                reconstructed[template.node_role_id] = dict(node.parameters)
            continue

        prefix = f"{template.node_role_id}_"
        expanded = sorted(
            (
                node
                for node in program_nodes.values()
                if node.node_id.startswith(prefix) and node.node_id[len(prefix) :].isdigit()
            ),
            key=lambda node: int(node.node_id[len(prefix) :]),
        )
        if not expanded:
            raise ValueError(
                f"compiled Program is missing foreach Pattern nodes: {template.node_role_id}"
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
