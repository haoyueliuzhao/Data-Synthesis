from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping

from finraw.builds import finish_build, start_build
from finraw.db.client import DBProtocol
from finraw.regional_share_audit import (
    GREATER_CHINA,
    INTERNATIONAL,
    MIXED_GLOBAL,
    UNCLASSIFIED,
    classify_entity,
    classify_entity_scope,
    classify_source,
    distribution,
)


FACT_UNIVERSE_POLICY_VERSION = "1.2.0"
BROAD_INTERNATIONAL_REGIONS = {INTERNATIONAL, MIXED_GLOBAL}
MEMBER_COLUMNS = [
    "membership_id",
    "universe_build_id",
    "fact_id",
    "region_bucket",
    "stratum_key",
    "selection_rank",
    "selection_reason",
]
DERIVED_MEMBER_COLUMNS = [
    "membership_id",
    "universe_build_id",
    "derived_id",
    "region_bucket",
    "stratum_key",
    "selection_rank",
    "selection_reason",
]


@dataclass(frozen=True)
class DerivedChain:
    derived_id: str
    derived_type: str
    region_bucket: str
    input_fact_ids: frozenset[str]


def build_fact_universe(
    db: DBProtocol,
    config: dict[str, Any],
    *,
    output_dir: str | None = None,
    batch_size: int = 10_000,
) -> dict[str, Any]:
    policy = dict(config.get("fact_universe") or {})
    if not bool(policy.get("enabled", False)):
        raise ValueError("fact_universe.enabled must be true")
    target_share = float(policy.get("target_greater_china_share", 0.48))
    if not 0 < target_share < 1:
        raise ValueError("target_greater_china_share must be between 0 and 1")
    _ensure_derived_members_schema(db)
    minimum_per_stratum = max(0, int(policy.get("minimum_per_stratum", 1)))
    input_fact_build_id = _required_active_build_id(db, "standardized_facts")
    input_entity_build_id = _required_active_build_id(db, "canonical_entities")
    input_metric_build_id = _required_active_build_id(db, "metrics")
    config_hash = _digest(policy)
    universe_build_id = start_build(
        db,
        layer="fact_validation",
        command="build-fact-universe",
        prefix="fact_universe",
        input_build_id=input_fact_build_id,
        notes=json.dumps(
            {
                "policy_id": policy.get(
                    "policy_id", "regional_stratified_historical_v1"
                ),
                "policy_version": FACT_UNIVERSE_POLICY_VERSION,
                "config_hash": config_hash,
            },
            sort_keys=True,
        ),
    )
    started_at = _now()
    _insert_universe_build(
        db,
        {
            "universe_build_id": universe_build_id,
            "input_fact_build_id": input_fact_build_id,
            "input_entity_build_id": input_entity_build_id,
            "policy_id": str(
                policy.get("policy_id") or "regional_stratified_historical_v1"
            ),
            "policy_version": FACT_UNIVERSE_POLICY_VERSION,
            "config_hash": config_hash,
            "membership_manifest_hash": None,
            "target_greater_china_share": target_share,
            "actual_greater_china_share": None,
            "candidate_fact_count": 0,
            "member_count": 0,
            "greater_china_member_count": 0,
            "international_member_count": 0,
            "unclassified_candidate_count": 0,
            "status": "running",
            "quality_status": None,
            "started_at": started_at,
            "completed_at": None,
            "is_active": False,
            "superseded_by": None,
            "notes": json.dumps(policy, ensure_ascii=False, sort_keys=True),
        },
    )
    try:
        entity_regions, entity_types = _entity_context(db, input_entity_build_id)
        metric_categories = _metric_categories(db, input_metric_build_id)
        source_markets = {
            str(row["source_id"]): row.get("market")
            for row in _rows(db, "SELECT source_id, market FROM source_registry")
        }
        derived_policy = dict(policy.get("derived_chain_priority") or {})
        derived_priority_enabled = bool(derived_policy.get("enabled", False))
        input_derived_build_id: str | None = None
        derived_chains: list[DerivedChain] = []
        derived_input_ids: set[str] = set()
        if derived_priority_enabled:
            input_derived_build_id, derived_chains = _load_derived_chains(
                db,
                input_fact_build_id,
                entity_regions,
            )
            derived_input_ids = {
                fact_id for chain in derived_chains for fact_id in chain.input_fact_ids
            }
        derived_input_regions: dict[str, str] = {}
        query, params = _candidate_query(
            input_fact_build_id,
            include_forecasts=bool(policy.get("include_forecasts", False)),
        )
        candidate_counts: Counter[str] = Counter()
        broad_stratum_counts: Counter[str] = Counter()
        source_candidate_counts: Counter[str] = Counter()
        for row in _stream_rows(db, query, params):
            region = _fact_region(row, entity_regions, source_markets)
            fact_id = str(row["fact_id"])
            if fact_id in derived_input_ids:
                derived_input_regions[fact_id] = region
            candidate_counts[region] += 1
            source_candidate_counts[str(row.get("source_id") or "unknown")] += 1
            if region in BROAD_INTERNATIONAL_REGIONS:
                broad_stratum_counts[
                    _stratum_key(row, metric_categories, entity_types)
                ] += 1

        if derived_priority_enabled:
            derived_chains = [
                DerivedChain(
                    derived_id=chain.derived_id,
                    derived_type=chain.derived_type,
                    region_bucket=_effective_chain_region(
                        chain,
                        derived_input_regions,
                    ),
                    input_fact_ids=chain.input_fact_ids,
                )
                for chain in derived_chains
            ]

        greater_china_count = candidate_counts[GREATER_CHINA]
        broad_count = sum(
            candidate_counts[region] for region in BROAD_INTERNATIONAL_REGIONS
        )
        if greater_china_count <= 0:
            raise RuntimeError(
                "No Greater China graph-ready facts are available for balancing"
            )
        broad_budget = min(
            broad_count,
            math.floor(greater_china_count * (1.0 - target_share) / target_share),
        )
        priority_fact_ids: set[str] = set()
        priority_report: dict[str, Any] = {
            "enabled": derived_priority_enabled,
            "input_derived_build_id": input_derived_build_id,
        }
        if derived_priority_enabled:
            priority_fact_ids, priority_report = select_derived_chain_priority(
                derived_chains,
                derived_input_regions,
                broad_fact_budget=broad_budget,
                target_greater_china_share=target_share,
                target_fraction=float(derived_policy.get("target_fraction", 0.90)),
                evaluation_interval=max(
                    1, int(derived_policy.get("evaluation_interval", 25))
                ),
            )
            priority_report["input_derived_build_id"] = input_derived_build_id
        remaining_stratum_counts: Counter[str] = Counter()
        priority_strata: set[str] = set()
        if priority_fact_ids:
            for row in _stream_rows(db, query, params):
                region = _fact_region(row, entity_regions, source_markets)
                if region not in BROAD_INTERNATIONAL_REGIONS:
                    continue
                stratum_key = _stratum_key(row, metric_categories, entity_types)
                if str(row["fact_id"]) in priority_fact_ids:
                    priority_strata.add(stratum_key)
                else:
                    remaining_stratum_counts[stratum_key] += 1
        else:
            remaining_stratum_counts.update(broad_stratum_counts)
        remaining_budget = broad_budget - len(priority_fact_ids)
        if remaining_budget < 0:
            raise RuntimeError(
                "Derived-chain priority facts exceed broad international budget"
            )
        quotas = allocate_stratum_quotas(
            remaining_stratum_counts,
            remaining_budget,
            minimum_per_stratum=minimum_per_stratum,
        )
        priority_ranks = {
            fact_id: rank
            for rank, fact_id in enumerate(sorted(priority_fact_ids), start=1)
        }

        selected_counts: Counter[str] = Counter()
        selected_source_counts: Counter[str] = Counter()
        stratum_ranks: Counter[str] = Counter()
        selected_strata: set[str] = set()
        selected_fact_ids: set[str] = set()
        manifest = hashlib.sha256()
        batch: list[dict[str, Any]] = []
        for row in _stream_rows(db, query, params):
            fact_id = str(row["fact_id"])
            region = _fact_region(row, entity_regions, source_markets)
            stratum_key = _stratum_key(row, metric_categories, entity_types)
            include = region == GREATER_CHINA
            reason = "all_greater_china"
            rank = 1
            if region in BROAD_INTERNATIONAL_REGIONS:
                if fact_id in priority_fact_ids:
                    include = True
                    rank = priority_ranks[fact_id]
                    reason = "derived_chain_support"
                else:
                    stratum_ranks[stratum_key] += 1
                    rank = stratum_ranks[stratum_key]
                    include = rank <= quotas.get(stratum_key, 0)
                    reason = "stratified_broad_international"
            if not include:
                continue
            selected_counts[region] += 1
            selected_fact_ids.add(fact_id)
            selected_source_counts[str(row.get("source_id") or "unknown")] += 1
            selected_strata.add(stratum_key)
            manifest.update(fact_id.encode("utf-8"))
            manifest.update(b"\n")
            batch.append(
                {
                    "membership_id": _digest([universe_build_id, fact_id]),
                    "universe_build_id": universe_build_id,
                    "fact_id": fact_id,
                    "region_bucket": region,
                    "stratum_key": stratum_key,
                    "selection_rank": rank,
                    "selection_reason": reason,
                }
            )
            if len(batch) >= batch_size:
                _insert_members(db, batch)
                batch.clear()
        if batch:
            _insert_members(db, batch)

        member_count = sum(selected_counts.values())
        selected_greater_china = selected_counts[GREATER_CHINA]
        selected_broad = sum(
            selected_counts[region] for region in BROAD_INTERNATIONAL_REGIONS
        )
        actual_share = selected_greater_china / member_count if member_count else 0.0
        derived_closure = derived_chain_closure_report(
            derived_chains,
            selected_fact_ids,
            input_fact_regions=derived_input_regions,
        )
        selected_derived, derived_membership = select_balanced_derived_members(
            derived_chains,
            selected_fact_ids,
            derived_input_regions,
            target_greater_china_share=target_share,
        )
        derived_ranks: Counter[str] = Counter()
        derived_batch: list[dict[str, Any]] = []
        for chain, region in selected_derived:
            stratum_key = f"{region}|{chain.derived_type}"
            derived_ranks[stratum_key] += 1
            manifest.update(b"derived:")
            manifest.update(chain.derived_id.encode("utf-8"))
            manifest.update(b"\n")
            derived_batch.append(
                {
                    "membership_id": _digest(
                        [universe_build_id, "derived", chain.derived_id]
                    ),
                    "universe_build_id": universe_build_id,
                    "derived_id": chain.derived_id,
                    "region_bucket": region,
                    "stratum_key": stratum_key,
                    "selection_rank": derived_ranks[stratum_key],
                    "selection_reason": (
                        "all_greater_china_derived"
                        if region == GREATER_CHINA
                        else "balanced_broad_derived"
                    ),
                }
            )
            if len(derived_batch) >= batch_size:
                _insert_derived_members(db, derived_batch)
                derived_batch.clear()
        if derived_batch:
            _insert_derived_members(db, derived_batch)
        priority_report["selected_priority_fact_count"] = len(priority_fact_ids)
        priority_report["closure_distribution"] = derived_closure
        priority_report["derived_member_distribution"] = derived_membership[
            "member_distribution"
        ]
        priority_report["derived_member_count"] = derived_membership[
            "member_distribution"
        ]["total"]
        stratum_coverage = (
            len(selected_strata & set(broad_stratum_counts)) / len(broad_stratum_counts)
            if broad_stratum_counts
            else 1.0
        )
        quality_failures = []
        if selected_greater_china != greater_china_count:
            quality_failures.append(
                "not_all_greater_china_facts_selected="
                f"{selected_greater_china}/{greater_china_count}"
            )
        if selected_broad != broad_budget:
            quality_failures.append(
                f"broad_international_budget_mismatch={selected_broad}/{broad_budget}"
            )
        if actual_share + 1e-12 < target_share:
            quality_failures.append(
                f"greater_china_share={actual_share:.6f} < {target_share:.6f}"
            )
        if not priority_fact_ids.issubset(selected_fact_ids):
            quality_failures.append("derived_chain_priority_fact_missing")
        if derived_priority_enabled:
            minimum_derived_share = float(
                derived_policy.get(
                    "minimum_greater_china_share",
                    max(0.0, target_share - 0.05),
                )
            )
            maximum_derived_share = float(
                derived_policy.get(
                    "maximum_greater_china_share",
                    min(1.0, target_share + 0.05),
                )
            )
            priority_report["alignment_band"] = {
                "minimum_greater_china_share": minimum_derived_share,
                "maximum_greater_china_share": maximum_derived_share,
            }
            derived_member_distribution = derived_membership["member_distribution"]
            derived_share = float(
                derived_member_distribution.get("greater_china_share") or 0.0
            )
            if not derived_member_distribution.get("total"):
                quality_failures.append("derived_universe_membership_is_empty")
            elif not minimum_derived_share <= derived_share <= maximum_derived_share:
                quality_failures.append(
                    "derived_greater_china_share="
                    f"{derived_share:.6f} outside "
                    f"[{minimum_derived_share:.6f},{maximum_derived_share:.6f}]"
                )
        minimum_stratum_coverage = float(policy.get("minimum_stratum_coverage", 0.95))
        if stratum_coverage < minimum_stratum_coverage:
            quality_failures.append(
                f"stratum_coverage={stratum_coverage:.6f} < "
                f"{minimum_stratum_coverage:.6f}"
            )
        quality_status = "failed" if quality_failures else "passed"
        completed_at = _now()
        _update_universe_build(
            db,
            universe_build_id,
            {
                "membership_manifest_hash": manifest.hexdigest(),
                "actual_greater_china_share": actual_share,
                "candidate_fact_count": sum(candidate_counts.values()),
                "member_count": member_count,
                "greater_china_member_count": selected_greater_china,
                "international_member_count": selected_broad,
                "unclassified_candidate_count": candidate_counts[UNCLASSIFIED],
                "status": "success" if not quality_failures else "failed",
                "quality_status": quality_status,
                "completed_at": completed_at,
            },
        )
        if not quality_failures:
            _activate_universe(db, universe_build_id)
        finish_build(
            db,
            universe_build_id,
            "success" if not quality_failures else "failed",
            f"members={member_count}; greater_china_share={actual_share:.6f}",
        )
        report = {
            "universe_build_id": universe_build_id,
            "input_fact_build_id": input_fact_build_id,
            "input_entity_build_id": input_entity_build_id,
            "policy_id": str(
                policy.get("policy_id") or "regional_stratified_historical_v1"
            ),
            "policy_version": FACT_UNIVERSE_POLICY_VERSION,
            "config_hash": config_hash,
            "membership_manifest_hash": manifest.hexdigest(),
            "target_greater_china_share": target_share,
            "actual_greater_china_share": actual_share,
            "candidate_distribution": distribution(candidate_counts),
            "member_distribution": distribution(selected_counts),
            "candidate_source_counts": dict(sorted(source_candidate_counts.items())),
            "member_source_counts": dict(sorted(selected_source_counts.items())),
            "broad_international_budget": broad_budget,
            "broad_international_stratum_count": len(broad_stratum_counts),
            "selected_broad_international_stratum_count": len(
                selected_strata & set(broad_stratum_counts)
            ),
            "stratum_coverage": stratum_coverage,
            "derived_chain_priority": priority_report,
            "derived_universe_membership": derived_membership,
            "quality_status": quality_status,
            "quality_failures": quality_failures,
            "is_active": not quality_failures,
            "notes": [
                "All eligible Greater China facts are retained.",
                "Broad international facts are selected deterministically by stratum and fact_id.",
                "When enabled, validated international derived chains reserve supporting facts before the remaining stratified quota is allocated.",
                "Derived facts are selected explicitly and versioned independently from accidental input closure.",
                "The full standardized and derived builds remain unchanged; membership tables define the downstream serving layer.",
            ],
        }
        if output_dir:
            paths = write_fact_universe_report(report, output_dir)
            report["written_files"] = [str(path) for path in paths]
        return report
    except Exception as exc:
        _update_universe_build(
            db,
            universe_build_id,
            {
                "status": "failed",
                "quality_status": "failed",
                "completed_at": _now(),
                "notes": json.dumps(
                    {"error": f"{type(exc).__name__}: {exc}"},
                    sort_keys=True,
                ),
            },
        )
        finish_build(
            db,
            universe_build_id,
            "failed",
            f"{type(exc).__name__}: {exc}",
        )
        raise


