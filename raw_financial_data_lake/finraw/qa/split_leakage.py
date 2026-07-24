from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from typing import Any, Iterable

from finraw.qa.store import json_value


SPLIT_LEAKAGE_POLICY_VERSION = "1.0.0"
TRAIN_SPLITS = frozenset({"train", "train_complex"})


def leakage_policy(policy: dict[str, Any]) -> dict[str, Any]:
    configured = dict(policy.get("split_leakage") or {})
    return {
        "policy_version": SPLIT_LEAKAGE_POLICY_VERSION,
        "entity_isolation": str(
            configured.get("entity_isolation", "entity_component")
        ),
        "temporal_isolation": str(
            configured.get(
                "temporal_isolation", "entity_metric_series_component"
            )
        ),
        "enforce_semantic_cluster_disjoint": bool(
            configured.get("enforce_semantic_cluster_disjoint", True)
        ),
        "enforce_entity_holdout_disjoint": bool(
            configured.get("enforce_entity_holdout_disjoint", True)
        ),
        "enforce_temporal_exact_disjoint": bool(
            configured.get("enforce_temporal_exact_disjoint", True)
        ),
        "enforce_temporal_series_disjoint": bool(
            configured.get("enforce_temporal_series_disjoint", True)
        ),
        "enforce_source_document_disjoint": bool(
            configured.get("enforce_source_document_disjoint", True)
        ),
        # Reusing a task grammar or surface skeleton may be intentional. Keep both
        # visible, but only turn them into holdouts when a benchmark requires it.
        "enforce_complex_pattern_disjoint": bool(
            configured.get("enforce_complex_pattern_disjoint", False)
        ),
        "enforce_question_skeleton_disjoint": bool(
            configured.get("enforce_question_skeleton_disjoint", False)
        ),
        "maximum_reported_examples": max(
            int(configured.get("maximum_reported_examples", 50)), 1
        ),
    }


def cluster_id(row: dict[str, Any]) -> str:
    return str(row.get("semantic_cluster_id") or row.get("qa_group_id") or "")


def entity_ids(row: dict[str, Any]) -> set[str]:
    return {
        str(value)
        for value in json_value(row.get("entity_ids"), [])
        if str(value).strip()
    }


def metric_ids(row: dict[str, Any]) -> set[str]:
    return {
        str(value)
        for value in json_value(row.get("metric_ids"), [])
        if str(value).strip()
    }


def source_document_ids(row: dict[str, Any]) -> set[str]:
    return {
        str(value)
        for value in json_value(row.get("source_document_ids"), [])
        if str(value).strip()
    }


def entity_is_holdout(entity_id: str) -> bool:
    return (
        int(hashlib.sha1(entity_id.encode("utf-8")).hexdigest()[:8], 16) % 20
        == 0
    )


def latest_year(time_scope: Any) -> int | None:
    scope = json_value(time_scope, {})
    years: list[int] = []
    for key, value in scope.items():
        if "year" in str(key).lower() and value not in (None, ""):
            try:
                years.append(int(value))
            except (TypeError, ValueError):
                pass
    for key in ("period_start", "period_end", "as_of_date", "report_date"):
        value = scope.get(key)
        if value:
            match = re.match(r"(\d{4})", str(value))
            if match:
                years.append(int(match.group(1)))
    return max(years) if years else None


def period_identity(row: dict[str, Any]) -> str:
    scope = json_value(row.get("time_scope"), {})
    temporal_tokens = (
        "year",
        "quarter",
        "month",
        "date",
        "period",
        "start",
        "end",
        "as_of",
        "time",
        "basis",
        "frequency",
        "fiscal",
        "calendar",
        "window",
        "observation",
    )
    temporal_scope = {
        str(key): value
        for key, value in scope.items()
        if any(token in str(key).lower() for token in temporal_tokens)
    }
    normalized = json.dumps(
        temporal_scope or scope,
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
    )
    return _digest(normalized)


def entity_metric_period_keys(row: dict[str, Any]) -> set[str]:
    period = period_identity(row)
    return {
        _digest(f"{entity}|{metric}|{period}")
        for entity in entity_ids(row)
        for metric in metric_ids(row)
    }


def entity_metric_series_keys(row: dict[str, Any]) -> set[str]:
    scope = json_value(row.get("time_scope"), {})
    semantics = json_value(row.get("canonical_semantics"), {})
    basis = str(scope.get("basis") or scope.get("time_basis") or "")
    frequency = str(scope.get("frequency") or semantics.get("frequency") or "")
    scope_type = str(
        scope.get("financial_scope_type")
        or semantics.get("financial_scope_type")
        or ""
    )
    return {
        _digest(f"{entity}|{metric}|{basis}|{frequency}|{scope_type}")
        for entity in entity_ids(row)
        for metric in metric_ids(row)
    }


