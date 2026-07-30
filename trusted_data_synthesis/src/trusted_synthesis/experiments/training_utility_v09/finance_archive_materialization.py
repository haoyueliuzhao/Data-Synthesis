from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field

from trusted_synthesis.core.evidence.corpus import EvidenceCorpus
from trusted_synthesis.core.evidence.schema import EvidenceItem
from trusted_synthesis.core.operations.registry import default_registry
from trusted_synthesis.core.refinement import build_synthesis_cell
from trusted_synthesis.core.refinement.materialization import (
    SynthesisBindingCandidate,
    SynthesisCellRequest,
)
from trusted_synthesis.core.task.schema import VerifierRequirement
from trusted_synthesis.domains.finance.adapter import FinanceArchiveAdapter
from trusted_synthesis.domains.finance.counterfactual import (
    finance_counterfactual_registry,
)
from trusted_synthesis.domains.finance.pattern_runtime import FinanceTaskPatternRuntime
from trusted_synthesis.domains.finance.plugins import finance_plugin_set
from trusted_synthesis.domains.finance.policy import FinanceSemanticPolicy
from trusted_synthesis.domains.finance.quality_clauses import (
    FinanceQualityClauseProvider,
)
from trusted_synthesis.domains.finance.tasks import FinanceTaskPlugin
from trusted_synthesis.experiments.cross_domain_contract_suite.fixtures import (
    ContractCase,
)
from trusted_synthesis.experiments.finance_pilot.sampler import (
    FINANCE_REAL_DISTRACTOR_INDEX_VERSION,
    FINANCE_SAMPLING_STRATUM_VERSION,
    RealDistractorIndex,
    RealDistractorSelection,
    TaskBinding,
    discover_bindings,
    sample_evidence,
)
from trusted_synthesis.experiments.finance_pilot.schema import FinancePilotConfig
from trusted_synthesis.experiments.finance_pilot.task_factory import (
    PilotTaskCase,
    build_task_cases,
)
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
FINANCE_ARCHIVE_PROVIDER_VERSION = "finance_archive_binding_provider.v5"
FINANCE_ARCHIVE_CAPACITY_VERSION = "finance_archive_capacity.v4"
FINANCE_PATTERN_TARGET_SHARES = {
    "finance.fact_retrieval": 0.05,
    "finance.comparison": 0.15,
    "finance.temporal_absolute_change": 0.10,
    "finance.temporal_growth": 0.15,
    "finance.temporal_average": 0.10,
    "finance.registered_ratio": 0.15,
    "finance.derived_growth_comparison": 0.30,
}


class FinanceArchiveCapacityReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    report_id: str = Field(min_length=1)
    provider_contract_hash: str = Field(min_length=1)
    kg_build_id: str = Field(min_length=1)
    target_sample_count: int = Field(ge=1)
    archive_fact_node_count: int = Field(ge=0)
    eligible_stream_to_archive_fact_ratio: float = Field(ge=0, le=1)
    complete_eligible_stream_scan: bool
    target_counts_by_pattern: dict[str, int]
    evidence_scanned_count: int = Field(ge=0)
    evidence_domain_valid_count: int = Field(ge=0)
    evidence_sampled_count: int = Field(ge=0)
    source_grounding_checked_count: int = Field(ge=0)
    source_grounding_valid_count: int = Field(ge=0)
    source_grounding_failure_counts: dict[str, int]
    source_grounding_pass_rate: float = Field(ge=0, le=1)
    source_grounding_rejected_source_counts: dict[str, int]
    binding_count_by_pattern: dict[str, int]
    binding_count_by_region: dict[str, int]
    binding_count_by_metric_category: dict[str, int]
    binding_count_by_source: dict[str, int]
    partition_binding_counts: dict[str, dict[str, int]]
    sampling_partition_id: Literal["A", "B"]
    execution_validation_count: int = Field(ge=0)
    executable_binding_count_by_pattern: dict[str, int]
    conflict_free_binding_count_by_pattern: dict[str, int]
    materialization_dry_run_count_by_pattern: dict[str, int]
    materialization_collision_count: int = Field(ge=0)
    capacity_estimation_method: Literal["full_corpus_disjoint_greedy_lower_bound.v1"]
    binding_execution_failure_counts: dict[str, int]
    evaluated_distractor_binding_count: int = Field(ge=0)
    hard_distractor_yield_by_pattern: dict[str, dict[str, object]]
    difficulty_distribution: dict[str, int]
    synthesis_cell_count: int = Field(ge=0)
    cell_exposure_capacity: dict[str, int]
    cell_conflict_free_capacity: dict[str, int]
    quota_shortfalls: dict[str, int]
    warnings: tuple[str, ...]
    status: Literal["ready", "blocked"]
    version: str = FINANCE_ARCHIVE_CAPACITY_VERSION


