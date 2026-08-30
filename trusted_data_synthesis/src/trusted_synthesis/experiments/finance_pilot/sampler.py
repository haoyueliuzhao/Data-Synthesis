from __future__ import annotations

import heapq
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from itertools import combinations
from typing import Any, TypeVar

from trusted_synthesis.core.evidence.payloads import ScalarObservation
from trusted_synthesis.core.evidence.schema import EvidenceItem
from trusted_synthesis.domains.finance.adapter import FinanceArchiveAdapter
from trusted_synthesis.domains.finance.patterns import (
    REGISTERED_FINANCIAL_COMPARISON_PAIRS,
    REGISTERED_FINANCIAL_RATIO_PAIRS,
)
from trusted_synthesis.domains.finance.policy import FinanceSemanticPolicy
from trusted_synthesis.experiments.finance_pilot.schema import FinancePilotConfig
from trusted_synthesis.hashing import canonical_hash

FINANCE_SAMPLING_STRATUM_VERSION = "finance_sampling_stratum.v3"
FINANCE_REAL_DISTRACTOR_INDEX_VERSION = "finance_real_distractor_index.v1"


@dataclass(frozen=True)
class TaskBinding:
    task_type: str
    evidence_ids: tuple[str, ...]
    stratum: tuple[str, ...]

    @property
    def binding_hash(self) -> str:
        return canonical_hash(
            {
                "task_type": self.task_type,
                "evidence_ids": self.evidence_ids,
                "stratum": self.stratum,
            },
            prefix="finance_pilot_binding:",
        )


@dataclass(frozen=True)
class EvidenceSample:
    evidence: tuple[EvidenceItem, ...]
    scanned_count: int
    domain_valid_count: int
    rejected_count: int
    stratum_counts: dict[str, int]
    sampled_count: int
    sampled_stratum_counts: dict[str, int]
    complete_stream_scan: bool
    source_grounding_checked_count: int
    source_grounding_valid_count: int
    source_grounding_rejected_count: int
    source_grounding_failure_counts: dict[str, int]
    source_grounding_rejected_source_counts: dict[str, int]


@dataclass(frozen=True)
class RealDistractorSelection:
    """Archive-native distractors plus hidden audit labels."""

    hard: tuple[EvidenceItem, ...]
    broad: tuple[EvidenceItem, ...]
    kinds: dict[str, str]
    mismatches: dict[str, tuple[str, ...]]

    @property
    def evidence(self) -> tuple[EvidenceItem, ...]:
        return (*self.hard, *self.broad)