def _load_derived_chains(
    db: DBProtocol,
    input_fact_build_id: str,
    entity_regions: Mapping[str, str],
) -> tuple[str, list[DerivedChain]]:
    builds = _rows(
        db,
        "SELECT build_id, COUNT(*) AS row_count FROM derived_facts "
        "WHERE input_build_id = ? AND COALESCE(is_active, 1) = 1 "
        "AND verification_status IN ('single_source', 'cross_verified') "
        "GROUP BY build_id ORDER BY build_id",
        [input_fact_build_id],
    )
    if len(builds) != 1:
        found = [str(row.get("build_id")) for row in builds]
        raise RuntimeError(
            "derived_chain_priority requires exactly one active derived build "
            f"for fact build {input_fact_build_id}; found {found}"
        )
    build_id = str(builds[0]["build_id"])
    chains = []
    for row in _rows(
        db,
        "SELECT derived_id, derived_type, input_fact_ids, entity_scope, "
        "scope_id, scope_entity_ids FROM derived_facts "
        "WHERE build_id = ? AND input_build_id = ? "
        "AND COALESCE(is_active, 1) = 1 "
        "AND verification_status IN ('single_source', 'cross_verified') "
        "ORDER BY derived_id",
        [build_id, input_fact_build_id],
    ):
        input_fact_ids = frozenset(
            str(value) for value in _json_list(row.get("input_fact_ids")) if value
        )
        if not input_fact_ids:
            continue
        entity_scope = _json_dict(row.get("entity_scope"))
        entity_ids = {
            str(value) for value in _json_list(row.get("scope_entity_ids")) if value
        }
        if entity_scope.get("entity_id"):
            entity_ids.add(str(entity_scope["entity_id"]))
        entity_ids.update(
            str(value) for value in entity_scope.get("entity_ids", []) if value
        )
        scope_id = str(row.get("scope_id") or "")
        if not entity_ids and scope_id in entity_regions:
            entity_ids.add(scope_id)
        chains.append(
            DerivedChain(
                derived_id=str(row["derived_id"]),
                derived_type=str(row.get("derived_type") or "unknown"),
                region_bucket=classify_entity_scope(entity_ids, entity_regions),
                input_fact_ids=input_fact_ids,
            )
        )
    return build_id, chains


