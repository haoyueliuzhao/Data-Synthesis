"""Post-hoc descriptive dev effects under outcome-blind frozen public groups.

Consumes the completed V18 compact evidence, not episodes, gold programs, test
results, private references, APIs or model checkpoints. Original dev estimands
remain unchanged. Group summaries and common-support standardization are not
confirmatory inference, new test performance or causal evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RUN = REPO / (
    "trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/"
    "v18_researcher_continuation_01"
)
AUDIT = RUN / "v24_data_distribution_audit_01"
SEEDS = (11, 29, 47)
ARMS = ("static", "manual_plus", "manual_minus", "c_only", "full")
METRICS = ("execution_accuracy", "program_accuracy")
DIMENSIONS = (
    "intent_proxy",
    "input_size_bin",
    "question_size_bin",
    "report_group",
    "company",
    "year",
)
STANDARDIZATION_DIMENSIONS = ("intent_proxy", "input_size_bin")
STANDARDIZATION_TARGETS = ("sft1000", "train744", "feedback350", "calibration120")
MINIMUM_STABLE_SUPPORT = 20
COMPARISONS = {
    "Full-Static": ("full", "static"),
    "Full-C-only": ("full", "c_only"),
    "Manual+-Static": ("manual_plus", "static"),
    "Manual--Static": ("manual_minus", "static"),
    "C-only-Static": ("c_only", "static"),
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def content_id(value):
    return hashlib.sha256(canonical({k: v for k, v in value.items() if k != "id"})).hexdigest()


def read_json(path):
    raw = Path(path).read_bytes()
    return json.loads(raw), {
        "path": str(Path(path).resolve()),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def decode_evidence(evidence, expected_roster, expected_n=883):
    """Reject changed encoding, missing questions/models and aggregate drift."""
    roster = evidence["dev_task_keys"]
    require(len(roster) == len(set(roster)) == expected_n, "dev roster incomplete/duplicated")
    require(set(roster) == set(expected_roster), "public/evidence dev roster mismatch")
    require(len(expected_roster) == expected_n, "public dev roster duplicate/missing")
    expected_models = {f"seed{s}/{a}" for s in SEEDS for a in ARMS}
    require(set(evidence["models"]) == expected_models, "model roster changed")
    decoded = {}
    for name, model in evidence["models"].items():
        codes = model["outcome_codes"]
        require(
            isinstance(codes, str) and len(codes) == expected_n, "outcome roster length changed"
        )
        require(all(code in "0123" for code in codes), "invalid outcome code")
        decoded[name] = {}
        for shift, metric in enumerate(METRICS):
            values = [(int(code) >> shift) & 1 for code in codes]
            totals = model["metrics"][metric]
            require(
                totals["unknown"] == 0 and totals["correct"] == sum(values),
                "outcome aggregate changed",
            )
            require(
                math.isclose(
                    totals["complete_dataset_mean"], sum(values) / expected_n, abs_tol=1e-12
                ),
                "outcome mean changed",
            )
            decoded[name][metric] = values
    return roster, decoded


def delta_vectors(decoded, metric, comparison):
    left, right = COMPARISONS[comparison]
    return {
        str(seed): [
            a - b
            for a, b in zip(
                decoded[f"seed{seed}/{left}"][metric],
                decoded[f"seed{seed}/{right}"][metric],
                strict=True,
            )
        ]
        for seed in SEEDS
    }


def paired_summary(vectors, indices):
    require(bool(indices), "empty paired group")
    by_seed = {}
    for seed, vector in vectors.items():
        values = [vector[i] for i in indices]
        by_seed[seed] = {
            "n": len(values),
            "wins": sum(x > 0 for x in values),
            "losses": sum(x < 0 for x in values),
            "ties": sum(x == 0 for x in values),
            "mean_difference": statistics.mean(values),
        }
    return {
        "n_questions": len(indices),
        "by_seed": by_seed,
        "equal_seed_mean_difference": statistics.mean(
            v["mean_difference"] for v in by_seed.values()
        ),
        "pooled_repeated_pairs": {
            "n": len(indices) * len(vectors),
            **{key: sum(v[key] for v in by_seed.values()) for key in ("wins", "losses", "ties")},
            "independent_question_count": len(indices),
        },
    }


def category_indices(roster, features, dimension):
    groups = defaultdict(list)
    for index, task_key in enumerate(roster):
        require(
            task_key in features and dimension in features[task_key],
            "missing frozen public feature",
        )
        value = features[task_key][dimension]
        require(
            isinstance(value, (str, int)) and not isinstance(value, bool), "invalid category value"
        )
        groups[str(value)].append(index)
    return dict(sorted(groups.items()))


def leave_one_group(vectors, groups, n):
    """All observed groups, actual remaining denominator, no resampling."""
    require(
        set(i for indices in groups.values() for i in indices) == set(range(n)),
        "leave-out groups omit questions",
    )
    require(sum(map(len, groups.values())) == n, "leave-out groups overlap")
    sums = {seed: sum(vector) for seed, vector in vectors.items()}
    original = {seed: total / n for seed, total in sums.items()}
    original["equal_seed_mean"] = statistics.mean(original.values())
    rows = {}
    for name, removed in groups.items():
        remaining = n - len(removed)
        means = {
            seed: (sums[seed] - sum(vector[i] for i in removed)) / remaining if remaining else None
            for seed, vector in vectors.items()
        }
        means["equal_seed_mean"] = statistics.mean(means.values()) if remaining else None
        rows[name] = {
            "removed_n": len(removed),
            "remaining_n": remaining,
            "mean_difference": means,
            "change_from_original": {
                seed: value - original[seed] if value is not None else None
                for seed, value in means.items()
            },
        }
    summary = {}
    for seed, baseline in original.items():
        values = {
            group: row["mean_difference"][seed]
            for group, row in rows.items()
            if row["mean_difference"][seed] is not None
        }
        summary[seed] = {
            "original": baseline,
            "range": [min(values.values()), max(values.values())] if values else None,
            "max_absolute_change": max(
                (abs(value - baseline) for value in values.values()), default=None
            ),
            "sign_flip_groups": [name for name, value in values.items() if value * baseline < 0],
            "zero_groups": [name for name, value in values.items() if value == 0],
            "any_sign_flip": any(value * baseline < 0 for value in values.values()),
            "undefined_groups": [
                name for name, row in rows.items() if row["mean_difference"][seed] is None
            ],
        }
    return {"group_count": len(groups), "summary": summary, "all_leave_one_groups": rows}


def standardize(vectors, dev_groups, target_keys, features, dimension, minimum_dev_group_tasks=1):
    """Observed dev cell effects weighted by target mass on common support only."""
    require(bool(target_keys), "empty target population")
    counts = Counter()
    for key in target_keys:
        require(key in features and dimension in features[key], "target public feature missing")
        counts[str(features[key][dimension])] += 1
    require(minimum_dev_group_tasks >= 1, "invalid minimum dev support")
    positive_support = sorted(set(dev_groups) & set(counts))
    support = [
        name for name in positive_support if len(dev_groups[name]) >= minimum_dev_group_tasks
    ]
    target_on_h = sum(counts[name] for name in support)
    dev_on_h = sum(len(dev_groups[name]) for name in support)
    dev_n = sum(map(len, dev_groups.values()))
    rows = {}
    for seed, vector in vectors.items():
        cell_means = {
            name: statistics.mean(vector[i] for i in dev_groups[name]) for name in support
        }
        reweighted = (
            sum(counts[name] / target_on_h * cell_means[name] for name in support)
            if target_on_h
            else None
        )
        dev_h = (
            sum(len(dev_groups[name]) * cell_means[name] for name in support) / dev_on_h
            if dev_on_h
            else None
        )
        rows[seed] = {
            "standardized_mean_difference_on_H": reweighted,
            "unweighted_dev_mean_difference_on_H": dev_h,
            "unweighted_full_dev_mean_difference": statistics.mean(vector),
            "cell_mean_differences_on_H": cell_means,
        }
    rows["equal_seed_mean"] = {
        name: statistics.mean(row[name] for row in rows.values())
        if (support or name == "unweighted_full_dev_mean_difference")
        else None
        for name in (
            "standardized_mean_difference_on_H",
            "unweighted_dev_mean_difference_on_H",
            "unweighted_full_dev_mean_difference",
        )
    }
    return {
        "target_n_records": len(target_keys),
        "target_unique_task_keys": len(set(target_keys)),
        "dev_n": dev_n,
        "common_support_H": support,
        "target_missing_in_dev_categories": sorted(set(counts) - set(dev_groups)),
        "mathematical_positive_common_support": {
            "categories": positive_support,
            "target_covered_n": sum(counts[name] for name in positive_support),
            "target_coverage_fraction": sum(counts[name] for name in positive_support)
            / len(target_keys),
            "dev_covered_n": sum(len(dev_groups[name]) for name in positive_support),
            "dev_coverage_fraction": sum(len(dev_groups[name]) for name in positive_support)
            / dev_n,
            "standardized_effect_computed": False,
        },
        "minimum_dev_group_tasks": minimum_dev_group_tasks,
        "target_categories_below_minimum_dev_group_tasks": sorted(
            name
            for name in set(counts) & set(dev_groups)
            if len(dev_groups[name]) < minimum_dev_group_tasks
        ),
        "dev_absent_from_target_categories": sorted(set(dev_groups) - set(counts)),
        "target_category_counts": dict(sorted(counts.items())),
        "dev_category_counts": {name: len(indices) for name, indices in dev_groups.items()},
        "target_covered_n": target_on_h,
        "target_coverage_fraction": target_on_h / len(target_keys),
        "dev_covered_n": dev_on_h,
        "dev_coverage_fraction": dev_on_h / dev_n,
        "normalized_target_weights_on_H": {name: counts[name] / target_on_h for name in support},
        "by_seed": rows,
        "unsupported_cells_extrapolated": False,
        "estimand": (
            "Observed dev cell effects standardized to target composition conditional on H; "
            "not new test performance or causal evidence."
        ),
    }


def grouped_summary(vectors, indices, small_group_threshold=20):
    value = paired_summary(vectors, indices)
    value["descriptive_small_group_no_efficacy_claim"] = len(indices) < small_group_threshold
    return value


def analyze(
    evidence,
    features,
    populations,
    dev_population="dev883",
    targets=STANDARDIZATION_TARGETS,
    expected_n=883,
    minimum_support_tasks=MINIMUM_STABLE_SUPPORT,
):
    require(dev_population in populations, "dev population missing")
    roster, decoded = decode_evidence(evidence, populations[dev_population], expected_n)
    groups = {dimension: category_indices(roster, features, dimension) for dimension in DIMENSIONS}
    result = {
        "schema": "finqa_v24_dev_group_analysis.v1",
        "analysis_scope": (
            "Post-hoc descriptive analysis; grouping frozen before opening dev per-question "
            "outcomes, not prospective research registration."
        ),
        "original_dev_denominator": expected_n,
        "seeds_equal_weight": list(SEEDS),
        "registered_comparisons": list(COMPARISONS)[:4],
        "supplementary_comparisons": ["C-only-Static"],
        "confidence_intervals": None,
        "p_values": None,
        "new_scoring": False,
        "test_results_read": False,
        "API_calls": 0,
        "GPU_calls": 0,
        "all_categories_retained": True,
        "minimum_group_tasks_for_main_text_discussion": 20,
        "smaller_groups_machine_attachment_only": (
            "All paired counts and means retained, "
            "strongly flagged descriptive_small_group_no_efficacy_claim."
        ),
        "minimum_dev_tasks_for_common_support": minimum_support_tasks,
        "grouping_category_counts": {
            dim: {key: len(indices) for key, indices in group.items()}
            for dim, group in groups.items()
        },
        "grouping_size_diagnostics": {
            dim: {
                "n_categories": len(group),
                "n_singleton_categories": sum(len(indices) == 1 for indices in group.values()),
                "n_categories_below_5": sum(len(indices) < 5 for indices in group.values()),
                "n_categories_below_10": sum(len(indices) < 10 for indices in group.values()),
                "small_category_rule": (
                    "Descriptive warning only; no category excluded "
                    "and no confidence intervals computed."
                ),
                "unknown_category_counts": {
                    key: len(indices)
                    for key, indices in group.items()
                    if key.lower() in ("unknown", "missing", "none", "na")
                },
            }
            for dim, group in groups.items()
        },
        "metric_results": {},
    }
    for metric in METRICS:
        comparisons = {}
        for name in COMPARISONS:
            vectors = delta_vectors(decoded, metric, name)
            comparisons[name] = {
                "original_full_dev": paired_summary(vectors, list(range(expected_n))),
                "groups": {
                    dimension: {
                        category: grouped_summary(vectors, indices)
                        for category, indices in group.items()
                    }
                    for dimension, group in groups.items()
                },
                "leave_one_out": {
                    dim: leave_one_group(vectors, groups[dim], expected_n)
                    for dim in ("report_group", "company")
                },
                "common_support_standardization": {
                    dimension: {
                        target: standardize(
                            vectors,
                            groups[dimension],
                            populations[target],
                            features,
                            dimension,
                            minimum_support_tasks,
                        )
                        for target in targets
                        if target in populations
                    }
                    for dimension in STANDARDIZATION_DIMENSIONS
                },
            }
        result["metric_results"][metric] = comparisons
    return result


def persist(path, value):
    path = Path(path)
    raw = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        require(path.read_text() == raw, "immutable audit output differs")
    else:
        with path.open("x") as stream:
            stream.write(raw)


def freeze_analysis_protocol(audit_root, grouping_protocol):
    """Clarify effect-only coordination before the first outcome join; no feature changes."""
    body = {
        "schema": "finqa_v24_frozen_dev_analysis_protocol.v1",
        "grouping_protocol_id": grouping_protocol["id"],
        "grouping_rules_id": grouping_protocol["rules_id"],
        "reason": (
            "Implementation coordination before any group correctness join; "
            "historical global dev results already known. "
            "No outcome-informed rule change or prospective registration claim."
        ),
        "overrides_only": ["rules.dev_effect_suppression", "rules.common_support_effect_contract"],
        "feature_rules_regex_and_bins_unchanged": True,
        "metrics": list(METRICS),
        "registered_comparisons": list(COMPARISONS)[:4],
        "supplementary_comparisons": ["C-only-Static"],
        "group_dimensions": list(DIMENSIONS),
        "group_effect_contract": {
            "all_categories": (
                "Retain n, wins, losses, ties and paired means for each seed and equal-seed mean "
                "in machine attachment; never select favorable categories."
            ),
            "main_text_minimum_group_tasks": 20,
            "small_groups_flag": "descriptive_small_group_no_efficacy_claim",
            "registered_full_dev_denominator": 883,
            "confidence_intervals": None,
            "p_values": None,
        },
        "leave_one_out": {
            "fields": ["report_group", "company"],
            "all_groups": True,
            "actual_remaining_denominator": True,
            "estimand": "Overall paired effect sensitivity, not small-group efficacy.",
        },
        "standardization": {
            "fields": list(STANDARDIZATION_DIMENSIONS),
            "targets": list(STANDARDIZATION_TARGETS),
            "mathematical_positive_support": (
                "target_n > 0 AND dev_n > 0; report dev/target coverage only"
            ),
            "stable_support_H": (
                "target_n > 0 AND dev_n >= 20; report dev/target coverage, "
                "then renormalize target mass within H"
            ),
            "minimum_dev_group_tasks": MINIMUM_STABLE_SUPPORT,
            "effects_computed_only_on_stable_support": True,
            "unsupported_cells_filled_or_extrapolated": False,
            "joint_high_dimensional_cells": False,
            "interpretation": (
                "Observed dev cell effects standardized to target composition conditional on H, "
                "not new test performance or causal evidence."
            ),
        },
        "scope": {
            "post_hoc_descriptive": True,
            "test_correctness_read": False,
            "private_references_read": False,
            "new_API_or_GPU_calls": 0,
            "original_experiment_mutations": False,
        },
    }
    path = Path(audit_root) / "dev_analysis_protocol.json"
    if path.exists():
        protocol, _ = read_json(path)
        require(
            protocol.get("id") == content_id(protocol), "dev analysis protocol content ID mismatch"
        )
        require(
            {key: value for key, value in protocol.items() if key not in ("id", "frozen_at")}
            == body,
            "immutable dev analysis protocol differs",
        )
    else:
        protocol = {**body, "frozen_at": datetime.now(timezone.utc).isoformat()}
        protocol["id"] = content_id(protocol)
        persist(path, protocol)
    return protocol


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-root", type=Path, default=AUDIT)
    parser.add_argument(
        "--evidence", type=Path, default=RUN / "final_report_20261005/evidence.json"
    )
    parser.add_argument(
        "--freeze-only",
        action="store_true",
        help="Freeze analysis-only coordination before any per-question outcome access, then stop.",
    )
    args = parser.parse_args()
    # Public/protocol validation MUST precede the first per-question outcome read.
    protocol, protocol_ref = read_json(args.audit_root / "grouping_protocol.json")
    require(protocol.get("id") == content_id(protocol), "grouping protocol content ID mismatch")
    public, public_ref = read_json(args.audit_root / "public_features.json")
    require(public.get("protocol_id") == protocol["id"], "public features protocol binding changed")
    require(public.get("id") == content_id(public), "public features content ID mismatch")
    require(
        all(target in public["populations"] for target in STANDARDIZATION_TARGETS),
        "required standardization population missing",
    )
    analysis_protocol = freeze_analysis_protocol(args.audit_root, protocol)
    if args.freeze_only:
        print(
            json.dumps(
                {
                    "dev_analysis_protocol_id": analysis_protocol["id"],
                    "frozen_at": analysis_protocol["frozen_at"],
                    "per_question_outcomes_read": False,
                }
            )
        )
        return
    evidence, evidence_ref = read_json(args.evidence)
    result = analyze(evidence, public["features"], public["populations"])
    result["source_bindings"] = {
        "grouping_protocol": protocol_ref,
        "public_features": public_ref,
        "completed_dev_evidence": evidence_ref,
    }
    result["grouping_protocol_id"] = protocol["id"]
    result["dev_analysis_protocol_id"] = analysis_protocol["id"]
    result["dev_analysis_protocol_frozen_at"] = analysis_protocol["frozen_at"]
    result["outcome_access_gate"] = (
        "Grouping and public feature content IDs validated and immutable dev analysis protocol "
        "frozen before first per-question outcome file read."
    )
    result["id"] = content_id(result)
    path = args.audit_root / "dev_group_analysis.json"
    persist(path, result)
    print(
        json.dumps(
            {
                "path": str(path),
                "id": result["id"],
                "denominator": result["original_dev_denominator"],
            }
        )
    )


if __name__ == "__main__":
    main()