class RealDistractorIndex:
    """Immutable inverted index for exact near-miss and broad distractor lookup.

    Each signature coordinate corresponds to exactly one semantic mismatch family.
    Intersecting every other coordinate therefore discovers only candidates with a
    single violation. Broad candidates use a binding-dependent deterministic probe
    so repeated materialization does not rescan the complete Archive.
    """

    index_version = FINANCE_REAL_DISTRACTOR_INDEX_VERSION

    def __init__(
        self,
        evidence: tuple[EvidenceItem, ...],
        *,
        broad_probe_limit: int = 1_024,
    ) -> None:
        if broad_probe_limit < 1:
            raise ValueError("broad distractor probe limit must be positive")
        self._evidence = evidence
        self._broad_probe_limit = broad_probe_limit
        self._signatures = tuple(_real_distractor_signature(item) for item in evidence)
        field_indexes: list[dict[Any, set[int]]] = [
            defaultdict(set) for _ in _REAL_DISTRACTOR_DIMENSIONS
        ]
        for index, signature in enumerate(self._signatures):
            for field_index, value in enumerate(signature):
                field_indexes[field_index][value].add(index)
        self._field_indexes = tuple(field_indexes)
        self._broad_order = tuple(
            sorted(
                range(len(evidence)),
                key=lambda index: canonical_hash(
                    evidence[index].evidence_version_id,
                    prefix="finance_real_distractor_broad_order:",
                ),
            )
        )

    def select(
        self,
        gold: tuple[EvidenceItem, ...],
        *,
        hard_count: int,
        broad_count: int,
        preferred_hard_kinds: tuple[str, ...] = (),
    ) -> RealDistractorSelection:
        if hard_count < 0 or broad_count < 0:
            raise ValueError("real distractor counts cannot be negative")
        if not gold or not self._evidence:
            return RealDistractorSelection(hard=(), broad=(), kinds={}, mismatches={})

        gold_ids = {item.evidence_id for item in gold}
        candidate_indexes: set[int] = set()
        for required in gold:
            signature = _real_distractor_signature(required)
            for omitted_index in range(len(_REAL_DISTRACTOR_DIMENSIONS)):
                matching_sets = [
                    self._field_indexes[field_index].get(value, set())
                    for field_index, value in enumerate(signature)
                    if field_index != omitted_index
                ]
                if not matching_sets or any(not values for values in matching_sets):
                    continue
                smallest = min(matching_sets, key=len)
                for candidate_index in smallest:
                    candidate_signature = self._signatures[candidate_index]
                    if candidate_signature[omitted_index] == signature[omitted_index]:
                        continue
                    if all(
                        candidate_signature[field_index] == signature[field_index]
                        for field_index in range(len(signature))
                        if field_index != omitted_index
                    ):
                        candidate_indexes.add(candidate_index)

        hard_profiles_by_id: dict[str, tuple[EvidenceItem, str, tuple[str, ...]]] = {}
        for candidate_index in candidate_indexes:
            item = self._evidence[candidate_index]
            if item.evidence_id in gold_ids or any(
                not _real_distractor_mismatches(item, required) for required in gold
            ):
                continue
            kind, mismatches = _closest_real_distractor_profile(item, gold)
            if kind is None or len(mismatches) != 1:
                continue
            hard_profiles_by_id[item.evidence_id] = (item, kind, mismatches)

        selected: list[tuple[EvidenceItem, str, tuple[str, ...]]] = []
        selected_ids: set[str] = set()
        hard_profiles = tuple(hard_profiles_by_id.values())
        for kind in preferred_hard_kinds:
            matches = [
                profile
                for profile in hard_profiles
                if profile[1] == kind and profile[0].evidence_id not in selected_ids
            ]
            if not matches:
                continue
            chosen = min(matches, key=lambda profile: _stable_item_key(profile[0], gold_ids))
            selected.append(chosen)
            selected_ids.add(chosen[0].evidence_id)
            if len(selected) >= hard_count:
                break

        if len(selected) < hard_count:
            remaining = sorted(
                (
                    profile
                    for profile in hard_profiles
                    if profile[0].evidence_id not in selected_ids
                ),
                key=lambda profile: (
                    _mismatch_priority(profile[1]),
                    _stable_item_key(profile[0], gold_ids),
                ),
            )
            for profile in remaining:
                selected.append(profile)
                selected_ids.add(profile[0].evidence_id)
                if len(selected) >= hard_count:
                    break

        broad_profiles: list[tuple[EvidenceItem, str, tuple[str, ...]]] = []
        if broad_count and self._broad_order:
            offset_hash = canonical_hash(
                tuple(sorted(gold_ids)),
                prefix="finance_real_distractor_broad_offset:",
            ).split(":", 1)[1]
            offset = int(offset_hash[:16], 16) % len(self._broad_order)
            probe_count = min(len(self._broad_order), self._broad_probe_limit)
            for position in range(probe_count):
                candidate_index = self._broad_order[(offset + position) % len(self._broad_order)]
                item = self._evidence[candidate_index]
                if item.evidence_id in gold_ids or item.evidence_id in selected_ids:
                    continue
                if any(not _real_distractor_mismatches(item, required) for required in gold):
                    continue
                kind, mismatches = _closest_real_distractor_profile(item, gold)
                if kind is None or len(mismatches) < 2:
                    continue
                broad_profiles.append((item, kind, mismatches))
            broad_profiles.sort(
                key=lambda profile: (
                    -len(profile[2]),
                    _stable_item_key(profile[0], gold_ids),
                )
            )

        broad = tuple(broad_profiles[:broad_count])
        profiles = (*selected, *broad)
        return RealDistractorSelection(
            hard=tuple(profile[0] for profile in selected),
            broad=tuple(profile[0] for profile in broad),
            kinds={profile[0].evidence_id: profile[1] for profile in profiles},
            mismatches={profile[0].evidence_id: profile[2] for profile in profiles},
        )