@dataclass(frozen=True)
class _CapacityEntry:
    pattern_id: str
    binding_hash: str
    cell_id: str
    evidence_version_ids: frozenset[str]


class _HardDistractorYield(TypedDict):
    evaluated_count: int
    bindings_with_full_hard_set: int
    mean_hard_count: float
    mean_mismatches_per_hard: float
    single_violation_hard_count: int
    single_violation_rate: float
    hard_error_family_counts: dict[str, int]
    hard_error_family_count: int
    full_hard_yield_rate: float
    mean_broad_count: float


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
        self._inspection = inspection
        self._candidate_pool_id = candidate_pool_id
        self.candidate_pool_id = candidate_pool_id
        self.sampling_partition_id = sampling_partition_id
        self._pool_split_seed = pool_split_seed
        self._policy = FinanceSemanticPolicy()
        self._source_grounding_verifier = adapter.source_grounding_verifier()
        self._quality_provider = FinanceQualityClauseProvider()
        self._task_plugin = FinanceTaskPlugin(
            allow_structured_claims=True,
            source_grounding_requirement=VerifierRequirement.REQUIRED,
        )
        self._runtime = FinanceTaskPatternRuntime()
        self._registry = default_registry()
        self._counterfactual_registry = finance_counterfactual_registry()
        self._plugin_set = finance_plugin_set(
            self._adapter,
            self._registry,
            self._source_grounding_verifier,
        ).model_copy(
            update={
                "versions": {
                    "source_grounding": self._source_grounding_verifier.verifier_version,
                    "plugin_set": "1.3.0",
                    "archive_kg_build": self._adapter.config.required_kg_build_id,
                    "provider": FINANCE_ARCHIVE_PROVIDER_VERSION,
                }
            }
        )
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
        sample = sample_evidence(
            adapter,
            pilot_config,
            self._policy,
            self._source_grounding_verifier,
        )
        self._sample = sample
        self._evidence = sample.evidence
        self._evidence_by_id = {item.evidence_id: item for item in self._evidence}
        self._distractor_index = RealDistractorIndex(self._evidence)
        bindings = discover_bindings(self._evidence, pilot_config)
        self._all_bindings = bindings
        self._contract_case_cache: dict[str, ContractCase] = {}
        self._distractor_selection_cache: dict[str, RealDistractorSelection] = {}
        self._pilot_case_cache: dict[str, PilotTaskCase] = {}
        self._bindings_by_pattern: dict[str, tuple[TaskBinding, ...]] = {}
        for task_type, pattern_id in self._pattern_id_by_task_type.items():
            values = tuple(binding for binding in bindings if binding.task_type == task_type)
            self._bindings_by_pattern[pattern_id] = values
        archive_contract = {
            "adapter_id": adapter.adapter_id,
            "adapter_config": adapter.config.model_dump(mode="json"),
            "inspection": inspection,
            "sample_config_hash": pilot_config.config_hash,
            "sampling_stratum_version": FINANCE_SAMPLING_STRATUM_VERSION,
            "real_distractor_index_version": FINANCE_REAL_DISTRACTOR_INDEX_VERSION,
            "source_grounding": {
                "verifier_id": self._source_grounding_verifier.verifier_id,
                "verifier_version": self._source_grounding_verifier.verifier_version,
                "manifest_hash": canonical_hash(
                    {
                        "verifier_id": self._source_grounding_verifier.verifier_id,
                        "verifier_version": self._source_grounding_verifier.verifier_version,
                    },
                    prefix="source_grounding_manifest:",
                ),
                "checked_count": sample.source_grounding_checked_count,
                "valid_count": sample.source_grounding_valid_count,
                "rejected_count": sample.source_grounding_rejected_count,
                "failure_counts": sample.source_grounding_failure_counts,
            },
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
                "source_grounding_verifier": (
                    self._source_grounding_verifier.verifier_id,
                    self._source_grounding_verifier.verifier_version,
                ),
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
                "enumeration_mode": "bounded_superpool_until_exhausted",
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
                "enumeration_mode": "bounded_superpool_until_exhausted",
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

    @property
    def kg_build_id(self) -> str:
        return self._adapter.config.required_kg_build_id

    def contract_cases(
        self,
        count: int,
        *,
        seed: int,
        require_corpus_disjoint: bool = True,
    ) -> tuple[ContractCase, ...]:
        """Select a deterministic, prefix-stable set of real Archive tasks.

        Weighted fair scheduling keeps every prefix close to the frozen Pattern mix, while
        corpus-disjoint selection prevents train/evaluation leakage through distractors.
        """

        if count < 1:
            raise ValueError("Finance Archive ContractCase count must be positive")
        ordered: dict[str, tuple[TaskBinding, ...]] = {}
        for pattern_id, values in sorted(self._bindings_by_pattern.items()):
            partition_values = tuple(
                binding
                for binding in values
                if self._partition(binding) == self.sampling_partition_id
            )
            ordered[pattern_id] = tuple(
                sorted(
                    partition_values,
                    key=lambda binding: canonical_hash(
                        {
                            "seed": seed,
                            "pattern_id": pattern_id,
                            "binding_hash": binding.binding_hash,
                        },
                        prefix="finance_archive_contract_case_order:",
                    ),
                )
            )

        positions = {pattern_id: 0 for pattern_id in ordered}
        selected_by_pattern = Counter({pattern_id: 0 for pattern_id in ordered})
        available = {
            pattern_id
            for pattern_id, values in ordered.items()
            if values and FINANCE_PATTERN_TARGET_SHARES.get(pattern_id, 0) > 0
        }
        selected: list[ContractCase] = []
        used_evidence_versions: set[str] = set()
        used_task_ids: set[str] = set()
        while len(selected) < count and available:
            pattern_id = min(
                available,
                key=lambda item: (
                    (selected_by_pattern[item] + 1) / FINANCE_PATTERN_TARGET_SHARES[item],
                    item,
                ),
            )
            values = ordered[pattern_id]
            chosen: ContractCase | None = None
            while positions[pattern_id] < len(values):
                binding = values[positions[pattern_id]]
                positions[pattern_id] += 1
                try:
                    case = self._contract_case(binding)
                except (KeyError, ValueError):
                    # Mining is deliberately broader than executable task semantics.
                    # Reject an invalid binding locally and continue the frozen order.
                    continue
                evidence_versions = {item.evidence_version_id for item in case.corpus.evidence}
                if case.task.task_id in used_task_ids:
                    continue
                if require_corpus_disjoint and evidence_versions & used_evidence_versions:
                    continue
                chosen = case
                used_task_ids.add(case.task.task_id)
                used_evidence_versions.update(evidence_versions)
                break
            if chosen is None:
                available.remove(pattern_id)
                continue
            selected.append(chosen)
            selected_by_pattern[pattern_id] += 1

        if len(selected) != count:
            raise ValueError(
                "Finance Archive lacks a corpus-disjoint ContractCase prefix: "
                f"requested={count}, selected={len(selected)}, "
                f"partition={self.sampling_partition_id}"
            )
        return tuple(selected)

    def capacity_report(
        self,
        *,
        target_sample_count: int = 1_000,
        pattern_target_shares: dict[str, float] | None = None,
        distractor_evaluation_limit_per_pattern: int = 50,
    ) -> FinanceArchiveCapacityReport:
        """Audit executable synthesis capacity before any Agent or LLM call."""

        if target_sample_count < 1:
            raise ValueError("capacity target sample count must be positive")
        if distractor_evaluation_limit_per_pattern < 1:
            raise ValueError("distractor evaluation limit must be positive")
        target_counts = _allocate_pattern_targets(
            target_sample_count,
            pattern_target_shares or FINANCE_PATTERN_TARGET_SHARES,
            tuple(sorted(self._patterns)),
        )
        binding_counts = {
            pattern_id: len(self._bindings_by_pattern.get(pattern_id, ()))
            for pattern_id in sorted(self._patterns)
        }
        region_counts: Counter[str] = Counter()
        metric_counts: Counter[str] = Counter()
        source_counts: Counter[str] = Counter()
        partition_counts: dict[str, Counter[str]] = {"A": Counter(), "B": Counter()}
        for pattern_id, catalog_bindings in self._bindings_by_pattern.items():
            for binding in catalog_bindings:
                region_counts[_binding_stratum_value(binding, 0, "unknown_region")] += 1
                metric_counts[_binding_stratum_value(binding, 1, "unknown_metric_category")] += 1
                source_counts[_binding_stratum_value(binding, 3, "unknown_source")] += 1
                partition_counts[self._partition(binding)][pattern_id] += 1

        execution_failures: Counter[str] = Counter()
        executable_bindings_by_pattern: dict[str, list[TaskBinding]] = {
            pattern_id: [] for pattern_id in self._patterns
        }
        execution_validation_count = 0
        for pattern_id, catalog_bindings in self._bindings_by_pattern.items():
            for binding in catalog_bindings:
                if self._partition(binding) != self.sampling_partition_id:
                    continue
                execution_validation_count += 1
                try:
                    self._pilot_case(binding)
                except (KeyError, ValueError) as error:
                    execution_failures[f"{pattern_id}|{_execution_failure_code(error)}"] += 1
                    continue
                executable_bindings_by_pattern[pattern_id].append(binding)
        executable_counts = {
            pattern_id: len(executable_bindings_by_pattern[pattern_id])
            for pattern_id in sorted(self._patterns)
        }
        difficulty_counts: Counter[str] = Counter()
        cell_exposure: Counter[str] = Counter()
        capacity_entries: list[_CapacityEntry] = []
        materialization_failures: Counter[str] = Counter()
        for pattern_id in sorted(self._patterns):
            for binding in sorted(
                executable_bindings_by_pattern.get(pattern_id, ()),
                key=lambda item: item.binding_hash,
            ):
                try:
                    case = self._contract_case(binding)
                    cell = build_synthesis_cell(
                        case.task.public,
                        case.corpus,
                        case.task.oracle.gold_evidence_ids,
                    )
                except (KeyError, ValueError) as error:
                    materialization_failures[
                        f"{pattern_id}|materialization:{_execution_failure_code(error)}"
                    ] += 1
                    continue
                difficulty_counts[cell.difficulty_bucket] += 1
                cell_exposure[cell.cell_id] += 1
                capacity_entries.append(
                    _CapacityEntry(
                        pattern_id=pattern_id,
                        binding_hash=binding.binding_hash,
                        cell_id=cell.cell_id,
                        evidence_version_ids=frozenset(
                            item.evidence_version_id for item in case.corpus.evidence
                        ),
                    )
                )
        execution_failures.update(materialization_failures)
        conflict_free_counts = _conflict_free_counts_by_key(
            capacity_entries,
            key=lambda entry: entry.pattern_id,
        )
        cell_conflict_free = _conflict_free_counts_by_key(
            capacity_entries,
            key=lambda entry: entry.cell_id,
        )
        dry_run_counts, materialization_collision_count = _materialization_dry_run(
            capacity_entries,
            target_counts,
        )
        distractor_yield: dict[str, _HardDistractorYield] = {}
        evaluated_total = 0
        for pattern_id in sorted(self._patterns):
            pattern_bindings = sorted(
                executable_bindings_by_pattern.get(pattern_id, ()),
                key=lambda item: item.binding_hash,
            )[:distractor_evaluation_limit_per_pattern]
            hard_total = 0
            hard_mismatch_total = 0
            single_violation_hard_count = 0
            hard_error_families: Counter[str] = Counter()
            broad_total = 0
            full_hard_count = 0
            for binding in pattern_bindings:
                gold = tuple(
                    self._evidence_by_id[evidence_id] for evidence_id in binding.evidence_ids
                )
                selection = self._real_distractors(binding, gold)
                hard_total += len(selection.hard)
                hard_mismatch_total += sum(
                    len(selection.mismatches[item.evidence_id]) for item in selection.hard
                )
                for item in selection.hard:
                    mismatches = selection.mismatches[item.evidence_id]
                    if len(mismatches) == 1:
                        single_violation_hard_count += 1
                        hard_error_families[mismatches[0]] += 1
                broad_total += len(selection.broad)
                full_hard_count += len(selection.hard) == 6
            evaluated = len(pattern_bindings)
            evaluated_total += evaluated
            distractor_yield[pattern_id] = {
                "evaluated_count": evaluated,
                "bindings_with_full_hard_set": full_hard_count,
                "mean_hard_count": hard_total / evaluated if evaluated else 0.0,
                "mean_mismatches_per_hard": (
                    hard_mismatch_total / hard_total if hard_total else 0.0
                ),
                "single_violation_hard_count": single_violation_hard_count,
                "single_violation_rate": (
                    single_violation_hard_count / hard_total if hard_total else 0.0
                ),
                "hard_error_family_counts": dict(sorted(hard_error_families.items())),
                "hard_error_family_count": len(hard_error_families),
                "full_hard_yield_rate": full_hard_count / evaluated if evaluated else 0.0,
                "mean_broad_count": broad_total / evaluated if evaluated else 0.0,
            }

        quota_shortfalls = {
            pattern_id: target_count - dry_run_counts.get(pattern_id, 0)
            for pattern_id, target_count in target_counts.items()
            if dry_run_counts.get(pattern_id, 0) < target_count
        }
        grounding_ready = (
            self._sample.sampled_count > 0
            and self._sample.source_grounding_valid_count >= self._sample.sampled_count
        )
        hard_semantics_ready = all(
            values["single_violation_rate"] == 1.0
            for values in distractor_yield.values()
            if values["evaluated_count"] > 0 and values["mean_hard_count"] > 0
        )
        status: Literal["ready", "blocked"] = (
            "ready"
            if (
                grounding_ready
                and hard_semantics_ready
                and not quota_shortfalls
                and not execution_failures
            )
            else "blocked"
        )
        warnings = []
        if not self._sample.complete_stream_scan:
            warnings.append("eligible_stream_scan_is_partial")
        if len(region_counts) < 2:
            warnings.append("binding_pool_has_single_region")
        if self._sample.source_grounding_failure_counts:
            warnings.append("source_grounding_rejections_present")
        if distractor_evaluation_limit_per_pattern < 5:
            warnings.append("distractor_audit_below_five_per_pattern")
        if any(
            conflict_free_counts.get(pattern_id, 0) < executable_counts.get(pattern_id, 0)
            for pattern_id in self._patterns
        ):
            warnings.append("corpus_overlap_reduces_materializable_capacity")
        if any(
            values["single_violation_rate"] < 1.0
            for values in distractor_yield.values()
            if values["evaluated_count"] > 0 and values["mean_hard_count"] > 0
        ):
            warnings.append("hard_distractor_contains_multiple_semantic_violations")
        payload = {
            "provider_contract_hash": self.provider_contract_hash,
            "kg_build_id": self._adapter.config.required_kg_build_id,
            "target_sample_count": target_sample_count,
            "archive_fact_node_count": int(self._inspection["fact_node_count"]),
            "eligible_stream_to_archive_fact_ratio": (
                min(
                    self._sample.scanned_count / int(self._inspection["fact_node_count"]),
                    1.0,
                )
                if int(self._inspection["fact_node_count"])
                else 0.0
            ),
            "complete_eligible_stream_scan": self._sample.complete_stream_scan,
            "target_counts_by_pattern": target_counts,
            "evidence_scanned_count": self._sample.scanned_count,
            "evidence_domain_valid_count": self._sample.domain_valid_count,
            "evidence_sampled_count": self._sample.sampled_count,
            "source_grounding_checked_count": self._sample.source_grounding_checked_count,
            "source_grounding_valid_count": self._sample.source_grounding_valid_count,
            "source_grounding_failure_counts": self._sample.source_grounding_failure_counts,
            "source_grounding_pass_rate": (
                self._sample.source_grounding_valid_count
                / self._sample.source_grounding_checked_count
                if self._sample.source_grounding_checked_count
                else 0.0
            ),
            "source_grounding_rejected_source_counts": (
                self._sample.source_grounding_rejected_source_counts
            ),
            "binding_count_by_pattern": binding_counts,
            "binding_count_by_region": dict(sorted(region_counts.items())),
            "binding_count_by_metric_category": dict(sorted(metric_counts.items())),
            "binding_count_by_source": dict(sorted(source_counts.items())),
            "sampling_partition_id": self.sampling_partition_id,
            "execution_validation_count": execution_validation_count,
            "executable_binding_count_by_pattern": executable_counts,
            "conflict_free_binding_count_by_pattern": {
                pattern_id: conflict_free_counts.get(pattern_id, 0)
                for pattern_id in sorted(self._patterns)
            },
            "materialization_dry_run_count_by_pattern": {
                pattern_id: dry_run_counts.get(pattern_id, 0)
                for pattern_id in sorted(self._patterns)
            },
            "materialization_collision_count": materialization_collision_count,
            "capacity_estimation_method": "full_corpus_disjoint_greedy_lower_bound.v1",
            "binding_execution_failure_counts": dict(sorted(execution_failures.items())),
            "partition_binding_counts": {
                partition: {
                    pattern_id: counts.get(pattern_id, 0) for pattern_id in sorted(self._patterns)
                }
                for partition, counts in sorted(partition_counts.items())
            },
            "evaluated_distractor_binding_count": evaluated_total,
            "hard_distractor_yield_by_pattern": distractor_yield,
            "difficulty_distribution": dict(sorted(difficulty_counts.items())),
            "synthesis_cell_count": len(cell_exposure),
            "cell_exposure_capacity": dict(sorted(cell_exposure.items())),
            "cell_conflict_free_capacity": dict(sorted(cell_conflict_free.items())),
            "quota_shortfalls": dict(sorted(quota_shortfalls.items())),
            "warnings": tuple(warnings),
            "status": status,
            "version": FINANCE_ARCHIVE_CAPACITY_VERSION,
        }
        return FinanceArchiveCapacityReport(
            report_id=canonical_hash(payload, prefix="finance_archive_capacity_report:"),
            **payload,
        )

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
        for source_binding in bindings:
            try:
                case = self._contract_case(source_binding)
            except (KeyError, ValueError):
                # Discovery intentionally over-generates; one invalid mined binding
                # must not exhaust the complete refined-Cell candidate stream.
                continue
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
                source_grounding_verifier=self._source_grounding_verifier,
                applied_binding_constraints=request.cell.active_binding_constraints,
            )

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

    def _real_distractors(
        self,
        binding: TaskBinding,
        gold: tuple[EvidenceItem, ...],
    ) -> RealDistractorSelection:
        cached = self._distractor_selection_cache.get(binding.binding_hash)
        if cached is not None:
            return cached
        selection = self._distractor_index.select(
            gold,
            hard_count=6,
            broad_count=2,
            preferred_hard_kinds=(
                "wrong_definition",
                "wrong_period",
                "wrong_scope",
                "wrong_entity",
                "stale_version",
                "forecast",
                "unit_mismatch",
                "currency_mismatch",
            ),
        )
        self._distractor_selection_cache[binding.binding_hash] = selection
        return selection

    def _pilot_case(self, binding: TaskBinding) -> PilotTaskCase:
        cached = self._pilot_case_cache.get(binding.binding_hash)
        if cached is not None:
            return cached
        gold = tuple(self._evidence_by_id[item] for item in binding.evidence_ids)
        pilot = build_task_cases(
            (binding,),
            gold,
            distractors_per_task=0,
            hard_distractors_per_task=0,
            hard_distractor_types=(),
            task_synthesizer=self._task_plugin,
        )[0]
        self._pilot_case_cache[binding.binding_hash] = pilot
        return pilot

    def _contract_case(self, binding: TaskBinding) -> ContractCase:
        cached = self._contract_case_cache.get(binding.binding_hash)
        if cached is not None:
            return cached
        gold = tuple(self._evidence_by_id[item] for item in binding.evidence_ids)
        pilot = self._pilot_case(binding)
        distractors = self._real_distractors(binding, gold)
        corpus_evidence = tuple(
            sorted((*gold, *distractors.evidence), key=lambda item: item.evidence_id)
        )
        corpus = EvidenceCorpus(
            corpus_id=canonical_hash(
                {
                    "task_id": pilot.task.task_id,
                    "evidence_version_ids": tuple(
                        item.evidence_version_id for item in corpus_evidence
                    ),
                },
                prefix="finance_archive_evidence_corpus:",
            ),
            evidence=corpus_evidence,
            build_id=pilot.bundle.graph_build_id,
        )
        case = ContractCase(
            domain="finance",
            bundle=pilot.bundle,
            corpus=corpus,
            proof_graph=pilot.proof_graph,
            task=pilot.task,
            registry=self._registry,
            semantic_policy=self._policy,
            quality_clause_provider=self._quality_provider,
            plugin_set=self._plugin_set,
            counterfactual_registry=self._counterfactual_registry,
            source_grounding_verifier=self._source_grounding_verifier,
        )
        self._contract_case_cache[binding.binding_hash] = case
        return case