def select_derived_chain_priority(
    chains: Iterable[DerivedChain],
    input_fact_regions: Mapping[str, str],
    *,
    broad_fact_budget: int,
    target_greater_china_share: float,
    target_fraction: float = 0.90,
    evaluation_interval: int = 25,
) -> tuple[set[str], dict[str, Any]]:
    if not 0 < target_fraction <= 1:
        raise ValueError("derived_chain_priority.target_fraction must be in (0, 1]")
    eligible: list[DerivedChain] = []
    for chain in chains:
        regions = {
            input_fact_regions.get(fact_id, UNCLASSIFIED)
            for fact_id in chain.input_fact_ids
        }
        if chain.region_bucket == GREATER_CHINA and regions == {GREATER_CHINA}:
            eligible.append(chain)
        elif (
            chain.region_bucket in BROAD_INTERNATIONAL_REGIONS
            and regions
            and regions.issubset(BROAD_INTERNATIONAL_REGIONS)
        ):
            eligible.append(chain)
    eligible_counts = Counter(chain.region_bucket for chain in eligible)
    greater_china_count = eligible_counts[GREATER_CHINA]
    if greater_china_count <= 0:
        raise RuntimeError(
            "No Greater China derived chains are eligible for regional balancing"
        )
    broad_chains = sorted(
        (
            chain
            for chain in eligible
            if chain.region_bucket in BROAD_INTERNATIONAL_REGIONS
        ),
        key=lambda chain: (
            len(chain.input_fact_ids),
            chain.derived_type,
            chain.derived_id,
        ),
    )
    broad_target = min(
        len(broad_chains),
        math.floor(
            greater_china_count
            * (1.0 - target_greater_china_share)
            / target_greater_china_share
        ),
    )
    priority_closure_target = math.floor(broad_target * target_fraction)
    selected_fact_ids: set[str] = set()
    seed_chains: list[DerivedChain] = []
    closed_broad_count = 0
    interval = max(1, evaluation_interval)
    for chain in broad_chains:
        additional = chain.input_fact_ids - selected_fact_ids
        if len(selected_fact_ids) + len(additional) > broad_fact_budget:
            continue
        selected_fact_ids.update(additional)
        seed_chains.append(chain)
        if len(seed_chains) % interval == 0 or len(seed_chains) == len(broad_chains):
            closed_broad_count = sum(
                candidate.input_fact_ids.issubset(selected_fact_ids)
                for candidate in broad_chains
            )
            if closed_broad_count >= priority_closure_target:
                break
    closed_broad_count = sum(
        chain.input_fact_ids.issubset(selected_fact_ids) for chain in broad_chains
    )
    report = {
        "enabled": True,
        "target_fraction": target_fraction,
        "eligible_derived_distribution": distribution(eligible_counts),
        "target_broad_derived_count": broad_target,
        "priority_closure_target": priority_closure_target,
        "seed_derived_count": len(seed_chains),
        "seed_derived_type_counts": dict(
            sorted(Counter(chain.derived_type for chain in seed_chains).items())
        ),
        "priority_fact_count": len(selected_fact_ids),
        "priority_closed_broad_derived_count": closed_broad_count,
    }
    return selected_fact_ids, report


