from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from finraw.qa.contamination import add_contamination_fingerprints
from finraw.qa.split_leakage import (
    TRAIN_SPLITS,
    canonical_question_skeleton,
)


DATASET_ROLE_POLICY_VERSION = "qa_dataset_role.v2"
GAP_DIMENSIONS = (
    "benchmark_task",
    "market_subset",
    "topic",
    "primary_operation_family",
    "frequency",
    "time_span_bucket",
    "answer_type",
)

DEFAULT_DATASET_ROLE_CONTRACT = {
    "contract_id": "finsearchcomp_t2_t3_release.v1",
    "training_splits": sorted(TRAIN_SPLITS),
    "target_distributions": [
        {
            "name": "benchmark_task_market",
            "fields": ["benchmark_task", "market_subset"],
            "weight": 0.45,
            "shares": {
                "T2|global": 119 / 391,
                "T2|greater_china": 100 / 391,
                "T3|global": 84 / 391,
                "T3|greater_china": 88 / 391,
            },
        },
        {
            "name": "market_language",
            "fields": ["market_subset", "language"],
            "weight": 0.25,
            "shares": {
                "global|en": (203 / 391) * 0.80,
                "global|zh": (203 / 391) * 0.15,
                "global|bilingual": (203 / 391) * 0.05,
                "greater_china|zh": (188 / 391) * 0.65,
                "greater_china|en": (188 / 391) * 0.20,
                "greater_china|bilingual": (188 / 391) * 0.15,
            },
        },
        {
            "name": "generation_pipeline",
            "fields": ["generation_pipeline"],
            "weight": 0.30,
            "shares": {
                "fact_qa": 0.30,
                "derived_fact_qa": 0.25,
                "static_graph_pattern": 0.25,
                "automatic_pattern_mining": 0.12,
                "typed_edge_walk": 0.08,
            },
        },
    ],
    "gap_manifest_paths": [],
    "gap_manifest_weight": 1.0,
    "maximum_per_surface_signature": 25,
    "maximum_per_program_signature": 250,
}