def _execution_failure_code(error: Exception) -> str:
    detail = str(error).rsplit(":", 1)[-1].strip() or "unknown_execution_failure"
    return f"{type(error).__name__}:{detail}"


def _binding_stratum_value(binding: TaskBinding, index: int, fallback: str) -> str:
    return binding.stratum[index] if len(binding.stratum) > index else fallback


def _allocate_pattern_targets(
    target_sample_count: int,
    shares: dict[str, float],
    pattern_ids: tuple[str, ...],
) -> dict[str, int]:
    unknown = set(shares) - set(pattern_ids)
    if unknown:
        raise ValueError(f"capacity shares contain unknown Patterns: {sorted(unknown)}")
    if any(value < 0 for value in shares.values()):
        raise ValueError("capacity Pattern shares cannot be negative")
    total_share = sum(shares.values())
    if total_share <= 0:
        raise ValueError("capacity Pattern shares must have positive mass")
    exact = {
        pattern_id: target_sample_count * shares.get(pattern_id, 0.0) / total_share
        for pattern_id in pattern_ids
    }
    targets = {pattern_id: int(value) for pattern_id, value in exact.items()}
    remaining = target_sample_count - sum(targets.values())
    remainder_order = sorted(
        pattern_ids,
        key=lambda pattern_id: (
            -(exact[pattern_id] - targets[pattern_id]),
            pattern_id,
        ),
    )
    for pattern_id in remainder_order[:remaining]:
        targets[pattern_id] += 1
    return targets


