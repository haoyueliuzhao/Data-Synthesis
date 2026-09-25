"""Read-only B confirmation report audit using saved metadata and binary scores.

No checkpoints, adapters, public task bodies, gzip sessions or private bundles
are opened. The only inferential calculation is a single exact reproduction of
the frozen primary analysis; subgroup and source contributions are descriptive.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from fractions import Fraction
from pathlib import Path

import fixed_kernel_B_confirmation_statistics_20260922 as statistics

from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p

STATISTICS_SCRIPT = (
    "trusted_data_synthesis/scripts/fixed_kernel_B_confirmation_statistics_20260922.py"
)


def _require(condition, message):
    p.require(condition, "B_report_statistics." + message)


def _fraction(value):
    return f"{value.numerator}/{value.denominator}"


def _summary(pairs):
    """Summarize fixed (static Q, delayed Q) pairs without changing weights."""
    _require(bool(pairs), "nonempty_pairs")
    for static, delayed in pairs:
        _require(
            type(static) is int and type(delayed) is int and static in (0, 1) and delayed in (0, 1),
            "binary_saved_Q",
        )
    denominator = len(pairs)
    baseline = sum(row[0] for row in pairs)
    treatment = sum(row[1] for row in pairs)
    counts = Counter(pairs)
    difference = Fraction(treatment - baseline, denominator)
    return {
        "denominator_per_arm": denominator,
        "static": {
            "qualified": baseline,
            "rate": baseline / denominator,
            "rate_rational": _fraction(Fraction(baseline, denominator)),
            "percent": 100 * baseline / denominator,
        },
        "delayed_c": {
            "qualified": treatment,
            "rate": treatment / denominator,
            "rate_rational": _fraction(Fraction(treatment, denominator)),
            "percent": 100 * treatment / denominator,
        },
        "net_qualified_difference": treatment - baseline,
        "rate_difference": float(difference),
        "rate_difference_rational": _fraction(difference),
        "percentage_point_difference": float(100 * difference),
        "paired": {
            "both_pass": counts[1, 1],
            "improved_static_fail_delayed_pass": counts[0, 1],
            "degraded_static_pass_delayed_fail": counts[1, 0],
            "both_fail": counts[0, 0],
        },
    }


def _concentration(clusters):
    """Post-run description of signed CIK net contributions, not a new test."""
    positive = sorted(
        (row for row in clusters if row["net_qualified_difference"] > 0),
        key=lambda row: (-row["net_qualified_difference"], row["cik"]),
    )
    negative = sorted(
        (row for row in clusters if row["net_qualified_difference"] < 0),
        key=lambda row: (row["net_qualified_difference"], row["cik"]),
    )
    positive_mass = sum(row["net_qualified_difference"] for row in positive)
    negative_mass = -sum(row["net_qualified_difference"] for row in negative)

    def shares(rows, mass):
        return {
            str(k): {
                "clusters_used": min(k, len(rows)),
                "absolute_net_count": sum(abs(row["net_qualified_difference"]) for row in rows[:k]),
                "share_of_same_sign_net_mass": (
                    sum(abs(row["net_qualified_difference"]) for row in rows[:k]) / mass
                    if mass
                    else None
                ),
            }
            for k in (1, 3, 5)
        }

    return {
        "descriptive_only_no_new_decision_rule": True,
        "positive_cluster_count": len(positive),
        "negative_cluster_count": len(negative),
        "zero_net_cluster_count": len(clusters) - len(positive) - len(negative),
        "positive_net_count_mass": positive_mass,
        "absolute_negative_net_count_mass": negative_mass,
        "absolute_cluster_net_count_mass": positive_mass + negative_mass,
        "net_count": positive_mass - negative_mass,
        "top_positive_clusters": [
            {"cik": row["cik"], "net_count": row["net_qualified_difference"]}
            for row in positive[:5]
        ],
        "top_negative_clusters": [
            {"cik": row["cik"], "net_count": row["net_qualified_difference"]}
            for row in negative[:5]
        ],
        "positive_top_k": shares(positive, positive_mass),
        "negative_top_k": shares(negative, negative_mass),
        "interpretation": (
            "Net counts are summed over all fixed task-seed pairs per CIK; within-CIK "
            "improvements and degradations can cancel. Shares use same-sign net mass, "
            "not the small overall net count; no causal or generalization claim follows."
        ),
    }


def extract(root: Path, raw: Path) -> dict:
    """Validate six completed cohorts and return JSON-safe audit statistics."""
    root, raw = Path(root).resolve(), Path(raw).resolve()
    evidence_files = []

    def read(relative, kind=None):
        path = raw / relative
        value = json.loads(path.read_bytes())
        if kind:
            p.checked(value, kind)
        evidence_files.append(
            {"path": str(path), "sha256": p.sha(path), "content_id": value.get("id")}
        )
        return value

    plan = read("protocol.json", "B_confirm_protocol")
    _require(
        plan["frozen"] is True
        and plan["candidate"] == "Delayed-C"
        and plan["baseline"] == "Static"
        and plan["seeds"] == list(statistics.SEEDS)
        and plan["models_count"] == 6
        and plan["confirm_tasks"] == 720
        and plan["tasks_per_group"] == 240,
        "fixed_confirmation_registration",
    )
    _require(
        p.sha(root / STATISTICS_SCRIPT) == plan["scientific_sources"][STATISTICS_SCRIPT],
        "original_frozen_statistics_source_bytes",
    )
    registry = plan["confirm_registry"]
    _require(p.sha(p.encode(registry)) == plan["confirm_registry_sha256"], "registry_hash")
    tasks = [
        {"task_id": row["task_id"], "group": row["group"], "cik": row["source_cluster"]}
        for row in registry
    ]
    manifest = read("confirm_views/manifest.json", "source_view_manifest_v2")
    _require(
        manifest["protocol_id"] == plan["id"]
        and manifest["original_registry_sha256"] == plan["confirm_registry_sha256"]
        and manifest["split"] == "confirm"
        and len(manifest["tasks"]) == manifest["task_count"] == 720,
        "manifest_registration",
    )
    _require(
        [(row["task_id"], row["group"], row["source_cluster"]) for row in manifest["tasks"]]
        == [(row["task_id"], row["group"], row["source_cluster"]) for row in registry],
        "exact_registered_tasks_groups_sources_and_order",
    )
    seal = read("confirmation_generation_seal.json", "B_confirm_generation_seal")
    _require(
        seal["protocol_id"] == plan["id"]
        and seal["source_manifest_id"] == manifest["id"]
        and seal["complete"] is True
        and seal["all_generation_workers_exited"] is True
        and seal["total_trajectories"] == 4320,
        "global_confirmation_generation_seal",
    )
    model_jobs = [row for row in plan["training_jobs"] if row["condition"] != "prefix"]
    expected = {(seed, arm) for seed in statistics.SEEDS for arm in statistics.ARMS}
    _require(
        len(model_jobs) == 6
        and len({row["key"] for row in model_jobs}) == 6
        and {(row["seed"], row["condition"]) for row in model_jobs} == expected
        and len(seal["models"]) == 6
        and {row["key"] for row in seal["models"]} == {row["key"] for row in model_jobs},
        "six_unique_fixed_models",
    )
    sealed_models = {row["key"]: row for row in seal["models"]}
    outcomes, models = [], []
    for model in model_jobs:
        key, seed, arm = model["key"], model["seed"], model["condition"]
        point = read(f"points/{key}/point.json", "anchored_model_parameter_point")
        _require(
            point["run"] == {"key": key, "seed": seed, "condition": arm, "pool": "B"}
            and point["step"] == 400
            and point["source_manifest_id"] == manifest["id"],
            "final_model_point_identity",
        )
        directory = Path("generation/confirm") / key
        registration = read(directory / "registration.json", "B_generation_registration")
        frozen = read(directory / "generation_manifest.json", "anchored_generation_manifest")
        score = read(directory / "scoring_report.json", "anchored_independent_scoring")
        bound = sealed_models[key]
        _require(
            bound["seed"] == seed
            and bound["condition"] == arm
            and bound["point_id"] == point["id"]
            and Path(bound["generation_manifest_path"]).resolve()
            == raw / directory / "generation_manifest.json"
            and bound["generation_manifest_sha256"]
            == p.sha(raw / directory / "generation_manifest.json"),
            "global_seal_exact_model_manifest_bytes",
        )
        _require(
            registration["protocol_id"] == frozen["protocol_id"] == plan["id"]
            and registration["seed"] == seed
            and registration["condition"] == arm
            and registration["stochastic"] is frozen["stochastic"] is False
            and registration["point_id"] == frozen["point_id"] == score["point_id"] == point["id"]
            and registration["source_manifest_id"]
            == frozen["source_manifest_id"]
            == score["source_manifest_id"]
            == manifest["id"]
            and frozen["complete"] is score["complete"] is True
            and frozen["tasks"] == manifest["tasks"]
            and score["generation_manifest_id"] == frozen["id"]
            and score["generation_seal_id"] == seal["id"]
            and score["financial_rule_unchanged"] is True
            and score["scoring_after_all_generation_complete"] is True
            and score["private_references_never_sent_to_generator"] is True
            and score["confirm_tasks_opened"] == 720
            and datetime.fromisoformat(score["finished_at"]) >= datetime.fromisoformat(seal["at"]),
            "cohort_point_source_seal_and_scoring_identity",
        )
        _require(
            len(registration["jobs"])
            == len(frozen["trajectories"])
            == len(score["scores"])
            == score["denominator"]
            == 720,
            "complete_720_rows_per_model",
        )
        for index, (task, job, item, value) in enumerate(
            zip(
                manifest["tasks"],
                registration["jobs"],
                frozen["trajectories"],
                score["scores"],
                strict=True,
            )
        ):
            p.checked(item, "anchored_generated_trajectory")
            _require(
                job["task"] == task
                and job["index"] == index
                and job["repeat"] == 0
                and item["job"] == job
                and item["point_id"] == point["id"]
                and item["private_assessment_performed"] is False
                and value["index"] == index
                and value["repeat"] == 0
                and value["task_id"] == task["task_id"]
                and value["group"] == task["group"]
                and value["session_id"] == item["session_id"]
                and type(value["Q"]) is int
                and value["Q"] in (0, 1),
                "exact_task_session_generation_score_join",
            )
            outcomes.append(
                {
                    "task_id": value["task_id"],
                    "group": value["group"],
                    "seed": seed,
                    "arm": arm,
                    "Q": value["Q"],
                }
            )
        _require(score["qualified"] == sum(row["Q"] for row in score["scores"]), "score_total")
        models.append(
            {
                "key": key,
                "seed": seed,
                "condition": arm,
                "point_id": point["id"],
                "registration_id": registration["id"],
                "generation_manifest_id": frozen["id"],
                "scoring_report_id": score["id"],
                "qualified": score["qualified"],
                "denominator": 720,
                "scoring_finished_at": score["finished_at"],
            }
        )

    # Exactly one recomputation under the frozen production rules.
    analysis = statistics.analyze_confirmation(tasks, outcomes)
    saved_analysis = read("confirmation_analysis.json")
    _require(analysis == saved_analysis, "strict_exact_frozen_analysis_reproduction")
    report = read("report.json", "B_confirm_completed_study")
    completion = read("complete.json", "B_confirm_completed_study")
    _require(
        report == completion
        and report["protocol_id"] == plan["id"]
        and report["point_estimate"] == analysis["point_estimate"]
        and report["ci95"] == analysis["ci95"]
        and report["positive_effect_confirmed"] == analysis["positive_effect_confirmed"],
        "completed_report_matches_saved_and_recomputed_analysis",
    )
    model_fields = ("key", "seed", "condition", "qualified", "denominator", "scoring_report_id")
    _require(
        report["models"] == [{field: row[field] for field in model_fields} for row in models],
        "completed_report_matches_all_six_scores",
    )

    lookup = {(row["task_id"], row["seed"], row["arm"]): row["Q"] for row in outcomes}

    def summarize(task_rows, seeds=statistics.SEEDS):
        return _summary(
            [
                (
                    lookup[task["task_id"], seed, "static"],
                    lookup[task["task_id"], seed, "delayed_c"],
                )
                for task in task_rows
                for seed in seeds
            ]
        )

    by_seed = [{"seed": seed, **summarize(tasks, (seed,))} for seed in statistics.SEEDS]
    by_group = [
        {"group": group, **summarize([task for task in tasks if task["group"] == group])}
        for group in statistics.GROUPS
    ]
    by_seed_group = [
        {
            "seed": seed,
            "group": group,
            **summarize([task for task in tasks if task["group"] == group], (seed,)),
        }
        for seed in statistics.SEEDS
        for group in statistics.GROUPS
    ]
    ciks = sorted({statistics._canonical_cik(task["cik"]) for task in tasks})
    by_cik = []
    for cik in ciks:
        cluster_tasks = [task for task in tasks if statistics._canonical_cik(task["cik"]) == cik]
        summary = summarize(cluster_tasks)
        by_cik.append(
            {
                "cik": cik,
                "task_count": len(cluster_tasks),
                "task_count_by_group": dict(Counter(task["group"] for task in cluster_tasks)),
                **summary,
                "contribution_to_overall_percentage_point_difference": 100
                * summary["net_qualified_difference"]
                / 2160,
                "net_qualified_difference_by_seed": {
                    str(seed): summarize(cluster_tasks, (seed,))["net_qualified_difference"]
                    for seed in statistics.SEEDS
                },
            }
        )
    aggregate = summarize(tasks)
    _require(
        aggregate["rate_difference_rational"] == analysis["point_estimate_rational"]
        and sum(row["net_qualified_difference"] for row in by_cik)
        == aggregate["net_qualified_difference"],
        "paired_aggregate_and_cluster_contribution_reconcile",
    )
    return {
        "schema_version": "fixed_kernel_B_report_statistics.20260925.v1",
        "metadata_only": True,
        "gzip_sessions_opened": 0,
        "private_bundles_opened": 0,
        "model_checkpoint_or_adapter_files_opened": 0,
        "protocol_id": plan["id"],
        "completed_report_id": report["id"],
        "confirmation_source_manifest_id": manifest["id"],
        "generation_seal_id": seal["id"],
        "generation_sealed_at": seal["at"],
        "completed_at": report["at"],
        "fixed_task_count": 720,
        "fixed_source_cluster_count": len(ciks),
        "paired_task_seed_count": 2160,
        "scored_sessions": 4320,
        "models": models,
        "aggregate": aggregate,
        "by_seed": by_seed,
        "by_group": by_group,
        "by_seed_group": by_seed_group,
        "by_CIK": by_cik,
        "CIK_contribution_concentration": _concentration(by_cik),
        "frozen_analysis_recomputed_once": True,
        "frozen_analysis_strictly_equal": True,
        "frozen_analysis": analysis,
        "ci95_percentage_points": {
            "lower": 100 * analysis["ci95"]["lower"],
            "upper": 100 * analysis["ci95"]["upper"],
            "lower_rational": _fraction(100 * Fraction(analysis["ci95"]["lower_rational"])),
            "upper_rational": _fraction(100 * Fraction(analysis["ci95"]["upper_rational"])),
        },
        "interpretation_boundaries": [
            "Positive point estimate does not satisfy the preregistered positive-effect rule "
            "when the interval crosses zero.",
            "Failure to confirm benefit is not evidence of equivalence or proof of no effect.",
            "The 4320 scored sessions contain 2160 arm-paired task-seed comparisons "
            "on the same 720 tasks, not 4320 independent tasks.",
            "The CIK interval conditions on these three fixed trained seeds "
            "and does not cover all training randomness.",
            "Seed, group and CIK breakdowns are post-run descriptive summaries, "
            "not additional confirmation criteria or causal diagnoses.",
            "Zero successes in a group does not identify whether model, interface, "
            "scoring or other mechanisms caused the result.",
        ],
        "evidence_files": evidence_files,
    }
