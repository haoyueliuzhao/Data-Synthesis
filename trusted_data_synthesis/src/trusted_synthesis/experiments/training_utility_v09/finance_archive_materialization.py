from __future__ import annotations

from collections.abc import Iterable

from trusted_synthesis.core.operations.registry import default_registry
from trusted_synthesis.core.plugins import DomainPluginSet
from trusted_synthesis.core.refinement import build_synthesis_cell
from trusted_synthesis.core.refinement.materialization import (
    SynthesisBindingCandidate,
    SynthesisCellRequest,
)
from trusted_synthesis.domains.finance.adapter import FinanceArchiveAdapter
from trusted_synthesis.domains.finance.counterfactual import (
    finance_counterfactual_registry,
)
from trusted_synthesis.domains.finance.pattern_runtime import FinanceTaskPatternRuntime
from trusted_synthesis.domains.finance.policy import FinanceSemanticPolicy
from trusted_synthesis.domains.finance.quality_clauses import (
    FinanceQualityClauseProvider,
)
from trusted_synthesis.domains.finance.tasks import FinanceTaskPlugin
from trusted_synthesis.experiments.cross_domain_contract_suite.fixtures import (
    ContractCase,
)
from trusted_synthesis.experiments.finance_pilot.sampler import (
    TaskBinding,
    discover_bindings,
    sample_evidence,
)
from trusted_synthesis.experiments.finance_pilot.schema import FinancePilotConfig
from trusted_synthesis.experiments.finance_pilot.task_factory import build_task_cases
from trusted_synthesis.hashing import canonical_hash

from .materialization import (
    _exclude_forecast,
    _reconstruct_binding,
    _require_current_version,
    _require_official_source,
    _require_same_definition,
    _require_same_frequency,
    _require_same_scope,
    _same_structural_cell,
)

FINANCE_ARCHIVE_PROVIDER_ID = "training_utility_v09_finance_archive_provider"
FINANCE_ARCHIVE_PROVIDER_VERSION = "finance_archive_binding_provider.v1"