def _conflict_free_counts_by_key(
    entries: Iterable[_CapacityEntry],
    *,
    key: Callable[[_CapacityEntry], str],
) -> dict[str, int]:
    groups: dict[str, list[_CapacityEntry]] = {}
    for entry in entries:
        groups.setdefault(str(key(entry)), []).append(entry)
    return {
        group_id: len(_greedy_disjoint_entries(group)) for group_id, group in sorted(groups.items())
    }


def _greedy_disjoint_entries(
    entries: Iterable[_CapacityEntry],
    *,
    forbidden: frozenset[str] = frozenset(),
    limit: int | None = None,
) -> tuple[_CapacityEntry, ...]:
    values = tuple(entries)
    frequencies = Counter(
        evidence_id for entry in values for evidence_id in entry.evidence_version_ids
    )
    ordered = sorted(
        values,
        key=lambda entry: (
            sum(frequencies[evidence_id] for evidence_id in entry.evidence_version_ids),
            len(entry.evidence_version_ids),
            entry.binding_hash,
        ),
    )
    selected: list[_CapacityEntry] = []
    used = set(forbidden)
    for entry in ordered:
        if entry.evidence_version_ids & used:
            continue
        selected.append(entry)
        used.update(entry.evidence_version_ids)
        if limit is not None and len(selected) >= limit:
            break
    return tuple(selected)


