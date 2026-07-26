from __future__ import annotations

from collections import defaultdict
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


def sample_evidence(
    adapter: FinanceArchiveAdapter,
    config: FinancePilotConfig,
    policy: FinanceSemanticPolicy,
) -> EvidenceSample:
    observed = tuple(adapter.iter_evidence(limit=config.evidence_scan_limit))
    valid = tuple(item for item in observed if policy.validate_evidence(item).passed)
    strata: dict[str, int] = defaultdict(int)
    for item in valid:
        strata["|".join(_evidence_stratum(item))] += 1
    return EvidenceSample(
        evidence=valid,
        scanned_count=len(observed),
        domain_valid_count=len(valid),
        rejected_count=len(observed) - len(valid),
        stratum_counts=dict(sorted(strata.items())),
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
        selected = tuple(ordered[-window:])
        if window == 2 and _numeric_value(selected[0]) == 0:
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