def sample_evidence(
    adapter: FinanceArchiveAdapter,
    config: FinancePilotConfig,
    policy: FinanceSemanticPolicy,
    source_grounding_verifier: Any | None = None,
) -> EvidenceSample:
    scan_limit = config.evidence_scan_limit or None
    strata: dict[str, int] = defaultdict(int)
    coherent_reservoirs: dict[tuple[str, ...], list[tuple[int, str, EvidenceItem]]] = defaultdict(
        list
    )
    diverse_reservoirs: dict[tuple[str, ...], list[tuple[int, str, EvidenceItem]]] = defaultdict(
        list
    )
    coherent_limit = max(1, config.stratum_reservoir_size // 2)
    diverse_limit = config.stratum_reservoir_size - coherent_limit
    scanned_count = 0
    domain_valid_count = 0
    for item in adapter.iter_evidence(limit=scan_limit):
        scanned_count += 1
        if not policy.validate_evidence(item).passed:
            continue
        domain_valid_count += 1
        stratum = _evidence_stratum(item)
        strata["|".join(stratum)] += 1
        _push_evidence_reservoir(
            coherent_reservoirs[stratum],
            item,
            _coherent_reservoir_rank(item),
            coherent_limit,
        )
        _push_evidence_reservoir(
            diverse_reservoirs[stratum],
            item,
            int(canonical_hash(item.evidence_id).split(":")[-1], 16),
            diverse_limit,
        )
    reservoir_by_id: dict[str, EvidenceItem] = {}
    for reservoir_group in (coherent_reservoirs, diverse_reservoirs):
        for heap in reservoir_group.values():
            for _, evidence_id, item in sorted(
                heap,
                key=lambda value: (-value[0], value[1]),
            ):
                reservoir_by_id.setdefault(evidence_id, item)
    reservoir_items = tuple(reservoir_by_id[evidence_id] for evidence_id in sorted(reservoir_by_id))
    grounding_failures: Counter[str] = Counter()
    grounding_rejected_sources: Counter[str] = Counter()
    if source_grounding_verifier is not None:
        grounded = []
        verification_items = sorted(
            reservoir_items,
            key=lambda item: (
                item.source_locator.raw_object_id or "",
                item.evidence_id,
            ),
        )
        for item in verification_items:
            report = source_grounding_verifier.verify(item)
            if report.passed:
                grounded.append(item)
                continue
            grounding_failures.update(report.failures)
            grounding_rejected_sources[item.source.source_id] += 1
        grounded_items = tuple(grounded)
    else:
        grounded_items = reservoir_items
    valid = _diverse_select(
        grounded_items,
        config.evidence_sample_size,
        key=_evidence_stratum,
        identity=lambda item: canonical_hash(item.evidence_id),
    )
    sampled_strata: dict[str, int] = defaultdict(int)
    for item in valid:
        sampled_strata["|".join(_evidence_stratum(item))] += 1
    return EvidenceSample(
        evidence=valid,
        scanned_count=scanned_count,
        domain_valid_count=domain_valid_count,
        rejected_count=scanned_count - domain_valid_count,
        stratum_counts=dict(sorted(strata.items())),
        sampled_count=len(valid),
        sampled_stratum_counts=dict(sorted(sampled_strata.items())),
        complete_stream_scan=scan_limit is None,
        source_grounding_checked_count=(
            len(reservoir_items) if source_grounding_verifier is not None else 0
        ),
        source_grounding_valid_count=(
            len(grounded_items) if source_grounding_verifier is not None else 0
        ),
        source_grounding_rejected_count=(
            len(reservoir_items) - len(grounded_items)
            if source_grounding_verifier is not None
            else 0
        ),
        source_grounding_failure_counts=dict(sorted(grounding_failures.items())),
        source_grounding_rejected_source_counts=dict(sorted(grounding_rejected_sources.items())),
    )


def discover_bindings(
    evidence: tuple[EvidenceItem, ...],
    config: FinancePilotConfig,
) -> tuple[TaskBinding, ...]:
    temporal_growth = _temporal_bindings(
        evidence,
        window=2,
        task_type="temporal_growth",
        require_relative_growth=True,
    )
    candidates = {
        "fact_retrieval": _lookup_bindings(evidence),
        "comparison": _comparison_bindings(evidence),
        "registered_cross_metric_comparison": _registered_cross_metric_bindings(evidence),
        "temporal_growth": temporal_growth,
        "temporal_average": _temporal_bindings(
            evidence,
            window=3,
            task_type="temporal_average",
        ),
        "temporal_absolute_change": _temporal_bindings(
            evidence,
            window=2,
            task_type="temporal_absolute_change",
        ),
        "registered_ratio": _registered_ratio_bindings(evidence),
        "derived_growth_comparison": _derived_growth_comparison_bindings(
            evidence,
            temporal_growth,
        ),
    }
    selected: list[TaskBinding] = []
    shortfalls = {}
    for task_type, quota in config.task_quotas.items():
        chosen = _diverse_select(
            candidates[task_type],
            quota,
            key=lambda item: item.stratum,
            identity=lambda item: item.binding_hash,
        )
        selected.extend(chosen)
        if len(chosen) < quota:
            shortfalls[task_type] = quota - len(chosen)
    if shortfalls and config.require_full_quota:
        raise ValueError(f"finance pilot task quota shortfall: {shortfalls}")
    return tuple(sorted(selected, key=lambda item: (item.task_type, item.binding_hash)))


def select_distractors(
    evidence: tuple[EvidenceItem, ...],
    gold: tuple[EvidenceItem, ...],
    count: int,
) -> tuple[EvidenceItem, ...]:
    gold_ids = {item.evidence_id for item in gold}
    subjects = {item.subject.subject_id for item in gold}
    predicates = {item.predicate for item in gold}
    times = {_time_label(item) for item in gold}
    definitions = {item.definition.definition_id for item in gold}
    units = {_unit_currency(item) for item in gold}
    candidates = tuple(item for item in evidence if item.evidence_id not in gold_ids)
    categories: tuple[Callable[[EvidenceItem], bool], ...] = (
        lambda item: item.subject.subject_id not in subjects and item.predicate in predicates,
        lambda item: (
            item.subject.subject_id in subjects
            and item.predicate in predicates
            and _time_label(item) not in times
        ),
        lambda item: item.subject.subject_id in subjects and item.predicate not in predicates,
        lambda item: (
            item.predicate in predicates and item.definition.definition_id not in definitions
        ),
        lambda item: item.predicate in predicates and _unit_currency(item) not in units,
        lambda item: True,
    )
    selected: list[EvidenceItem] = []
    selected_ids: set[str] = set()
    for predicate in categories:
        matches = [item for item in candidates if predicate(item)]
        matches.sort(key=lambda item: _stable_item_key(item, gold_ids))
        for item in matches:
            if item.evidence_id in selected_ids or _matches_public_scope(item, gold):
                continue
            selected.append(item)
            selected_ids.add(item.evidence_id)
            break
        if len(selected) >= count:
            break
    if len(selected) < count:
        remaining = sorted(candidates, key=lambda item: _stable_item_key(item, gold_ids))
        for item in remaining:
            if item.evidence_id in selected_ids or _matches_public_scope(item, gold):
                continue
            selected.append(item)
            selected_ids.add(item.evidence_id)
            if len(selected) >= count:
                break
    return tuple(selected[:count])


def select_real_distractors(
    evidence: tuple[EvidenceItem, ...],
    gold: tuple[EvidenceItem, ...],
    *,
    hard_count: int,
    broad_count: int,
    preferred_hard_kinds: tuple[str, ...] = (),
) -> RealDistractorSelection:
    """Select immutable near-misses from the pinned archive without mutating evidence."""

    if hard_count < 0 or broad_count < 0:
        raise ValueError("real distractor counts cannot be negative")
    gold_ids = {item.evidence_id for item in gold}
    profiles = []
    for item in evidence:
        if item.evidence_id in gold_ids:
            continue
        kind, mismatches = _closest_real_distractor_profile(item, gold)
        if kind is None:
            continue
        profiles.append((item, kind, mismatches))

    hard_profiles = [profile for profile in profiles if len(profile[2]) == 1]
    selected: list[tuple[EvidenceItem, str, tuple[str, ...]]] = []
    selected_ids: set[str] = set()
    for kind in preferred_hard_kinds:
        matches = [
            profile
            for profile in hard_profiles
            if profile[1] == kind and profile[0].evidence_id not in selected_ids
        ]
        if not matches:
            continue
        chosen = min(
            matches,
            key=lambda profile: (
                len(profile[2]),
                _stable_item_key(profile[0], gold_ids),
            ),
        )
        selected.append(chosen)
        selected_ids.add(chosen[0].evidence_id)
        if len(selected) >= hard_count:
            break

    if len(selected) < hard_count:
        remaining = sorted(
            (profile for profile in hard_profiles if profile[0].evidence_id not in selected_ids),
            key=lambda profile: (
                len(profile[2]),
                _mismatch_priority(profile[1]),
                _stable_item_key(profile[0], gold_ids),
            ),
        )
        for profile in remaining:
            selected.append(profile)
            selected_ids.add(profile[0].evidence_id)
            if len(selected) >= hard_count:
                break

    broad = sorted(
        (profile for profile in profiles if profile[0].evidence_id not in selected_ids),
        key=lambda profile: (
            -len(profile[2]),
            _stable_item_key(profile[0], gold_ids),
        ),
    )[:broad_count]
    hard = tuple(profile[0] for profile in selected)
    broad_items = tuple(profile[0] for profile in broad)
    kinds = {profile[0].evidence_id: profile[1] for profile in (*selected, *broad)}
    mismatch_map = {profile[0].evidence_id: profile[2] for profile in (*selected, *broad)}
    return RealDistractorSelection(
        hard=hard,
        broad=broad_items,
        kinds=dict(sorted(kinds.items())),
        mismatches=dict(sorted(mismatch_map.items())),
    )


def _closest_real_distractor_profile(
    distractor: EvidenceItem,
    required: tuple[EvidenceItem, ...],
) -> tuple[str | None, tuple[str, ...]]:
    profiles = []
    for item in required:
        mismatches = _real_distractor_mismatches(distractor, item)
        if not mismatches:
            continue
        kind = min(mismatches, key=_mismatch_priority)
        profiles.append((kind, mismatches, item.evidence_id))
    if not profiles:
        return None, ()
    kind, mismatches, _ = min(
        profiles,
        key=lambda profile: (
            len(profile[1]),
            _mismatch_priority(profile[0]),
            profile[2],
        ),
    )
    return kind, mismatches


_REAL_DISTRACTOR_DIMENSIONS = (
    "wrong_entity",
    "wrong_metric",
    "wrong_definition",
    "wrong_scope",
    "wrong_period",
    "unit_mismatch",
    "currency_mismatch",
    "time_basis_mismatch",
    "frequency_mismatch",
    "period_type_mismatch",
    "wrong_source",
    "source_authority_mismatch",
    "stale_version",
    "forecast",
)


def _real_distractor_signature(item: EvidenceItem) -> tuple[Any, ...]:
    unit, currency = _unit_currency(item)
    authority = getattr(item.source.authority, "value", str(item.source.authority))
    epistemic_status = getattr(
        item.epistemic_status,
        "value",
        str(item.epistemic_status),
    )
    return (
        item.subject.subject_id,
        item.predicate,
        item.definition.definition_id,
        _scope_key(item),
        _time_label(item),
        unit,
        currency,
        item.temporal_context.basis,
        item.temporal_context.frequency,
        item.definition.attributes.get("period_type"),
        item.source.source_id,
        authority,
        (epistemic_status, item.provenance.build_ids.get("kg")),
        _is_forecast(item),
    )


def _real_distractor_mismatches(
    candidate: EvidenceItem,
    required: EvidenceItem,
) -> tuple[str, ...]:
    mismatches = []
    if candidate.subject.subject_id != required.subject.subject_id:
        mismatches.append("wrong_entity")
    if candidate.predicate != required.predicate:
        mismatches.append("wrong_metric")
    if candidate.definition.definition_id != required.definition.definition_id:
        mismatches.append("wrong_definition")
    if _scope_key(candidate) != _scope_key(required):
        mismatches.append("wrong_scope")
    if _time_label(candidate) != _time_label(required):
        mismatches.append("wrong_period")
    candidate_unit, candidate_currency = _unit_currency(candidate)
    required_unit, required_currency = _unit_currency(required)
    if candidate_unit != required_unit:
        mismatches.append("unit_mismatch")
    if candidate_currency != required_currency:
        mismatches.append("currency_mismatch")
    if candidate.temporal_context.basis != required.temporal_context.basis:
        mismatches.append("time_basis_mismatch")
    if candidate.temporal_context.frequency != required.temporal_context.frequency:
        mismatches.append("frequency_mismatch")
    if candidate.definition.attributes.get("period_type") != required.definition.attributes.get(
        "period_type"
    ):
        mismatches.append("period_type_mismatch")
    if candidate.source.source_id != required.source.source_id:
        mismatches.append("wrong_source")
    if candidate.source.authority != required.source.authority:
        mismatches.append(
            "lower_authority"
            if _authority_rank(candidate) < _authority_rank(required)
            else "source_authority_mismatch"
        )
    if (
        candidate.epistemic_status != required.epistemic_status
        or candidate.provenance.build_ids.get("kg") != required.provenance.build_ids.get("kg")
    ):
        mismatches.append("stale_version")
    if _is_forecast(candidate) != _is_forecast(required):
        mismatches.append("forecast")
    return tuple(sorted(set(mismatches), key=_mismatch_priority))


def _scope_key(item: EvidenceItem) -> tuple[str | None, str | None]:
    if item.scope is None:
        return None, None
    return item.scope.scope_type, item.scope.scope_id


def _is_forecast(item: EvidenceItem) -> bool:
    return bool(item.domain_context.get("is_forecast", False))


def _authority_rank(item: EvidenceItem) -> int:
    return {
        "unknown": 0,
        "secondary": 1,
        "curated_database": 2,
        "peer_reviewed": 3,
        "official": 4,
        "primary": 5,
    }.get(item.source.authority.value, 0)


def _mismatch_priority(kind: str) -> int:
    order = (
        "wrong_definition",
        "wrong_period",
        "wrong_scope",
        "wrong_entity",
        "wrong_metric",
        "unit_mismatch",
        "currency_mismatch",
        "period_type_mismatch",
        "time_basis_mismatch",
        "frequency_mismatch",
        "forecast",
        "stale_version",
        "lower_authority",
        "source_authority_mismatch",
        "wrong_source",
    )
    return order.index(kind) if kind in order else len(order)


def _lookup_bindings(evidence: tuple[EvidenceItem, ...]) -> tuple[TaskBinding, ...]:
    return tuple(
        TaskBinding(
            task_type="fact_retrieval",
            evidence_ids=(item.evidence_id,),
            stratum=_evidence_stratum(item),
        )
        for item in evidence
    )


def _comparison_bindings(evidence: tuple[EvidenceItem, ...]) -> tuple[TaskBinding, ...]:
    groups: dict[tuple[Any, ...], list[EvidenceItem]] = defaultdict(list)
    for item in evidence:
        groups[_comparison_key(item)].append(item)
    bindings: list[TaskBinding] = []
    for items in groups.values():
        by_subject: dict[str, EvidenceItem] = {}
        for item in sorted(items, key=lambda value: value.evidence_id):
            by_subject.setdefault(item.subject.subject_id, item)
        unique = sorted(by_subject.values(), key=lambda value: value.evidence_id)
        group_bindings = []
        for left, right in combinations(unique, 2):
            group_bindings.append(
                TaskBinding(
                    task_type="comparison",
                    evidence_ids=(left.evidence_id, right.evidence_id),
                    stratum=(
                        _combined_region((left, right)),
                        _metric_category(left),
                        left.temporal_context.frequency or "unknown_frequency",
                        left.source.source_id,
                        str(left.domain_context.get("verification_status") or "unknown_status"),
                    ),
                )
            )
        bindings.extend(_deterministic_binding_reservoir(group_bindings, 64))
    return tuple(bindings)


def _temporal_bindings(
    evidence: tuple[EvidenceItem, ...],
    *,
    window: int,
    task_type: str,
    require_relative_growth: bool = False,
) -> tuple[TaskBinding, ...]:
    groups: dict[tuple[Any, ...], list[EvidenceItem]] = defaultdict(list)
    for item in evidence:
        groups[_series_key(item)].append(item)
    bindings: list[TaskBinding] = []
    for items in groups.values():
        if _series_period_class(items[0]) == "unsupported_ytd":
            continue
        by_period: dict[date, EvidenceItem] = {}
        for item in sorted(
            items,
            key=lambda value: (
                -value.extraction_confidence,
                value.evidence_id,
            ),
        ):
            period = _time_point(item)
            if period is not None:
                by_period.setdefault(period, item)
        ordered = [by_period[key] for key in sorted(by_period)]
        group_bindings = []
        for start in range(len(ordered) - window + 1):
            selected = tuple(ordered[start : start + window])
            if not all(
                _periods_are_adjacent(left, right)
                for left, right in zip(selected, selected[1:], strict=False)
            ):
                continue
            if require_relative_growth and not _relative_growth_allowed(selected[0]):
                continue
            group_bindings.append(
                TaskBinding(
                    task_type=task_type,
                    evidence_ids=tuple(item.evidence_id for item in selected),
                    stratum=_evidence_stratum(selected[0]),
                )
            )
        bindings.extend(_deterministic_binding_reservoir(group_bindings, 32))
    return tuple(bindings)


def _registered_ratio_bindings(
    evidence: tuple[EvidenceItem, ...],
) -> tuple[TaskBinding, ...]:
    groups: dict[tuple[Any, ...], list[EvidenceItem]] = defaultdict(list)
    for item in evidence:
        groups[_ratio_context_key(item)].append(item)
    bindings = []
    for items in groups.values():
        by_predicate: dict[str, EvidenceItem] = {}
        for item in sorted(items, key=lambda value: value.evidence_id):
            by_predicate.setdefault(item.predicate, item)
        for numerator_predicate, denominator_predicate in REGISTERED_FINANCIAL_RATIO_PAIRS:
            numerator = by_predicate.get(numerator_predicate)
            denominator = by_predicate.get(denominator_predicate)
            if numerator is None or denominator is None:
                continue
            if not numerator.definition.definition_id or not denominator.definition.definition_id:
                continue
            if _numeric_value(denominator) == 0:
                continue
            bindings.append(
                TaskBinding(
                    task_type="registered_ratio",
                    evidence_ids=(numerator.evidence_id, denominator.evidence_id),
                    stratum=(
                        *_evidence_stratum(numerator),
                        f"{numerator_predicate}/{denominator_predicate}",
                    ),
                )
            )
    return tuple(bindings)


def _registered_cross_metric_bindings(
    evidence: tuple[EvidenceItem, ...],
) -> tuple[TaskBinding, ...]:
    groups: dict[tuple[Any, ...], list[EvidenceItem]] = defaultdict(list)
    for item in evidence:
        groups[_ratio_context_key(item)].append(item)
    policy = FinanceSemanticPolicy()
    bindings = []
    for items in groups.values():
        by_predicate: dict[str, EvidenceItem] = {}
        for item in sorted(items, key=lambda value: value.evidence_id):
            by_predicate.setdefault(item.predicate, item)
        for left_predicate, right_predicate in REGISTERED_FINANCIAL_COMPARISON_PAIRS:
            left = by_predicate.get(left_predicate)
            right = by_predicate.get(right_predicate)
            if left is None or right is None:
                continue
            if not policy.validate_registered_comparison_pair(
                left,
                right,
                REGISTERED_FINANCIAL_COMPARISON_PAIRS,
            ).comparable:
                continue
            bindings.append(
                TaskBinding(
                    task_type="registered_cross_metric_comparison",
                    evidence_ids=(left.evidence_id, right.evidence_id),
                    stratum=(
                        *_evidence_stratum(left),
                        "raw_static_graph_pattern",
                        f"{left_predicate}/{right_predicate}",
                    ),
                )
            )
    return tuple(bindings)


def _derived_growth_comparison_bindings(
    evidence: tuple[EvidenceItem, ...],
    growth_bindings: tuple[TaskBinding, ...],
) -> tuple[TaskBinding, ...]:
    by_id = {item.evidence_id: item for item in evidence}
    groups: dict[tuple[Any, ...], list[TaskBinding]] = defaultdict(list)
    for binding in growth_bindings:
        earlier, later = (by_id[evidence_id] for evidence_id in binding.evidence_ids)
        groups[_derived_window_key(earlier, later)].append(binding)
    output: list[TaskBinding] = []
    for group in groups.values():
        by_subject: dict[str, TaskBinding] = {}
        for binding in sorted(group, key=lambda item: item.binding_hash):
            subject_id = by_id[binding.evidence_ids[0]].subject.subject_id
            by_subject.setdefault(subject_id, binding)
        group_bindings = []
        for left, right in combinations(by_subject.values(), 2):
            left_earlier = by_id[left.evidence_ids[0]]
            right_earlier = by_id[right.evidence_ids[0]]
            group_bindings.append(
                TaskBinding(
                    task_type="derived_growth_comparison",
                    evidence_ids=(
                        *left.evidence_ids,
                        *right.evidence_ids,
                    ),
                    stratum=(
                        _combined_region((left_earlier, right_earlier)),
                        _metric_category(left_earlier),
                        left_earlier.temporal_context.frequency or "unknown_frequency",
                        left_earlier.source.source_id,
                        "derived_growth_comparison",
                    ),
                )
            )
        output.extend(_deterministic_binding_reservoir(group_bindings, 64))
    return tuple(output)


def _ratio_context_key(item: EvidenceItem) -> tuple[Any, ...]:
    return (
        item.subject.subject_id,
        _period_identity_key(item),
        item.source.source_id,
        item.temporal_context.basis,
        item.temporal_context.frequency,
        _scope_key(item),
        _unit_currency(item),
    )


def _derived_window_key(
    earlier: EvidenceItem,
    later: EvidenceItem,
) -> tuple[Any, ...]:
    return (
        earlier.predicate,
        _time_point(earlier),
        _time_point(later),
        earlier.source.source_id,
        earlier.definition.definition_id,
        _unit_currency(earlier),
        earlier.temporal_context.basis,
        earlier.temporal_context.frequency,
        earlier.scope.scope_type if earlier.scope else None,
        earlier.definition.attributes.get("period_type"),
    )


def _comparison_key(item: EvidenceItem) -> tuple[Any, ...]:
    return (
        item.predicate,
        _time_label(item),
        item.definition.definition_id,
        _unit_currency(item),
        item.temporal_context.basis,
        item.temporal_context.frequency,
        item.scope.scope_type if item.scope else None,
        item.definition.attributes.get("period_type"),
    )


def _series_key(item: EvidenceItem) -> tuple[Any, ...]:
    return (
        item.subject.subject_id,
        item.predicate,
        item.source.source_id,
        item.definition.definition_id,
        _unit_currency(item),
        item.temporal_context.basis,
        item.temporal_context.frequency,
        item.scope.scope_type if item.scope else None,
        item.definition.attributes.get("period_type"),
        _series_period_class(item),
    )


def _evidence_stratum(item: EvidenceItem) -> tuple[str, ...]:
    return (
        _region(item),
        _metric_category(item),
        item.temporal_context.frequency or "unknown_frequency",
        item.source.source_id,
        str(item.domain_context.get("verification_status") or "unknown_status"),
        item.predicate,
        item.subject.subject_type,
        _year_bucket(item),
    )


def _year_bucket(item: EvidenceItem) -> str:
    point = _time_point(item)
    if point is None:
        return "unknown_year"
    start = point.year - point.year % 5
    return f"{start}-{start + 4}"


def _metric_category(item: EvidenceItem) -> str:
    return str(item.definition.attributes.get("metric_category") or "unknown_metric_category")


def _region(item: EvidenceItem) -> str:
    attributes = item.subject.attributes
    value = " ".join(
        str(attributes.get(key) or "") for key in ("country", "market", "exchange")
    ).casefold()
    greater_china_markers = (
        "china",
        "chinese",
        "hong kong",
        "macau",
        "mainland",
        "cn",
        "hk",
        "sse",
        "szse",
        "hkex",
    )
    return (
        "mainland_hong_kong_macau"
        if any(marker in value for marker in greater_china_markers)
        else "global"
    )


def _combined_region(items: tuple[EvidenceItem, ...]) -> str:
    regions = {_region(item) for item in items}
    return next(iter(regions)) if len(regions) == 1 else "cross_region"


def _time_point(item: EvidenceItem) -> date | None:
    context = item.temporal_context
    return context.valid_to or context.observed_at or context.valid_from


def _period_identity_key(
    item: EvidenceItem,
) -> tuple[str | None, str | None, str | None, str | None]:
    context = item.temporal_context
    return (
        context.label,
        context.valid_from.isoformat() if context.valid_from else None,
        context.valid_to.isoformat() if context.valid_to else None,
        context.observed_at.isoformat() if context.observed_at else None,
    )


def _time_label(item: EvidenceItem) -> str:
    context = item.temporal_context
    point = _time_point(item)
    return context.label or (point.isoformat() if point else "unspecified")


def _unit_currency(item: EvidenceItem) -> tuple[str | None, str | None]:
    payload = item.payload
    if not isinstance(payload, ScalarObservation):
        return None, None
    return payload.unit, payload.currency


def _numeric_value(item: EvidenceItem) -> Decimal:
    payload = item.payload
    if not isinstance(payload, ScalarObservation):
        raise ValueError(f"pilot requires scalar evidence: {item.evidence_id}")
    return Decimal(str(payload.value))


def _relative_growth_allowed(item: EvidenceItem) -> bool:
    if _numeric_value(item) <= 0:
        return False
    payload = item.payload
    if not isinstance(payload, ScalarObservation):
        return False
    unit = str(payload.unit or "").casefold()
    default_unit = str(item.definition.attributes.get("default_unit") or "").casefold()
    rate_markers = ("percent", "%", "basis point", "percentage point")
    return not any(marker in unit or marker in default_unit for marker in rate_markers)


def _latest_contiguous_window(
    ordered: list[EvidenceItem], window: int
) -> tuple[EvidenceItem, ...] | None:
    for end in range(len(ordered), window - 1, -1):
        candidate = tuple(ordered[end - window : end])
        if all(
            _periods_are_adjacent(left, right)
            for left, right in zip(candidate, candidate[1:], strict=False)
        ):
            return candidate
    return None


def _periods_are_adjacent(left: EvidenceItem, right: EvidenceItem) -> bool:
    left_date = _time_point(left)
    right_date = _time_point(right)
    if left_date is None or right_date is None or left_date >= right_date:
        return False
    period_class = _series_period_class(left)
    if period_class != _series_period_class(right):
        return False
    if period_class == "fiscal_quarter":
        left_index = _fiscal_quarter_index(left)
        right_index = _fiscal_quarter_index(right)
        return left_index is not None and right_index == left_index + 1
    if period_class in {"annual", "yearly"}:
        return right_date.year == left_date.year + 1
    if period_class == "quarterly":
        return _month_index(right_date) == _month_index(left_date) + 3
    if period_class == "monthly":
        return _month_index(right_date) == _month_index(left_date) + 1
    days = (right_date - left_date).days
    if period_class == "weekly":
        return 5 <= days <= 10
    if period_class == "daily":
        return 1 <= days <= 10
    return False


def _series_period_class(item: EvidenceItem) -> str:
    fiscal_quarter = str(item.domain_context.get("fiscal_quarter") or "").upper()
    if "YTD" in fiscal_quarter:
        return "unsupported_ytd"
    if fiscal_quarter == "FY":
        return "annual"
    if fiscal_quarter in {"Q1", "Q2", "Q3", "Q4"}:
        return "fiscal_quarter"
    return str(item.temporal_context.frequency or "unknown").casefold()


def _fiscal_quarter_index(item: EvidenceItem) -> int | None:
    fiscal_year = item.domain_context.get("fiscal_year")
    fiscal_quarter = str(item.domain_context.get("fiscal_quarter") or "").upper()
    quarter = {"Q1": 0, "Q2": 1, "Q3": 2, "Q4": 3}.get(fiscal_quarter)
    if fiscal_year is None or quarter is None:
        return None
    return int(fiscal_year) * 4 + quarter


def _month_index(value: date) -> int:
    return value.year * 12 + value.month


def _matches_public_scope(item: EvidenceItem, gold: tuple[EvidenceItem, ...]) -> bool:
    return (
        item.subject.subject_id in {value.subject.subject_id for value in gold}
        and item.predicate in {value.predicate for value in gold}
        and _time_label(item) in {_time_label(value) for value in gold}
    )


def _stable_item_key(item: EvidenceItem, gold_ids: set[str]) -> str:
    return canonical_hash(
        {"evidence_id": item.evidence_id, "gold_ids": sorted(gold_ids)},
        prefix="finance_pilot_distractor:",
    )


def _deterministic_binding_reservoir(
    bindings: Iterable[TaskBinding],
    limit: int,
) -> tuple[TaskBinding, ...]:
    if limit < 1:
        raise ValueError("binding reservoir limit must be positive")
    unique = {binding.binding_hash: binding for binding in bindings}
    return tuple(
        unique[key]
        for key in sorted(
            unique,
            key=lambda value: canonical_hash(
                value,
                prefix="finance_binding_reservoir:",
            ),
        )[:limit]
    )


T = TypeVar("T")


def _coherent_reservoir_rank(item: EvidenceItem) -> int:
    return int(
        canonical_hash(
            {
                "subject_id": item.subject.subject_id,
                "scope": _scope_key(item),
                "source_id": item.source.source_id,
            },
            prefix="finance_coherent_evidence_reservoir:",
        ).split(":")[-1],
        16,
    )


def _push_evidence_reservoir(
    heap: list[tuple[int, str, EvidenceItem]],
    item: EvidenceItem,
    rank: int,
    limit: int,
) -> None:
    if limit <= 0:
        return
    entry = (-rank, item.evidence_id, item)
    if len(heap) < limit:
        heapq.heappush(heap, entry)
    elif rank < -heap[0][0]:
        heapq.heapreplace(heap, entry)


def _diverse_select(
    items: Iterable[T],
    quota: int,
    *,
    key: Callable[[T], tuple[str, ...]],
    identity: Callable[[T], str],
) -> tuple[T, ...]:
    buckets: dict[tuple[str, ...], list[T]] = defaultdict(list)
    for item in items:
        buckets[key(item)].append(item)
    for bucket in buckets.values():
        bucket.sort(key=identity)
    selected: list[T] = []
    active = sorted(buckets, key=lambda value: canonical_hash(value))
    while active and len(selected) < quota:
        next_active: list[tuple[str, ...]] = []
        for bucket_key in active:
            bucket = buckets[bucket_key]
            if bucket and len(selected) < quota:
                selected.append(bucket.pop(0))
            if bucket:
                next_active.append(bucket_key)
        active = next_active
    return tuple(selected)