class FinanceArchiveBindingProvider:
    """Enumerate fresh Finance bindings from a pinned graph-ready archive."""

    provider_id = FINANCE_ARCHIVE_PROVIDER_ID
    provider_version = FINANCE_ARCHIVE_PROVIDER_VERSION
    seed_effective = True

    def __init__(
        self,
        adapter: FinanceArchiveAdapter,
        *,
        candidate_pool_id: str,
        sampling_partition_id: str,
        pool_split_seed: int,
        evidence_scan_limit: int = 200_000,
        evidence_sample_size: int = 50_000,
        stratum_reservoir_size: int = 5_000,
        candidates_per_pattern: int = 2_000,
    ) -> None:
        if not candidate_pool_id:
            raise ValueError("finance Archive candidate pool ID cannot be empty")
        if sampling_partition_id not in {"A", "B"}:
            raise ValueError("finance Archive partition must be A or B")
        if candidates_per_pattern < 1:
            raise ValueError("finance Archive candidate quota must be positive")
        inspection = adapter.inspect()
        if not inspection["compatible"]:
            raise ValueError(
                f"finance Archive Provider requires a compatible archive: {inspection['errors']}"
            )
        self._adapter = adapter
        self._candidate_pool_id = candidate_pool_id
        self.candidate_pool_id = candidate_pool_id
        self.sampling_partition_id = sampling_partition_id
        self._pool_split_seed = pool_split_seed
        self._policy = FinanceSemanticPolicy()
        self._quality_provider = FinanceQualityClauseProvider()
        self._task_plugin = FinanceTaskPlugin(allow_structured_claims=True)
        self._runtime = FinanceTaskPatternRuntime()
        self._registry = default_registry()
        self._counterfactual_registry = finance_counterfactual_registry()
        self._patterns = {
            pattern.pattern_id: pattern for pattern in self._task_plugin.pattern_manifest
        }
        self._pattern_id_by_task_type = {
            pattern.task_type: pattern.pattern_id for pattern in self._task_plugin.pattern_manifest
        }
        self._constraint_validators = {
            "exclude_forecast": _exclude_forecast,
            "require_current_version": _require_current_version,
            "require_official_source": _require_official_source,
            "require_same_definition": _require_same_definition,
            "require_same_frequency": _require_same_frequency,
            "require_same_scope": _require_same_scope,
        }
        pilot_config = FinancePilotConfig(
            pilot_id="training_utility_v09.finance_archive_provider",
            evidence_scan_limit=evidence_scan_limit,
            evidence_sample_size=evidence_sample_size,
            stratum_reservoir_size=stratum_reservoir_size,
            distractors_per_task=1,
            hard_distractors_per_task=6,
            hard_distractor_types=(
                "wrong_definition",
                "stale_version",
                "forecast",
                "unit_mismatch",
                "currency_mismatch",
                "wrong_scope",
            ),
            task_quotas={
                task_type: candidates_per_pattern for task_type in self._pattern_id_by_task_type
            },
            require_full_quota=False,
        )
        sample = sample_evidence(adapter, pilot_config, self._policy)
        self._evidence = sample.evidence
        self._evidence_by_id = {item.evidence_id: item for item in self._evidence}
        bindings = discover_bindings(self._evidence, pilot_config)
        self._bindings_by_pattern: dict[str, tuple[TaskBinding, ...]] = {}
        for task_type, pattern_id in self._pattern_id_by_task_type.items():
            values = tuple(binding for binding in bindings if binding.task_type == task_type)
            self._bindings_by_pattern[pattern_id] = values
        archive_contract = {
            "adapter_id": adapter.adapter_id,
            "adapter_config": adapter.config.model_dump(mode="json"),
            "inspection": inspection,
            "sample_config_hash": pilot_config.config_hash,
            "evidence_manifest_hash": canonical_hash(
                tuple(item.evidence_version_id for item in self._evidence),
                prefix="finance_archive_provider_evidence:",
            ),
            "binding_manifest_hash": canonical_hash(
                tuple(binding.binding_hash for binding in bindings),
                prefix="finance_archive_provider_bindings:",
            ),
        }
        self.compiler_contract_hash = canonical_hash(
            {
                "patterns": {
                    key: value.pattern_hash for key, value in sorted(self._patterns.items())
                },
                "runtime": (self._runtime.runtime_id, self._runtime.runtime_version),
                "constraints": tuple(sorted(self._constraint_validators)),
            },
            prefix="finance_archive_binding_compiler_contract:",
        )
        self.candidate_pool_contract_hash = canonical_hash(
            {
                "candidate_pool_id": candidate_pool_id,
                "archive_contract": archive_contract,
                "pool_split_seed": pool_split_seed,
                "partition_count": 2,
            },
            prefix="finance_archive_candidate_pool_contract:",
        )
        self.sampling_contract_hash = canonical_hash(
            {
                "candidate_pool_contract_hash": self.candidate_pool_contract_hash,
                "sampling_partition_id": sampling_partition_id,
                "seed_controls_order": True,
            },
            prefix="finance_archive_sampling_contract:",
        )
        self.provider_contract_hash = canonical_hash(
            {
                "compiler_contract_hash": self.compiler_contract_hash,
                "sampling_contract_hash": self.sampling_contract_hash,
            },
            prefix="finance_archive_provider_contract:",
        )

    def for_partition(self, sampling_partition_id: str) -> FinanceArchiveBindingProvider:
        """Share the immutable archive catalog while changing only the A/B view."""

        if sampling_partition_id not in {"A", "B"}:
            raise ValueError("finance Archive partition must be A or B")
        clone = object.__new__(FinanceArchiveBindingProvider)
        clone.__dict__ = dict(self.__dict__)
        clone.sampling_partition_id = sampling_partition_id
        clone.sampling_contract_hash = canonical_hash(
            {
                "candidate_pool_contract_hash": clone.candidate_pool_contract_hash,
                "sampling_partition_id": sampling_partition_id,
                "seed_controls_order": True,
            },
            prefix="finance_archive_sampling_contract:",
        )
        clone.provider_contract_hash = canonical_hash(
            {
                "compiler_contract_hash": clone.compiler_contract_hash,
                "sampling_contract_hash": clone.sampling_contract_hash,
            },
            prefix="finance_archive_provider_contract:",
        )
        return clone

    def domain_for_pattern(self, pattern_id: str) -> str:
        if pattern_id not in self._patterns:
            raise ValueError(f"Pattern is absent from Finance Archive: {pattern_id}")
        return "finance"

    def iter_candidates(
        self,
        request: SynthesisCellRequest,
    ) -> Iterable[SynthesisBindingCandidate]:
        pattern = self._patterns.get(request.cell.pattern_id)
        if pattern is None:
            raise ValueError(
                f"requested Pattern is absent from Finance Archive: {request.cell.pattern_id}"
            )
        unknown = set(request.cell.active_binding_constraints) - set(self._constraint_validators)
        if unknown:
            raise ValueError(f"unknown Finance Archive constraints: {sorted(unknown)}")
        bindings = [
            binding
            for binding in self._bindings_by_pattern[request.cell.pattern_id]
            if self._partition(binding) == self.sampling_partition_id
        ]
        bindings.sort(
            key=lambda binding: canonical_hash(
                {
                    "request_seed": request.seed,
                    "cell_id": request.cell.cell_id,
                    "binding_hash": binding.binding_hash,
                },
                prefix="finance_archive_seeded_binding_order:",
            )
        )
        yielded = 0
        for source_binding in bindings:
            case = self._contract_case(source_binding)
            source_cell = build_synthesis_cell(
                case.task.public,
                case.corpus,
                case.task.oracle.gold_evidence_ids,
            )
            if not _same_structural_cell(source_cell, request.cell):
                continue
            binding = _reconstruct_binding(case, pattern)
            required = tuple(
                self._evidence_by_id[evidence_id] for evidence_id in source_binding.evidence_ids
            )
            if not all(
                self._constraint_validators[constraint](required)
                for constraint in request.cell.active_binding_constraints
            ):
                continue
            yield SynthesisBindingCandidate(
                candidate_id=canonical_hash(
                    {
                        "request_id": request.request_id,
                        "source_binding_hash": source_binding.binding_hash,
                        "candidate_pool_contract_hash": self.candidate_pool_contract_hash,
                        "sampling_partition_id": self.sampling_partition_id,
                    },
                    prefix="finance_archive_binding_candidate:",
                ),
                pattern=pattern,
                binding=binding,
                bundle=case.bundle,
                corpus=case.corpus,
                proof_graph=case.proof_graph,
                operation_registry=case.registry,
                pattern_runtime=self._runtime,
                semantic_policy=case.semantic_policy,
                quality_clause_provider=case.quality_clause_provider,
                domain_plugin_set=case.plugin_set,
                applied_binding_constraints=request.cell.active_binding_constraints,
            )
            yielded += 1
            if yielded >= request.requested_count:
                return

    def _partition(self, binding: TaskBinding) -> str:
        digest = canonical_hash(
            {
                "candidate_pool_id": self._candidate_pool_id,
                "binding_hash": binding.binding_hash,
                "pool_split_seed": self._pool_split_seed,
            },
            prefix="finance_archive_binding_partition:",
        ).split(":", 1)[1]
        return "A" if int(digest[:16], 16) % 2 == 0 else "B"

    def _contract_case(self, binding: TaskBinding) -> ContractCase:
        gold = tuple(self._evidence_by_id[item] for item in binding.evidence_ids)
        pilot = build_task_cases(
            (binding,),
            gold,
            distractors_per_task=0,
            hard_distractors_per_task=6,
            hard_distractor_types=(
                "wrong_definition",
                "stale_version",
                "forecast",
                "unit_mismatch",
                "currency_mismatch",
                "wrong_scope",
            ),
            task_synthesizer=self._task_plugin,
        )[0]
        return ContractCase(
            domain="finance",
            bundle=pilot.bundle,
            corpus=pilot.corpus,
            proof_graph=pilot.proof_graph,
            task=pilot.task,
            registry=self._registry,
            semantic_policy=self._policy,
            quality_clause_provider=self._quality_provider,
            plugin_set=DomainPluginSet(
                domain="finance",
                evidence_adapter_id=self._adapter.adapter_id,
                semantic_policy_id=self._policy.policy_id,
                task_plugin_ids=(self._task_plugin.plugin_id,),
                quality_clause_provider_id=self._quality_provider.provider_id,
                quality_clause_provider_version=self._quality_provider.provider_version,
                operation_registry_manifest_hash=canonical_hash(
                    self._registry.manifest(),
                    prefix="operation_manifest:",
                ),
                counterfactual_operator_manifest_hash=(self._counterfactual_registry.manifest_hash),
                versions={
                    "archive_kg_build": self._adapter.config.required_kg_build_id,
                    "provider": FINANCE_ARCHIVE_PROVIDER_VERSION,
                },
            ),
            counterfactual_registry=self._counterfactual_registry,
        )