def compute_dataset_role_values(
    bundles: list[dict[str, Any]],
    contract: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    resolved = resolve_dataset_role_contract(contract)
    eligible = [
        bundle
        for bundle in bundles
        if bundle.get("deterministic_gate_status") == "passed"
    ]
    features = {str(bundle["qa_id"]): _features(bundle) for bundle in eligible}
    training_splits = set(
        str(item) for item in resolved.get("training_splits") or TRAIN_SPLITS
    )
    training_features = {
        qa_id: row
        for qa_id, row in features.items()
        if row["split"] in training_splits
    }
    distributions = _compiled_distributions(resolved, training_features)
    gap_targets = _compiled_gap_targets(resolved, training_features)
    surface_counts = Counter(
        row["surface_signature"] for row in training_features.values()
    )
    program_counts = Counter(
        row["operation_program_signature"] for row in training_features.values()
    )

    outputs: dict[str, dict[str, Any]] = {}
    for bundle in bundles:
        qa_id = str(bundle["qa_id"])
        if qa_id not in features:
            outputs[qa_id] = _ineligible_output(
                resolved, "deterministic_gate_failed"
            )
            continue
        row = features[qa_id]
        training_eligible = row["split"] in training_splits
        distribution_values: dict[str, float] = {}
        weighted_values: list[tuple[float, float]] = []
        contributions: list[str] = []
        for distribution in distributions:
            key = _stratum_key(row, distribution["fields"])
            value = float(distribution["values"].get(key, 0.0))
            distribution_values[
                "gap_" + str(distribution["name"])
            ] = value
            weighted_values.append((value, float(distribution["weight"])))
            if value >= 50:
                contributions.append("gap:" + str(distribution["name"]) + ":" + key)

        matching_gap_values = []
        for target in gap_targets:
            if _matches_selector(row, target["selector"]):
                matching_gap_values.append(float(target["value"]))
                if float(target["value"]) >= 50:
                    contributions.append(
                        "gap_manifest:" + str(target["target_id"])
                    )
        if matching_gap_values:
            weighted_values.append(
                (
                    max(matching_gap_values),
                    float(resolved.get("gap_manifest_weight") or 1.0),
                )
            )
            distribution_values["gap_manifest"] = max(matching_gap_values)

        gap_alignment = _weighted_mean(weighted_values)
        surface_capacity = _capacity_value(
            surface_counts[row["surface_signature"]],
            int(resolved["maximum_per_surface_signature"]),
        )
        program_capacity = _capacity_value(
            program_counts[row["operation_program_signature"]],
            int(resolved["maximum_per_program_signature"]),
        )
        signature_capacity = 0.6 * surface_capacity + 0.4 * program_capacity
        split_value = 100.0 if training_eligible else 0.0
        score = (
            0.85 * gap_alignment
            + 0.10 * signature_capacity
            + 0.05 * split_value
        )
        if not training_eligible:
            score = 0.0
            contributions = []
        components = {
            **distribution_values,
            "gap_alignment_value": round(gap_alignment, 6),
            "surface_signature_capacity": round(surface_capacity, 6),
            "operation_program_capacity": round(program_capacity, 6),
            "signature_capacity_value": round(signature_capacity, 6),
            "training_split_value": split_value,
            "training_release_eligible": 100.0 if training_eligible else 0.0,
        }
        outputs[qa_id] = {
            "dataset_role_policy_version": DATASET_ROLE_POLICY_VERSION,
            "dataset_role_contract_id": resolved["contract_id"],
            "dataset_role_value_score": round(score, 6),
            "coverage_contributions": sorted(set(contributions)),
            "components": components,
            "training_release_eligible": training_eligible,
            "release_role": (
                "sft_training"
                if row["split"] == "train"
                else "sft_complex_training"
                if row["split"] == "train_complex"
                else "evaluation_holdout"
            ),
            "release_exclusion_reason": (
                None if training_eligible else f"split_not_training:{row['split']}"
            ),
            "signatures": {
                "protected_or_template_signature": row["protected_or_template_signature"],
                "slot_normalized_signature": row["slot_normalized_signature"],
                "operation_program_signature": row["operation_program_signature"],
                "surface_signature": row["surface_signature"],
            },
        }
    return outputs


def resolve_dataset_role_contract(
    contract: dict[str, Any] | None,
) -> dict[str, Any]:
    resolved = {
        **DEFAULT_DATASET_ROLE_CONTRACT,
        **dict(contract or {}),
    }
    resolved["contract_id"] = str(
        resolved.get("contract_id") or "unnamed_dataset_role_contract"
    )
    training_splits = tuple(
        str(item) for item in resolved.get("training_splits") or TRAIN_SPLITS
    )
    if set(training_splits) - set(TRAIN_SPLITS):
        raise ValueError(
            "Dataset Role training_splits may contain only train and train_complex"
        )
    resolved["training_splits"] = list(training_splits)
    for key in (
        "maximum_per_surface_signature",
        "maximum_per_program_signature",
    ):
        resolved[key] = max(int(resolved.get(key) or 1), 1)

    target_distributions = []
    for raw in resolved.get("target_distributions") or []:
        distribution = dict(raw)
        name = str(distribution.get("name") or "")
        fields = [str(item) for item in distribution.get("fields") or []]
        shares = {
            str(key): float(value)
            for key, value in dict(distribution.get("shares") or {}).items()
        }
        if not name or not fields or not shares:
            raise ValueError("Each target distribution requires name, fields, and shares")
        if any(value < 0 for value in shares.values()):
            raise ValueError(f"Negative target share in {name}")
        total = sum(shares.values())
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Target shares for {name} must sum to 1; observed={total}")
        target_distributions.append(
            {
                "name": name,
                "fields": fields,
                "shares": shares,
                "weight": max(float(distribution.get("weight") or 0), 0.0),
            }
        )
    if not target_distributions:
        raise ValueError("Dataset Role contract has no target distributions")
    resolved["target_distributions"] = target_distributions
    resolved["gap_manifest_paths"] = [
        str(item) for item in resolved.get("gap_manifest_paths") or []
    ]
    return resolved


def build_slice_metrics(
    bundles: list[dict[str, Any]],
    evaluation_items: list[dict[str, Any]],
    *,
    minimum_slice_size: int = 30,
) -> dict[str, Any]:
    bundle_by_qa = {str(row["qa_id"]): row for row in bundles}
    item_by_qa = {str(row["qa_id"]): row for row in evaluation_items}
    dimensions = (
        "benchmark_task",
        "task_subtype",
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
                [row[0] for row in rows],
                [row[1] for row in rows],
                minimum_slice_size=minimum_slice_size,
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
    months = int(label.get("time_span_months") or 0)
    row = {
        "benchmark_task": str(label.get("benchmark_task") or "unknown"),
        "market_subset": str(label.get("market_subset") or "unknown"),
        "language": str(sample.get("language") or label.get("language") or "unknown"),
        "topic": str(label.get("topic") or "unknown"),
        "primary_operation_family": operation,
        "frequency": str(label.get("frequency") or "unknown"),
        "time_span_bucket": _time_span_bucket(months),
        "answer_type": answer_type,
        "generation_pipeline": str(label.get("generation_pipeline") or "unknown"),
        "source_metric": f"{source_classes}|{metric_families}",
        "split": str(sample.get("split") or "unassigned"),
        "pattern": str(
            candidate.get("pattern_id")
            or candidate.get("task_subtype")
            or "legacy"
        ),
    }
    fingerprint_input = {
        "question": sample.get("question"),
        "answer_type": answer_type,
        "metric_families": label.get("metric_families") or candidate.get("metric_ids") or [],
        "operation_families": label.get("operation_families") or [operation],
        "time_basis": label.get("time_basis"),
        "frequency": label.get("frequency"),
        "structural_features": label.get("structural_features") or {},
    }
    fingerprints = add_contamination_fingerprints(
        fingerprint_input, official=False
    )
    skeleton_input = {
        **sample,
        "canonical_semantics": candidate.get("canonical_semantics") or {},
    }
    protected_or_template = canonical_question_skeleton(skeleton_input)
    row.update(
        {
            "protected_or_template_signature": protected_or_template,
            "slot_normalized_signature": str(
                fingerprints["slot_normalized_signature"]
            ),
            "operation_program_signature": str(
                fingerprints["operation_program_signature"]
            ),
            "surface_signature": "|".join(
                (
                    protected_or_template,
                    str(fingerprints["slot_normalized_signature"]),
                    str(fingerprints["operation_program_signature"]),
                )
            ),
        }
    )
    return row


def _compiled_distributions(
    contract: dict[str, Any],
    features: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    total = int(contract.get("target_release_count") or len(features))
    output = []
    for distribution in contract["target_distributions"]:
        fields = list(distribution["fields"])
        counts = Counter(_stratum_key(row, fields) for row in features.values())
        values = {}
        for key, target_share in distribution["shares"].items():
            target_count = float(target_share) * total
            current_count = counts.get(key, 0)
            values[key] = _gap_value(target_count, current_count)
        output.append({**distribution, "values": values})
    return output


def _compiled_gap_targets(
    contract: dict[str, Any],
    features: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    raw_targets = list(contract.get("gap_manifest") or [])
    for path_text in contract.get("gap_manifest_paths") or []:
        path = Path(path_text)
        if not path.exists():
            raise FileNotFoundError(f"Dataset Role gap manifest not found: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        raw_targets.extend(payload.get("gaps") or [])
    output = []
    for index, raw in enumerate(raw_targets):
        target_count = float(raw.get("target_count") or 0)
        if target_count <= 0:
            continue
        selector = {
            key: str(raw[key])
            for key in GAP_DIMENSIONS
            if raw.get(key) is not None
        }
        if not selector:
            continue
        current_count = sum(
            _matches_selector(row, selector) for row in features.values()
        )
        output.append(
            {
                "target_id": raw.get("gap_id")
                or raw.get("target_id")
                or f"gap_{index:05d}",
                "selector": selector,
                "target_count": target_count,
                "current_count": current_count,
                "value": _gap_value(target_count, current_count),
            }
        )
    return output


def _gap_value(target_count: float, current_count: int) -> float:
    if target_count <= 0 or current_count >= target_count:
        return 0.0
    return round(100.0 * (target_count - current_count) / target_count, 6)


def _capacity_value(count: int, maximum: int) -> float:
    if count <= maximum:
        return 100.0
    return round(100.0 * maximum / count, 6)


def _weighted_mean(values: list[tuple[float, float]]) -> float:
    denominator = sum(weight for _, weight in values if weight > 0)
    if not denominator:
        return 0.0
    return sum(value * weight for value, weight in values if weight > 0) / denominator


def _stratum_key(row: dict[str, str], fields: list[str]) -> str:
    return "|".join(str(row.get(field) or "unknown") for field in fields)


def _matches_selector(row: dict[str, str], selector: dict[str, str]) -> bool:
    return all(str(row.get(key) or "unknown") == value for key, value in selector.items())


def _ineligible_output(
    contract: dict[str, Any], reason: str
) -> dict[str, Any]:
    return {
        "dataset_role_policy_version": DATASET_ROLE_POLICY_VERSION,
        "dataset_role_contract_id": contract["contract_id"],
        "dataset_role_value_score": 0.0,
        "coverage_contributions": [],
        "components": {
            "training_release_eligible": 0.0,
            "gap_alignment_value": 0.0,
        },
        "training_release_eligible": False,
        "release_role": "ineligible",
        "release_exclusion_reason": reason,
        "signatures": {},
    }


def _slice_value(bundle: dict[str, Any], dimension: str) -> Any:
    label = bundle["distribution_label"]
    sample = bundle["sample"]
    if dimension == "language":
        return sample.get("language")
    if dimension == "task_subtype":
        return sample.get("task_subtype") or bundle["candidate"].get(
            "task_subtype"
        )
    if dimension == "difficulty":
        return sample.get("difficulty")
    if dimension == "answer_type":
        return sample.get("answer_type")
    if dimension == "metric_family":
        return "+".join(sorted(label.get("metric_families") or ["unknown"]))
    if dimension == "source_class":
        return "+".join(sorted(label.get("source_classes") or ["unknown"]))
    if dimension == "time_span_bucket":
        return _time_span_bucket(int(label.get("time_span_months") or 0))
    return label.get(dimension)


def _time_span_bucket(months: int) -> str:
    if months <= 12:
        return "up_to_1y"
    if months <= 36:
        return "1y_to_3y"
    if months <= 120:
        return "3y_to_10y"
    return "10y_plus"


def _summarize_items(
    items: list[dict[str, Any]],
    bundles: list[dict[str, Any]],
    *,
    minimum_slice_size: int,
) -> dict[str, Any]:
    subjective = sorted(
        float(item["subjective_quality_score"])
        for item in items
        if item.get("subjective_quality_score") is not None
    )
    role_values = [float(item.get("dataset_role_value_score") or 0) for item in items]
    signature_counts = Counter(
        _features(bundle)["surface_signature"] for bundle in bundles
    )
    duplicate_count = sum(count for count in signature_counts.values() if count > 1)
    sample_count = len(items)
    deterministic_pass_count = sum(
        item.get("deterministic_gate_status") == "passed" for item in items
    )
    accepted_count = sum(
        item.get("decision") in {"accepted", "accepted_for_coverage"}
        for item in items
    )
    fatal_count = sum(bool(item.get("fatal_flags")) for item in items)
    return {
        "sample_count": sample_count,
        "minimum_recommended_slice_size": minimum_slice_size,
        "insufficient_slice_size": sample_count < minimum_slice_size,
        "interpretation_status": (
            "insufficient_slice_size"
            if sample_count < minimum_slice_size
            else "descriptive_sample_size_met"
        ),
        "deterministic_pass_rate": _rate(
            item.get("deterministic_gate_status") == "passed" for item in items
        ),
        "subjective_mean": _mean(subjective),
        "subjective_p10": _percentile(subjective, 0.10),
        "subjective_p50": _percentile(subjective, 0.50),
        "subjective_p90": _percentile(subjective, 0.90),
        "fatal_flag_rate": _rate(bool(item.get("fatal_flags")) for item in items),
        "accepted_rate": _rate(
            item.get("decision") in {"accepted", "accepted_for_coverage"}
            for item in items
        ),
        "confidence_intervals_95": {
            "deterministic_pass_rate": _wilson_interval(
                deterministic_pass_count, sample_count
            ),
            "accepted_rate": _wilson_interval(accepted_count, sample_count),
            "fatal_flag_rate": _wilson_interval(fatal_count, sample_count),
        },
        "manual_review_rate": _rate(
            item.get("decision") == "manual_review" for item in items
        ),
        "judge_disagreement_rate": _rate(
            bool(item.get("judge_disagreement", {}).get("requires_adjudication"))
            for item in items
        ),
        "dataset_role_value_mean": _mean(role_values),
        "protected_signature_duplicate_rate": (
            round(duplicate_count / len(bundles), 6) if bundles else 0.0
        ),
    }


def _wilson_interval(
    successes: int,
    total: int,
    *,
    z: float = 1.959963984540054,
) -> dict[str, float | int | None]:
    if total <= 0:
        return {
            "successes": successes,
            "total": total,
            "lower": None,
            "upper": None,
        }
    proportion = successes / total
    denominator = 1 + (z * z / total)
    center = (proportion + z * z / (2 * total)) / denominator
    margin = (
        z
        * (
            (proportion * (1 - proportion) / total)
            + (z * z / (4 * total * total))
        )
        ** 0.5
        / denominator
    )
    return {
        "successes": successes,
        "total": total,
        "lower": round(max(0.0, center - margin), 6),
        "upper": round(min(1.0, center + margin), 6),
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
