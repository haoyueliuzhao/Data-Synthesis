from __future__ import annotations

import heapq
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, TypeVar

from trusted_synthesis.core.evidence.payloads import ScalarObservation
from trusted_synthesis.core.evidence.schema import EvidenceItem
from trusted_synthesis.domains.finance.adapter import FinanceArchiveAdapter
from trusted_synthesis.domains.finance.policy import FinanceSemanticPolicy
from trusted_synthesis.experiments.finance_pilot.schema import FinancePilotConfig
from trusted_synthesis.hashing import canonical_hash


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


def sample_evidence(
    adapter: FinanceArchiveAdapter,
    config: FinancePilotConfig,
    policy: FinanceSemanticPolicy,
    source_grounding_verifier: Any | None = None,
) -> EvidenceSample:
    scan_limit = config.evidence_scan_limit or None
    strata: dict[str, int] = defaultdict(int)
    reservoirs: dict[tuple[str, ...], list[tuple[int, str, EvidenceItem]]] = defaultdict(list)
    scanned_count = 0
    domain_valid_count = 0
    for item in adapter.iter_evidence(limit=scan_limit):
        scanned_count += 1
        if not policy.validate_evidence(item).passed:
            continue
        domain_valid_count += 1
        stratum = _evidence_stratum(item)
        strata["|".join(stratum)] += 1
        rank = int(canonical_hash(item.evidence_id).split(":")[-1], 16)
        heap = reservoirs[stratum]
        entry = (-rank, item.evidence_id, item)
        if len(heap) < config.stratum_reservoir_size:
            heapq.heappush(heap, entry)
        elif rank < -heap[0][0]:
            heapq.heapreplace(heap, entry)
    reservoir_items = tuple(
        item
        for heap in reservoirs.values()
        for _, _, item in sorted(heap, key=lambda value: (-value[0], value[1]))
    )
    grounding_failures: Counter[str] = Counter()
    grounding_rejected_sources: Counter[str] = Counter()
    if source_grounding_verifier is not None:
        grounded = []
        for item in reservoir_items:
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
    candidates = {
        "fact_retrieval": _lookup_bindings(evidence),
        "comparison": _comparison_bindings(evidence),
        "temporal_growth": _temporal_bindings(evidence, window=2),
        "temporal_average": _temporal_bindings(evidence, window=3),
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
    bindings = []
    for items in groups.values():
        by_subject: dict[str, EvidenceItem] = {}
        for item in sorted(items, key=lambda value: value.evidence_id):
            by_subject.setdefault(item.subject.subject_id, item)
        unique = sorted(by_subject.values(), key=lambda value: value.evidence_id)
        if len(unique) < 2:
            continue
        left, right = unique[0], unique[-1]
        bindings.append(
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
    return tuple(bindings)


def _temporal_bindings(
    evidence: tuple[EvidenceItem, ...], *, window: int
) -> tuple[TaskBinding, ...]:
    groups: dict[tuple[Any, ...], list[EvidenceItem]] = defaultdict(list)
    for item in evidence:
        groups[_series_key(item)].append(item)
    bindings = []
    task_type = "temporal_growth" if window == 2 else "temporal_average"
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
        if len(ordered) < window:
            continue
        selected = _latest_contiguous_window(ordered, window)
        if selected is None:
            continue
        if window == 2 and not _relative_growth_allowed(selected[0]):
            continue
        first = selected[0]
        bindings.append(
            TaskBinding(
                task_type=task_type,
                evidence_ids=tuple(item.evidence_id for item in selected),
                stratum=_evidence_stratum(first),
            )
        )
    return tuple(bindings)


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
    )


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


T = TypeVar("T")


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