def _materialization_dry_run(
    entries: Iterable[_CapacityEntry],
    targets: dict[str, int],
) -> tuple[dict[str, int], int]:
    by_pattern: dict[str, list[_CapacityEntry]] = {pattern_id: [] for pattern_id in targets}
    for entry in entries:
        if entry.pattern_id in by_pattern:
            by_pattern[entry.pattern_id].append(entry)
    local_capacity = {
        pattern_id: len(_greedy_disjoint_entries(values))
        for pattern_id, values in by_pattern.items()
    }
    pattern_order = sorted(
        targets,
        key=lambda pattern_id: (
            local_capacity[pattern_id] / max(targets[pattern_id], 1),
            pattern_id,
        ),
    )
    used: set[str] = set()
    counts = {pattern_id: 0 for pattern_id in targets}
    collision_count = 0
    for pattern_id in pattern_order:
        target = targets[pattern_id]
        candidates = _rank_capacity_entries(by_pattern[pattern_id])
        for entry in candidates:
            if counts[pattern_id] >= target:
                break
            if entry.evidence_version_ids & used:
                collision_count += 1
                continue
            used.update(entry.evidence_version_ids)
            counts[pattern_id] += 1
    return counts, collision_count


def _rank_capacity_entries(entries: Iterable[_CapacityEntry]) -> tuple[_CapacityEntry, ...]:
    values = tuple(entries)
    frequencies = Counter(
        evidence_id for entry in values for evidence_id in entry.evidence_version_ids
    )
    return tuple(
        sorted(
            values,
            key=lambda entry: (
                sum(frequencies[evidence_id] for evidence_id in entry.evidence_version_ids),
                len(entry.evidence_version_ids),
                entry.binding_hash,
            ),
        )
    )