def pattern_identity(row: dict[str, Any]) -> str:
    for key in (
        "proposal_semantic_id",
        "catalog_pattern_id",
        "pattern_id",
        "graph_pattern_id",
    ):
        value = row.get(key)
        if value:
            return str(value)
    return f"task:{row.get('task_subtype') or 'unknown'}"


def canonical_question_skeleton(row: dict[str, Any]) -> str:
    metadata = json_value(row.get("source_metadata"), {})
    generation = metadata.get("question_generation") or {}
    protected = generation.get("protected_question")
    if protected:
        return _normalize_skeleton(str(protected))
    template_id = row.get("template_id")
    if template_id:
        return f"template:{template_id}"
    question = str(row.get("canonical_question") or row.get("question") or "")
    semantics = json_value(row.get("canonical_semantics"), {})
    replace_values: list[str] = []
    for key, value in semantics.items():
        if not any(token in str(key).lower() for token in ("name", "label", "period")):
            continue
        if isinstance(value, (str, int, float)) and str(value).strip():
            replace_values.append(str(value))
    for value in sorted(replace_values, key=len, reverse=True):
        question = re.sub(re.escape(value), "<slot>", question, flags=re.IGNORECASE)
    question = re.sub(r"(?<![A-Za-z])[-+]?\d+(?:\.\d+)?%?", "<number>", question)
    return _normalize_skeleton(question)


class _DisjointSet:
    def __init__(self, values: Iterable[str]) -> None:
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


def strict_holdout_clusters(
    rows: list[dict[str, Any]],
    *,
    cutoff_year: int,
    policy: dict[str, Any],
) -> dict[str, Any]:
    clusters = sorted({cluster_id(row) for row in rows if cluster_id(row)})
    entity_holdouts: set[str] = set()
    temporal_holdouts: set[str] = set()

    if policy["entity_isolation"] == "entity_component":
        entity_holdouts = _component_holdouts(
            rows,
            clusters,
            key_fn=entity_ids,
            seed_fn=lambda row: any(entity_is_holdout(v) for v in entity_ids(row)),
        )
    else:
        entity_holdouts = {
            cluster_id(row)
            for row in rows
            if any(entity_is_holdout(v) for v in entity_ids(row))
        }

    if policy["temporal_isolation"] == "entity_metric_series_component":
        temporal_holdouts = _component_holdouts(
            rows,
            clusters,
            key_fn=entity_metric_series_keys,
            seed_fn=lambda row: (latest_year(row.get("time_scope")) or 0)
            >= cutoff_year,
        )
    else:
        temporal_holdouts = {
            cluster_id(row)
            for row in rows
            if (latest_year(row.get("time_scope")) or 0) >= cutoff_year
        }

    return {
        "entity_holdout_clusters": entity_holdouts,
        "temporal_holdout_clusters": temporal_holdouts,
        "entity_holdout_cluster_count": len(entity_holdouts),
        "temporal_holdout_cluster_count": len(temporal_holdouts),
    }


def audit_split_leakage(
    rows: list[dict[str, Any]], policy: dict[str, Any]
) -> dict[str, Any]:
    maximum_examples = int(policy["maximum_reported_examples"])
    semantic = _multi_split_overlap(rows, lambda row: {cluster_id(row)})
    entity = _target_overlap(rows, "test_entity_holdout", entity_ids)
    temporal_exact = _target_overlap(
        rows, "test_temporal_holdout", entity_metric_period_keys
    )
    temporal_series = _target_overlap(
        rows, "test_temporal_holdout", entity_metric_series_keys
    )
    complex_pattern = _target_overlap(rows, "test_complex", lambda row: {pattern_identity(row)})
    documents = _evaluation_overlap(rows, source_document_ids)
    skeletons = _evaluation_overlap(
        rows, lambda row: {_digest(canonical_question_skeleton(row))}
    )

    checks = {
        "semantic_cluster": _check_payload(semantic, maximum_examples),
        "entity_holdout_entity": _check_payload(entity, maximum_examples),
        "temporal_holdout_entity_metric_period": _check_payload(
            temporal_exact, maximum_examples
        ),
        "temporal_holdout_entity_metric_series": _check_payload(
            temporal_series, maximum_examples
        ),
        "complex_holdout_pattern": _check_payload(
            complex_pattern, maximum_examples
        ),
        "source_document": _check_payload(documents, maximum_examples),
        "canonical_question_skeleton": _check_payload(
            skeletons, maximum_examples
        ),
    }
    enforcement = {
        "semantic_cluster": policy["enforce_semantic_cluster_disjoint"],
        "entity_holdout_entity": policy["enforce_entity_holdout_disjoint"],
        "temporal_holdout_entity_metric_period": policy[
            "enforce_temporal_exact_disjoint"
        ],
        "temporal_holdout_entity_metric_series": policy[
            "enforce_temporal_series_disjoint"
        ],
        "complex_holdout_pattern": policy["enforce_complex_pattern_disjoint"],
        "source_document": policy["enforce_source_document_disjoint"],
        "canonical_question_skeleton": policy[
            "enforce_question_skeleton_disjoint"
        ],
    }
    violations = [
        name
        for name, check in checks.items()
        if enforcement[name] and int(check["overlap_count"]) > 0
    ]
    return {
        "policy": policy,
        "train_splits": sorted(TRAIN_SPLITS),
        "checks": checks,
        "enforcement": enforcement,
        "violations": violations,
        "passed": not violations,
    }


