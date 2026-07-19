from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from typing import Any

from finraw.db.client import DBProtocol
from finraw.qa.store import json_value

ANALYSIS_SPLIT_VERSION = "1.2.0"


class _DisjointSet:
    def __init__(self, values: list[str]):
        self.parent = {value: value for value in values}

    def find(self, value: str) -> str:
        parent = self.parent[value]
        if parent != value:
            self.parent[value] = self.find(parent)
        return self.parent[value]

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def split_analysis_samples(
    db: DBProtocol,
    analysis_build_id: str,
    policy: dict[str, Any],
) -> dict[str, Any]:
    rows = [
        dict(row)
        for row in db.fetchall(
            """
            SELECT s.analysis_sample_id, s.analysis_semantic_cluster_id,
                   s.signal_composition_id, c.analysis_pattern_id,
                   c.entity_ids, c.period_scope, c.difficulty_features,
                   c.scope_definition
            FROM analysis_samples s
            JOIN analysis_candidates c ON c.candidate_id = s.candidate_id
            WHERE s.analysis_build_id = ? AND s.validation_status = 'passed'
            ORDER BY s.analysis_sample_id
            """,
            (analysis_build_id,),
        )
    ]
    if not rows:
        return {
            "version": ANALYSIS_SPLIT_VERSION,
            "split_counts": {},
            "component_count": 0,
            "leakage_audit": _empty_audit(),
        }

    sample_ids = [str(row["analysis_sample_id"]) for row in rows]
    dsu = _DisjointSet(sample_ids)
    entity_to_samples: dict[str, list[str]] = defaultdict(list)
    bundle_keys: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        sample_id = str(row["analysis_sample_id"])
        entities = sorted(str(value) for value in json_value(row["entity_ids"], []))
        for entity_id in entities:
            entity_to_samples[entity_id].append(sample_id)
        scope_key = _scope_key(row, entities)
        bundle_keys[scope_key].append(sample_id)

    for sample_group in [*entity_to_samples.values(), *bundle_keys.values()]:
        first = sample_group[0]
        for sample_id in sample_group[1:]:
            dsu.union(first, sample_id)

    components: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        components[dsu.find(str(row["analysis_sample_id"]))].append(row)

    split_counts: Counter[str] = Counter()
    assignments: dict[str, str] = {}
    component_summary = []
    redirected_components = 0
    for component_rows in components.values():
        preferred_split = _component_split(component_rows, policy)
        split, redirect_reason = _capacity_aware_split(
            preferred_split,
            component_size=len(component_rows),
            total_sample_count=len(rows),
            policy=policy,
        )
        if redirect_reason:
            redirected_components += 1
        entities = sorted(
            {
                str(entity_id)
                for row in component_rows
                for entity_id in json_value(row["entity_ids"], [])
            }
        )
        periods = sorted(
            {
                int(year)
                for row in component_rows
                for year in json_value(row["period_scope"], {}).get("years", [])
            }
        )
        compositions = sorted(
            {str(row["signal_composition_id"]) for row in component_rows}
        )
        for row in component_rows:
            sample_id = str(row["analysis_sample_id"])
            assignments[sample_id] = split
            db.execute(
                "UPDATE analysis_samples SET split = ? WHERE analysis_sample_id = ?",
                (split, sample_id),
            )
            split_counts[split] += 1
        component_summary.append(
            {
                "component_hash": _digest([entities, periods, compositions])[:16],
                "sample_count": len(component_rows),
                "entity_count": len(entities),
                "periods": periods,
                "signal_compositions": compositions,
                "preferred_split": preferred_split,
                "split": split,
                "redirect_reason": redirect_reason,
            }
        )

    audit = _leakage_audit(rows, assignments)
    return {
        "version": ANALYSIS_SPLIT_VERSION,
        "strategy": str(policy.get("strategy") or "entity_scope_component_holdout_v1"),
        "split_counts": dict(sorted(split_counts.items())),
        "component_count": len(components),
        "redirected_component_count": redirected_components,
        "component_summary": sorted(
            component_summary, key=lambda item: item["component_hash"]
        ),
        "leakage_audit": audit,
    }


def _capacity_aware_split(
    preferred_split: str,
    *,
    component_size: int,
    total_sample_count: int,
    policy: dict[str, Any],
) -> tuple[str, str | None]:
    """Keep connected components intact without letting one dominate evaluation."""
    minimum_samples = max(1, int(policy.get("capacity_control_min_samples", 50)))
    maximum_pct = max(
        0.0,
        min(100.0, float(policy.get("maximum_holdout_component_pct", 20.0))),
    )
    if (
        not preferred_split.startswith("test_")
        or total_sample_count < minimum_samples
        or maximum_pct >= 100.0
    ):
        return preferred_split, None

    component_pct = component_size * 100.0 / max(total_sample_count, 1)
    if component_pct <= maximum_pct:
        return preferred_split, None
    return (
        "train",
        "holdout_component_exceeds_capacity:"
        f"{component_size}/{total_sample_count}={component_pct:.4f}%>"
        f"{maximum_pct:.4f}%",
    )


