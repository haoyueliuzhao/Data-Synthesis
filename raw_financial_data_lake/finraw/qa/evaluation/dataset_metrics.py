from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any


ADVANCED_PIPELINES = {"automatic_pattern_mining", "typed_edge_walk"}


def compute_dataset_role_values(
    bundles: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    eligible = [
        bundle
        for bundle in bundles
        if bundle.get("deterministic_gate_status") == "passed"
    ]
    features = {bundle["qa_id"]: _features(bundle) for bundle in eligible}
    counters = {
        name: Counter(row[name] for row in features.values())
        for name in (
            "task_market_language",
            "operation_answer",
            "source_metric",
            "pattern",
            "skeleton",
        )
    }
    outputs: dict[str, dict[str, Any]] = {}
    for bundle in bundles:
        qa_id = str(bundle["qa_id"])
        if qa_id not in features:
            outputs[qa_id] = {
                "dataset_role_value_score": 0.0,
                "coverage_contributions": [],
                "components": {},
            }
            continue
        row = features[qa_id]
        components = {
            "task_market_language_rarity": _rarity(
                counters["task_market_language"], row["task_market_language"]
            ),
            "operation_answer_rarity": _rarity(
                counters["operation_answer"], row["operation_answer"]
            ),
            "source_metric_rarity": _rarity(
                counters["source_metric"], row["source_metric"]
            ),
            "advanced_pipeline_value": (
                100.0 if row["pipeline"] in ADVANCED_PIPELINES else 35.0
            ),
            "holdout_value": 100.0 if row["split"] != "train" else 40.0,
            "kg_structure_rarity": _rarity(counters["pattern"], row["pattern"]),
            "surface_rarity": _rarity(counters["skeleton"], row["skeleton"]),
        }
        score = (
            0.20 * components["task_market_language_rarity"]
            + 0.20 * components["operation_answer_rarity"]
            + 0.15 * components["source_metric_rarity"]
            + 0.15 * components["advanced_pipeline_value"]
            + 0.15 * components["holdout_value"]
            + 0.10 * components["kg_structure_rarity"]
            + 0.05 * components["surface_rarity"]
        )
        contributions = [
            name.removesuffix("_rarity").removesuffix("_value")
            for name, value in components.items()
            if value >= 75
        ]
        outputs[qa_id] = {
            "dataset_role_value_score": round(score, 6),
            "coverage_contributions": sorted(contributions),
            "components": {key: round(value, 6) for key, value in components.items()},
        }
    return outputs


def build_slice_metrics(
    bundles: list[dict[str, Any]], evaluation_items: list[dict[str, Any]]
) -> dict[str, Any]:
    bundle_by_qa = {str(row["qa_id"]): row for row in bundles}
    item_by_qa = {str(row["qa_id"]): row for row in evaluation_items}
    dimensions = (
        "benchmark_task",
        "market_subset",
        "language",
        "difficulty",
        "generation_pipeline",
        "primary_operation_family",
        "answer_type",
        "topic",
        "metric_family",
        "source_class",
        "time_span_bucket",
    )
    output: dict[str, Any] = {}
    for dimension in dimensions:
        groups: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = defaultdict(list)
        for qa_id, item in item_by_qa.items():
            bundle = bundle_by_qa.get(qa_id)
            if not bundle:
                continue
            groups[str(_slice_value(bundle, dimension) or "unknown")].append(
                (item, bundle)
            )
        output[dimension] = {
            key: _summarize_items(
                [row[0] for row in rows], [row[1] for row in rows]
            )
            for key, rows in sorted(groups.items())
        }
    return output


def _features(bundle: dict[str, Any]) -> dict[str, str]:
    label = bundle["distribution_label"]
    sample = bundle["sample"]
    candidate = bundle["candidate"]
    source_classes = "+".join(sorted(label.get("source_classes") or ["unknown"]))
    metric_families = "+".join(
        sorted(label.get("metric_families") or candidate.get("metric_ids") or ["unknown"])
    )
    operation = str(label.get("primary_operation_family") or "lookup")
    answer_type = str(label.get("answer_type") or sample.get("answer_type") or "unknown")
    return {
        "task_market_language": "|".join(
            (
                str(label.get("benchmark_task") or "unknown"),
                str(label.get("market_subset") or "unknown"),
                str(sample.get("language") or "unknown"),
            )
        ),
        "operation_answer": f"{operation}|{answer_type}",
        "source_metric": f"{source_classes}|{metric_families}",
        "pipeline": str(label.get("generation_pipeline") or "unknown"),
        "split": str(sample.get("split") or "unassigned"),
        "pattern": str(candidate.get("pattern_id") or candidate.get("task_subtype") or "legacy"),
        "skeleton": _question_skeleton(str(sample.get("question") or "")),
    }


def _rarity(counter: Counter[str], key: str) -> float:
    if not counter:
        return 0.0
    count = counter.get(key, 0)
    maximum = max(counter.values(), default=1)
    if maximum <= 1:
        return 100.0
    return round(25.0 + 75.0 * (maximum - count) / (maximum - 1), 6)


def _question_skeleton(question: str) -> str:
    value = question.casefold()
    value = re.sub(r"\b\d{4}(?:-\d{2}-\d{2})?\b", "<period>", value)
    value = re.sub(r"[-+]?\d+(?:\.\d+)?%?", "<number>", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _slice_value(bundle: dict[str, Any], dimension: str) -> Any:
    label = bundle["distribution_label"]
    sample = bundle["sample"]
    if dimension == "language":
        return sample.get("language")
    if dimension == "difficulty":
        return sample.get("difficulty")
    if dimension == "answer_type":
        return sample.get("answer_type")
    if dimension == "metric_family":
        return "+".join(sorted(label.get("metric_families") or ["unknown"]))
    if dimension == "source_class":
        return "+".join(sorted(label.get("source_classes") or ["unknown"]))
    if dimension == "time_span_bucket":
        months = int(label.get("time_span_months") or 0)
        if months <= 12:
            return "up_to_1y"
        if months <= 36:
            return "1y_to_3y"
        if months <= 120:
            return "3y_to_10y"
        return "10y_plus"
    return label.get(dimension)


def _summarize_items(
    items: list[dict[str, Any]], bundles: list[dict[str, Any]]
) -> dict[str, Any]:
    subjective = sorted(
        float(item["subjective_quality_score"])
        for item in items
        if item.get("subjective_quality_score") is not None
    )
    role_values = [float(item.get("dataset_role_value_score") or 0) for item in items]
    skeleton_counts = Counter(
        _question_skeleton(str(bundle["sample"].get("question") or ""))
        for bundle in bundles
    )
    duplicate_count = sum(
        count for count in skeleton_counts.values() if count > 1
    )
    return {
        "sample_count": len(items),
        "deterministic_pass_rate": _rate(
            item.get("deterministic_gate_status") == "passed" for item in items
        ),
        "subjective_mean": _mean(subjective),
        "subjective_p10": _percentile(subjective, 0.10),
        "subjective_p50": _percentile(subjective, 0.50),
        "subjective_p90": _percentile(subjective, 0.90),
        "fatal_flag_rate": _rate(bool(item.get("fatal_flags")) for item in items),
        "manual_review_rate": _rate(
            item.get("decision") == "manual_review" for item in items
        ),
        "judge_disagreement_rate": _rate(
            bool(item.get("judge_disagreement", {}).get("requires_adjudication"))
            for item in items
        ),
        "dataset_role_value_mean": _mean(role_values),
        "skeleton_duplicate_rate": round(
            duplicate_count / len(bundles), 6
        )
        if bundles
        else 0.0,
    }


def _rate(values: Any) -> float:
    rows = list(values)
    return round(sum(bool(value) for value in rows) / len(rows), 6) if rows else 0.0


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 6) if values else None


def _percentile(values: list[float], ratio: float) -> float | None:
    if not values:
        return None
    index = round((len(values) - 1) * ratio)
    return round(values[index], 6)