def _component_holdouts(
    rows: list[dict[str, Any]],
    clusters: list[str],
    *,
    key_fn: Any,
    seed_fn: Any,
) -> set[str]:
    dsu = _DisjointSet(clusters)
    owner: dict[str, str] = {}
    seeded_clusters: set[str] = set()
    for row in rows:
        cluster = cluster_id(row)
        if not cluster:
            continue
        if seed_fn(row):
            seeded_clusters.add(cluster)
        for key in key_fn(row):
            if key in owner:
                dsu.union(cluster, owner[key])
            else:
                owner[key] = cluster
    seeded_roots = {dsu.find(cluster) for cluster in seeded_clusters}
    return {cluster for cluster in clusters if dsu.find(cluster) in seeded_roots}


def _target_overlap(rows: list[dict[str, Any]], target_split: str, key_fn: Any) -> dict[str, Any]:
    train_keys = _keys_for_splits(rows, TRAIN_SPLITS, key_fn)
    target_keys = _keys_for_splits(rows, {target_split}, key_fn)
    overlap = train_keys & target_keys
    return _overlap_payload(train_keys, target_keys, overlap, target_split)


def _evaluation_overlap(rows: list[dict[str, Any]], key_fn: Any) -> dict[str, Any]:
    train_keys = _keys_for_splits(rows, TRAIN_SPLITS, key_fn)
    evaluation_splits = {
        str(row.get("split"))
        for row in rows
        if row.get("split") and str(row.get("split")) not in TRAIN_SPLITS
    }
    target_keys = _keys_for_splits(rows, evaluation_splits, key_fn)
    overlap = train_keys & target_keys
    per_split = {}
    for split in sorted(evaluation_splits):
        split_keys = _keys_for_splits(rows, {split}, key_fn)
        per_split[split] = len(train_keys & split_keys)
    payload = _overlap_payload(train_keys, target_keys, overlap, "all_evaluation")
    payload["overlap_count_by_split"] = per_split
    return payload


def _multi_split_overlap(rows: list[dict[str, Any]], key_fn: Any) -> dict[str, Any]:
    key_splits: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        split = str(row.get("split") or "")
        for key in key_fn(row):
            if key:
                key_splits[str(key)].add(split)
    overlap = {key for key, splits in key_splits.items() if len(splits) > 1}
    return {
        "train_key_count": 0,
        "target_key_count": len(key_splits),
        "overlap_count": len(overlap),
        "overlap_rate_of_target": len(overlap) / len(key_splits) if key_splits else 0.0,
        "target_split": "all_splits",
        "overlap_keys": overlap,
    }


def _keys_for_splits(
    rows: list[dict[str, Any]], splits: set[str] | frozenset[str], key_fn: Any
) -> set[str]:
    result: set[str] = set()
    for row in rows:
        if str(row.get("split") or "") in splits:
            result.update(str(value) for value in key_fn(row) if str(value).strip())
    return result


def _overlap_payload(
    train_keys: set[str], target_keys: set[str], overlap: set[str], target_split: str
) -> dict[str, Any]:
    return {
        "train_key_count": len(train_keys),
        "target_key_count": len(target_keys),
        "overlap_count": len(overlap),
        "overlap_rate_of_target": len(overlap) / len(target_keys) if target_keys else 0.0,
        "target_split": target_split,
        "overlap_keys": overlap,
    }


def _check_payload(payload: dict[str, Any], maximum_examples: int) -> dict[str, Any]:
    out = dict(payload)
    overlap = sorted(out.pop("overlap_keys", set()))
    out["overlap_examples"] = overlap[:maximum_examples]
    out["passed"] = not overlap
    return out


def _normalize_skeleton(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]