def _component_split(rows: list[dict[str, Any]], policy: dict[str, Any]) -> str:
    entities = sorted(
        {
            str(entity_id)
            for row in rows
            for entity_id in json_value(row["entity_ids"], [])
        }
    )
    periods = sorted(
        {
            int(year)
            for row in rows
            for year in json_value(row["period_scope"], {}).get("years", [])
        }
    )
    compositions = sorted({str(row["signal_composition_id"]) for row in rows})
    patterns = sorted({str(row["analysis_pattern_id"]) for row in rows})
    scopes = sorted({str(row.get("scope_definition") or "") for row in rows})
    conflict = any(
        int(
            json_value(row.get("difficulty_features"), {}).get("counter_claim_count")
            or 0
        )
        > 0
        for row in rows
    )
    component_key = [entities, periods, compositions, patterns, scopes]

    if "peer_positioning_v1" in patterns and _bucket(["peer", scopes]) < _pct(
        policy, "peer_scope_holdout_pct", 10
    ):
        return "test_peer_scope_holdout"
    if conflict and _bucket(["conflict", component_key]) < _pct(
        policy, "conflicting_evidence_holdout_pct", 10
    ):
        return "test_conflicting_evidence"
    if any(
        _bucket(["composition", value])
        < _pct(policy, "signal_composition_holdout_pct", 10)
        for value in compositions
    ):
        return "test_signal_composition_holdout"
    # Include the disjoint component identity so a dominant common window (for
    # example 2023-2025) cannot move every entity using that window into test.
    if periods and _bucket(["periods", periods, entities, scopes]) < _pct(
        policy, "temporal_holdout_pct", 10
    ):
        return "test_temporal_holdout"
    if _bucket(["entities", entities]) < _pct(policy, "entity_holdout_pct", 10):
        return "test_entity_holdout"

    bucket = _bucket(["standard", component_key])
    train = _pct(policy, "train_pct", 70)
    dev = _pct(policy, "dev_pct", 10)
    return (
        "train"
        if bucket < train
        else "dev"
        if bucket < train + dev
        else "test_standard"
    )


def _scope_key(row: dict[str, Any], entities: list[str]) -> str:
    if str(row["analysis_pattern_id"]) == "peer_positioning_v1":
        return "peer:" + _digest([row.get("scope_definition"), entities])
    return "entity:" + _digest(entities)


def _leakage_audit(
    rows: list[dict[str, Any]], assignments: dict[str, str]
) -> dict[str, Any]:
    dimensions: dict[str, dict[str, set[str]]] = {
        "entity": defaultdict(set),
        "peer_scope": defaultdict(set),
        "evidence_window": defaultdict(set),
        "semantic_cluster": defaultdict(set),
    }
    for row in rows:
        sample_id = str(row["analysis_sample_id"])
        split = assignments[sample_id]
        entities = sorted(str(value) for value in json_value(row["entity_ids"], []))
        periods = sorted(
            int(value) for value in json_value(row["period_scope"], {}).get("years", [])
        )
        for entity_id in entities:
            dimensions["entity"][entity_id].add(split)
        if str(row["analysis_pattern_id"]) == "peer_positioning_v1":
            dimensions["peer_scope"][
                _digest([row.get("scope_definition"), entities])
            ].add(split)
        dimensions["evidence_window"][_digest([entities, periods])].add(split)
        dimensions["semantic_cluster"][str(row["analysis_semantic_cluster_id"])].add(
            split
        )
    violations = {
        name: sorted(key for key, splits in values.items() if len(splits) > 1)
        for name, values in dimensions.items()
    }
    return {
        "entity_cross_split_count": len(violations["entity"]),
        "peer_scope_cross_split_count": len(violations["peer_scope"]),
        "evidence_window_cross_split_count": len(violations["evidence_window"]),
        "semantic_cluster_cross_split_count": len(violations["semantic_cluster"]),
        "passed": not any(violations.values()),
        "violations": violations,
    }


def _empty_audit() -> dict[str, Any]:
    return {
        "entity_cross_split_count": 0,
        "peer_scope_cross_split_count": 0,
        "evidence_window_cross_split_count": 0,
        "semantic_cluster_cross_split_count": 0,
        "passed": True,
        "violations": {},
    }


def _pct(policy: dict[str, Any], key: str, default: int) -> int:
    return max(0, min(100, int(policy.get(key, default))))


def _bucket(value: Any) -> int:
    return int(_digest(value)[:8], 16) % 100


def _digest(value: Any) -> str:
    import json

    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode()
    ).hexdigest()