def derived_chain_closure_report(
    chains: Iterable[DerivedChain],
    selected_fact_ids: set[str],
    *,
    input_fact_regions: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    closed = [
        chain for chain in chains if chain.input_fact_ids.issubset(selected_fact_ids)
    ]
    effective = [
        (chain, _effective_chain_region(chain, input_fact_regions or {}))
        for chain in closed
    ]
    counts = Counter(region for _, region in effective)
    report = distribution(counts)
    grouped: dict[str, Counter[str]] = defaultdict(Counter)
    for chain, region in effective:
        grouped[chain.derived_type][region] += 1
    report["by_derived_type"] = {
        derived_type: distribution(values)
        for derived_type, values in sorted(grouped.items())
    }
    return report


def select_balanced_derived_members(
    chains: Iterable[DerivedChain],
    selected_fact_ids: set[str],
    input_fact_regions: Mapping[str, str],
    *,
    target_greater_china_share: float,
) -> tuple[list[tuple[DerivedChain, str]], dict[str, Any]]:
    closed = [
        (chain, _effective_chain_region(chain, input_fact_regions))
        for chain in chains
        if chain.input_fact_ids.issubset(selected_fact_ids)
    ]
    classified = [item for item in closed if item[1] != UNCLASSIFIED]
    greater_china = sorted(
        (item for item in classified if item[1] == GREATER_CHINA),
        key=lambda item: (item[0].derived_type, item[0].derived_id),
    )
    broad = [item for item in classified if item[1] in BROAD_INTERNATIONAL_REGIONS]
    broad_target = min(
        len(broad),
        math.floor(
            len(greater_china)
            * (1.0 - target_greater_china_share)
            / target_greater_china_share
        ),
    )
    grouped: dict[str, list[tuple[DerivedChain, str]]] = defaultdict(list)
    for item in broad:
        grouped[item[0].derived_type].append(item)
    for values in grouped.values():
        values.sort(key=lambda item: (item[1], item[0].derived_id))
    selected_broad: list[tuple[DerivedChain, str]] = []
    offsets = {key: 0 for key in grouped}
    while len(selected_broad) < broad_target:
        progressed = False
        for key in sorted(grouped):
            offset = offsets[key]
            values = grouped[key]
            if offset >= len(values):
                continue
            selected_broad.append(values[offset])
            offsets[key] += 1
            progressed = True
            if len(selected_broad) >= broad_target:
                break
        if not progressed:
            break
    selected = sorted(
        [*greater_china, *selected_broad],
        key=lambda item: (item[1], item[0].derived_type, item[0].derived_id),
    )
    candidate_counts = Counter(region for _, region in classified)
    member_counts = Counter(region for _, region in selected)
    return selected, {
        "selection_policy": "all_greater_china_plus_stratified_broad_v1",
        "candidate_distribution": distribution(candidate_counts),
        "member_distribution": distribution(member_counts),
        "broad_target": broad_target,
        "unclassified_closed_count": sum(
            region == UNCLASSIFIED for _, region in closed
        ),
        "derived_type_counts": dict(
            sorted(Counter(chain.derived_type for chain, _ in selected).items())
        ),
    }


def _effective_chain_region(
    chain: DerivedChain,
    input_fact_regions: Mapping[str, str],
) -> str:
    if chain.region_bucket != UNCLASSIFIED:
        return chain.region_bucket
    regions = {
        input_fact_regions.get(fact_id, UNCLASSIFIED)
        for fact_id in chain.input_fact_ids
    }
    if regions == {GREATER_CHINA}:
        return GREATER_CHINA
    if regions and regions.issubset(BROAD_INTERNATIONAL_REGIONS):
        return MIXED_GLOBAL if MIXED_GLOBAL in regions else INTERNATIONAL
    if regions and UNCLASSIFIED not in regions:
        return MIXED_GLOBAL
    return UNCLASSIFIED


def _group_derived_types(
    chains: Iterable[DerivedChain],
) -> dict[str, Counter[str]]:
    grouped: dict[str, Counter[str]] = defaultdict(Counter)
    for chain in chains:
        grouped[chain.derived_type][chain.region_bucket] += 1
    return grouped


def _json_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if value in (None, ""):
        return None
    try:
        return json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def _json_list(value: Any) -> list[Any]:
    parsed = _json_value(value)
    return parsed if isinstance(parsed, list) else []


def _json_dict(value: Any) -> dict[str, Any]:
    parsed = _json_value(value)
    return parsed if isinstance(parsed, dict) else {}


def allocate_stratum_quotas(
    counts: Mapping[str, int],
    budget: int,
    *,
    minimum_per_stratum: int = 1,
) -> dict[str, int]:
    positive = {key: int(value) for key, value in counts.items() if int(value) > 0}
    if budget <= 0 or not positive:
        return {key: 0 for key in positive}
    budget = min(int(budget), sum(positive.values()))
    quotas = {key: 0 for key in positive}
    if minimum_per_stratum > 0:
        minimum_total = sum(
            min(minimum_per_stratum, value) for value in positive.values()
        )
        if minimum_total <= budget:
            quotas = {
                key: min(minimum_per_stratum, value) for key, value in positive.items()
            }
        else:
            for key in sorted(
                positive,
                key=lambda item: (-positive[item], item),
            )[:budget]:
                quotas[key] = 1
            return quotas
    remaining = budget - sum(quotas.values())
    residual = {key: positive[key] - quotas[key] for key in positive}
    residual_total = sum(residual.values())
    if remaining <= 0 or residual_total <= 0:
        return quotas
    fractions: list[tuple[float, str]] = []
    for key in sorted(positive):
        exact = remaining * residual[key] / residual_total
        addition = min(residual[key], math.floor(exact))
        quotas[key] += addition
        fractions.append((exact - addition, key))
    leftover = budget - sum(quotas.values())
    for _, key in sorted(fractions, key=lambda item: (-item[0], item[1])):
        if leftover <= 0:
            break
        if quotas[key] >= positive[key]:
            continue
        quotas[key] += 1
        leftover -= 1
    return quotas


def active_fact_universe_build_id(
    db: DBProtocol,
    *,
    input_fact_build_id: str | None = None,
) -> str | None:
    active_predicate = (
        "is_active IS TRUE"
        if db.__class__.__name__ == "PostgresMetadataDB"
        else "is_active = 1"
    )
    predicates = [
        active_predicate,
        "status = 'success'",
        "quality_status = 'passed'",
    ]
    params: list[Any] = []
    if input_fact_build_id:
        predicates.append("input_fact_build_id = ?")
        params.append(input_fact_build_id)
    row = db.fetchone(
        "SELECT universe_build_id FROM fact_universe_builds WHERE "
        + " AND ".join(predicates)
        + " ORDER BY completed_at DESC LIMIT 1",
        params,
    )
    return str(row["universe_build_id"]) if row else None


def write_fact_universe_report(report: dict[str, Any], output_dir: str) -> list[Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    json_path = output / "fact_universe_report.json"
    markdown_path = output / "fact_universe_report.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(_markdown(report), encoding="utf-8")
    return [json_path, markdown_path]


def _candidate_query(
    fact_build_id: str, *, include_forecasts: bool
) -> tuple[str, list[Any]]:
    sql = (
        "SELECT fact_id, entity_id, metric_id, source_id, frequency, "
        "fiscal_year, calendar_year, period_end FROM standardized_facts "
        "WHERE build_id = ? AND COALESCE(is_active, 1) = 1 "
        "AND COALESCE(graph_ready, 0) = 1 "
        "AND verification_status IN ('single_source', 'cross_verified') "
    )
    if not include_forecasts:
        sql += "AND COALESCE(is_forecast, 0) = 0 "
    return sql + "ORDER BY fact_id", [fact_build_id]


def _entity_context(
    db: DBProtocol, build_id: str
) -> tuple[dict[str, str], dict[str, str]]:
    aliases: dict[str, set[str]] = defaultdict(set)
    for row in _rows(
        db,
        "SELECT entity_id, source_id FROM entity_alias_map WHERE build_id = ?",
        [build_id],
    ):
        aliases[str(row["entity_id"])].add(str(row["source_id"]))
    regions = {}
    entity_types = {}
    for row in _rows(
        db,
        "SELECT * FROM canonical_entities WHERE build_id = ?",
        [build_id],
    ):
        entity_id = str(row["entity_id"])
        regions[entity_id] = classify_entity(row, aliases.get(entity_id, set()))
        entity_types[entity_id] = str(row.get("entity_type") or "unknown")
    return regions, entity_types


def _metric_categories(db: DBProtocol, build_id: str) -> dict[str, str]:
    return {
        str(row["metric_id"]): str(row.get("metric_category") or "unknown")
        for row in _rows(
            db,
            "SELECT metric_id, metric_category FROM metrics WHERE build_id = ?",
            [build_id],
        )
    }


def _fact_region(
    row: Mapping[str, Any],
    entity_regions: Mapping[str, str],
    source_markets: Mapping[str, Any],
) -> str:
    entity_id = str(row.get("entity_id") or "")
    region = entity_regions.get(entity_id, UNCLASSIFIED)
    if region != UNCLASSIFIED:
        return region
    source_id = str(row.get("source_id") or "")
    return classify_source(source_id, source_markets.get(source_id))


def _stratum_key(
    row: Mapping[str, Any],
    metric_categories: Mapping[str, str],
    entity_types: Mapping[str, str],
) -> str:
    entity_id = str(row.get("entity_id") or "")
    metric_id = str(row.get("metric_id") or "")
    year = _year(row)
    payload = {
        "source_id": str(row.get("source_id") or "unknown"),
        "metric_category": metric_categories.get(metric_id, "unknown"),
        "entity_type": entity_types.get(entity_id, "unknown"),
        "frequency": str(row.get("frequency") or "unknown"),
        "year_bucket": f"{(year // 10) * 10}s" if year else "unknown",
    }
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _year(row: Mapping[str, Any]) -> int | None:
    for value in (
        row.get("fiscal_year"),
        row.get("calendar_year"),
        row.get("period_end"),
    ):
        text = str(value or "")
        if len(text) >= 4 and text[:4].isdigit():
            return int(text[:4])
    return None


def _required_active_build_id(db: DBProtocol, table: str) -> str:
    rows = _rows(
        db,
        f"SELECT build_id, COUNT(*) AS row_count FROM {table} "
        "WHERE COALESCE(is_active, 1) = 1 AND build_id IS NOT NULL "
        "GROUP BY build_id ORDER BY build_id",
    )
    if len(rows) != 1:
        found = [str(row.get("build_id")) for row in rows]
        raise RuntimeError(f"{table} must have exactly one active build; found {found}")
    return str(rows[0]["build_id"])


def _stream_rows(
    db: DBProtocol,
    sql: str,
    params: Iterable[Any] = (),
    *,
    fetch_size: int = 10_000,
) -> Iterator[dict[str, Any]]:
    connection = db.conn  # type: ignore[attr-defined]
    cursor = connection.cursor()
    try:
        statement = db._sql(sql) if hasattr(db, "_sql") else sql  # type: ignore[attr-defined]
        cursor.execute(statement, tuple(params))
        while True:
            rows = cursor.fetchmany(fetch_size)
            if not rows:
                break
            for row in rows:
                yield dict(row)
    finally:
        cursor.close()


def _rows(db: DBProtocol, sql: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in db.fetchall(sql, params)]


def _insert_universe_build(db: DBProtocol, row: dict[str, Any]) -> None:
    columns = list(row)
    _insert_many(db, "fact_universe_builds", columns, [row])


def _insert_members(db: DBProtocol, rows: list[dict[str, Any]]) -> None:
    _insert_many(db, "fact_universe_members", MEMBER_COLUMNS, rows)


def _insert_derived_members(db: DBProtocol, rows: list[dict[str, Any]]) -> None:
    _insert_many(
        db,
        "fact_universe_derived_members",
        DERIVED_MEMBER_COLUMNS,
        rows,
    )


def _ensure_derived_members_schema(db: DBProtocol) -> None:
    timestamp_type = (
        "TIMESTAMPTZ" if db.__class__.__name__ == "PostgresMetadataDB" else "TEXT"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS fact_universe_derived_members ("
        "membership_id TEXT PRIMARY KEY, "
        "universe_build_id TEXT NOT NULL REFERENCES fact_universe_builds(universe_build_id), "
        "derived_id TEXT NOT NULL REFERENCES derived_facts(derived_id), "
        "region_bucket TEXT NOT NULL, stratum_key TEXT NOT NULL, "
        "selection_rank INTEGER NOT NULL, selection_reason TEXT NOT NULL, "
        f"created_at {timestamp_type} DEFAULT CURRENT_TIMESTAMP)"
    )
    db.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_fact_universe_derived_unique "
        "ON fact_universe_derived_members(universe_build_id, derived_id)"
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_fact_universe_derived_id "
        "ON fact_universe_derived_members(derived_id, universe_build_id)"
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_fact_universe_derived_region "
        "ON fact_universe_derived_members(universe_build_id, region_bucket)"
    )


def _insert_many(
    db: DBProtocol,
    table: str,
    columns: list[str],
    rows: list[dict[str, Any]],
) -> None:
    if not rows:
        return
    values = [[row.get(column) for column in columns] for row in rows]
    primary_key = columns[0]
    if db.__class__.__name__ == "PostgresMetadataDB":
        placeholders = ",".join(["%s"] * len(columns))
        updates = ", ".join(
            f"{column}=EXCLUDED.{column}" for column in columns if column != primary_key
        )
        sql = (
            f"INSERT INTO {table} ({','.join(columns)}) "
            f"VALUES ({placeholders}) ON CONFLICT ({primary_key}) "
            f"DO UPDATE SET {updates}"
        )
        with db.conn.cursor() as cursor:  # type: ignore[attr-defined]
            cursor.executemany(sql, values)
        db.conn.commit()  # type: ignore[attr-defined]
    else:
        placeholders = ",".join(["?"] * len(columns))
        db.conn.executemany(  # type: ignore[attr-defined]
            f"INSERT OR REPLACE INTO {table} ({','.join(columns)}) "
            f"VALUES ({placeholders})",
            values,
        )
        db.conn.commit()  # type: ignore[attr-defined]


def _update_universe_build(
    db: DBProtocol, universe_build_id: str, fields: dict[str, Any]
) -> None:
    assignments = ", ".join(f"{key} = ?" for key in fields)
    db.execute(
        f"UPDATE fact_universe_builds SET {assignments} WHERE universe_build_id = ?",
        [*fields.values(), universe_build_id],
    )


def _activate_universe(db: DBProtocol, universe_build_id: str) -> None:
    inactive_value: bool | int = (
        False if db.__class__.__name__ == "PostgresMetadataDB" else 0
    )
    active_value: bool | int = (
        True if db.__class__.__name__ == "PostgresMetadataDB" else 1
    )
    active_predicate = (
        "is_active IS TRUE"
        if db.__class__.__name__ == "PostgresMetadataDB"
        else "is_active = 1"
    )
    db.execute(
        "UPDATE fact_universe_builds SET is_active = ?, superseded_by = ? "
        f"WHERE {active_predicate} AND universe_build_id <> ?",
        [inactive_value, universe_build_id, universe_build_id],
    )
    db.execute(
        "UPDATE fact_universe_builds SET is_active = ?, superseded_by = NULL "
        "WHERE universe_build_id = ?",
        [active_value, universe_build_id],
    )


def _digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _markdown(report: Mapping[str, Any]) -> str:
    candidates = report["candidate_distribution"]
    members = report["member_distribution"]
    derived_priority = dict(report.get("derived_chain_priority") or {})
    derived_closure = dict(derived_priority.get("closure_distribution") or {})
    lines = [
        "# Fact Universe Report",
        "",
        f"- universe_build_id: `{report['universe_build_id']}`",
        f"- input_fact_build_id: `{report['input_fact_build_id']}`",
        f"- quality_status: {report['quality_status']}",
        f"- target Greater China share: {report['target_greater_china_share']:.2%}",
        f"- actual Greater China share: {report['actual_greater_china_share']:.2%}",
        f"- candidate facts: {candidates['total']:,}",
        f"- selected facts: {members['total']:,}",
        f"- broad-international stratum coverage: {report['stratum_coverage']:.2%}",
        "",
        "## Regional Membership",
        "",
        "| region | candidates | members |",
        "| --- | ---: | ---: |",
    ]
    for region in (GREATER_CHINA, INTERNATIONAL, MIXED_GLOBAL, UNCLASSIFIED):
        lines.append(
            f"| {region} | {candidates['bucket_counts'][region]:,} | "
            f"{members['bucket_counts'][region]:,} |"
        )
    if derived_priority.get("enabled"):
        lines.extend(
            [
                "",
                "## Derived Chain Closure",
                "",
                f"- input_derived_build_id: {derived_priority.get('input_derived_build_id')}",
                f"- selected priority facts: {derived_priority.get('selected_priority_fact_count', 0):,}",
                f"- closed derived facts: {derived_closure.get('total', 0):,}",
                "- closed DerivedFact Greater China share: "
                f"{float(derived_closure.get('greater_china_share') or 0.0):.2%}",
            ]
        )
        alignment = dict(derived_priority.get("alignment_band") or {})
        if alignment:
            lines.append(
                "- required closure alignment band: "
                f"{float(alignment['minimum_greater_china_share']):.2%}-"
                f"{float(alignment['maximum_greater_china_share']):.2%}"
            )
    lines.extend(["", "## Quality Failures", ""])
    lines.extend(
        [f"- {failure}" for failure in report["quality_failures"]] or ["- none"]
    )
    lines.append("")
    return "\n".join(lines)
