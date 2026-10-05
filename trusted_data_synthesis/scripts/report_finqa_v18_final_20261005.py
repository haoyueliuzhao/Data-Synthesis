"""Extract a compact, reproducible report from completed FinQA records only.

No generation, native rescoring, private-reference reads, tensor loads or API calls.
The registered mixed mechanism estimand is preserved; draw splits are descriptive.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RUN = REPO / (
    "trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/"
    "v18_researcher_continuation_01"
)
OUTPUT = RUN / "final_report_20261005/evidence.json"
SEEDS = (11, 29, 47)
ARMS = ("static", "manual_plus", "manual_minus", "c_only", "full")
LABELS = dict(zip(ARMS, ("Static", "Manual+", "Manual-", "C-only", "Full"), strict=True))
CONDITIONS = {"C_direction": ("Static", "positive", "reverse"), "N_same_point": ("C-only", "Full")}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def extract():
    sources = {}

    def read(path, expected_sha=None):
        path = Path(path).resolve()
        relative = str(path.relative_to(REPO))
        raw = path.read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        require(expected_sha is None or sha == expected_sha, "source binding changed: " + relative)
        data = json.loads(raw)
        require("id" in data, "bound source required: " + relative)
        body = {k: v for k, v in data.items() if k != "id"}
        require(
            hashlib.sha256(canonical(body)).hexdigest() == data["id"],
            "source content ID changed: " + relative,
        )
        sources[relative] = {"id": data["id"], "sha256": sha, "bytes": len(raw)}
        return data

    def outcomes(rows):
        values = [
            [r["native"]["native"][metric] for r in rows]
            for metric in ("execution_accuracy", "program_accuracy")
        ]
        require(
            all(x in (0, 1) for v in values for x in v),
            "unknown/nonbinary metric in completed scores",
        )
        return values

    def codes(values):
        return "".join(str(int(e) + 2 * int(p)) for e, p in zip(*values, strict=True))

    completion = read(RUN / "evaluation_continuation_01/queue/result/record.json")
    paired = read(RUN / "final_evaluation/paired_summary/record.json")
    mechanism = read(RUN / "mechanisms/evaluation_result/record.json")
    registration = read(RUN / "mechanisms/registration/record.json")
    require(
        completion["final_evaluation_id"] == paired["id"]
        and completion["mechanism_report_id"] == mechanism["id"],
        "final completion links changed",
    )
    require(
        not completion["test1147_opened"] and not completion["Experiment5_started"], "scope changed"
    )
    require(
        paired["distinct_question_count"] == 883
        and paired["total_repeated_model_episodes"] == 13245,
        "dev denominator changed",
    )
    require(
        mechanism["denominator"] == 5400 and mechanism["registration_id"] == registration["id"],
        "mechanism denominator/registration changed",
    )
    require(
        paired["statistics_contract"]["confidence_intervals"] is None
        and paired["statistics_contract"]["p_values"] is None,
        "unregistered inference",
    )

    base_ref = paired["Base_score_report"]
    base = read(base_ref["path"], base_ref["sha256"])
    require(base["id"] == paired["Base_score_id"], "Base identity changed")
    models, dev_roster, values_by_model = {}, None, {}
    for seed in SEEDS:
        for arm in ARMS:
            key = f"seed{seed}/{arm}"
            ref = paired["report_bindings"][key]
            score = read(ref["path"], ref["sha256"])
            require(
                score["seed"] == seed
                and score["arm"] == LABELS[arm]
                and score["denominator"] == 883,
                "model coordinate changed",
            )
            rows = score["results"]
            roster = [r["task_key"] for r in rows]
            require(len(roster) == len(set(roster)) == 883, "dev roster incomplete/duplicated")
            if dev_roster is None:
                dev_roster = roster
            require(roster == dev_roster, "dev pair alignment changed")
            vals = outcomes(rows)
            for metric, vector in zip(
                ("execution_accuracy", "program_accuracy"), vals, strict=True
            ):
                m = score["metrics"][metric]
                require(m["unknown"] == 0 and m["correct"] == sum(vector), "score total mismatch")
                require(
                    math.isclose(m["complete_dataset_mean"], sum(vector) / 883),
                    "score mean mismatch",
                )
            values_by_model[(seed, LABELS[arm])] = vals
            models[key] = {
                "score_id": score["id"],
                "metrics": score["metrics"],
                "outcome_codes": codes(vals),
                "native_status_counts": dict(Counter(r["native"]["status"] for r in rows)),
                "native_reason_counts": dict(
                    Counter(r["native"].get("reason", "scored") for r in rows)
                ),
                "stop_reason_counts": dict(Counter(r["stop_reason"] for r in rows)),
                "actual_model_calls": sum(r["actual_model_calls"] for r in rows),
            }
    comparisons = {}
    for metric_index, (metric, groups) in enumerate(paired["comparisons"].items()):
        require(
            metric == ("execution_accuracy", "program_accuracy")[metric_index],
            "metric order changed",
        )
        comparisons[metric] = {}
        for name, item in groups.items():
            left, right = {
                "Full-Static": ("Full", "Static"),
                "Full-C-only": ("Full", "C-only"),
                "Manual+-Static": ("Manual+", "Static"),
                "Manual--Static": ("Manual-", "Static"),
            }[name]
            deltas = []
            for seed in SEEDS:
                a, b = (
                    values_by_model[(seed, left)][metric_index],
                    values_by_model[(seed, right)][metric_index],
                )
                delta = [(x - y) for x, y in zip(a, b, strict=True)]
                expected = item["paired_by_seed"][str(seed)]
                require(
                    expected["wins"] == sum(x > 0 for x in delta)
                    and expected["losses"] == sum(x < 0 for x in delta),
                    "paired wins/losses changed",
                )
                deltas.append(statistics.mean(delta))
            require(
                math.isclose(statistics.mean(deltas), item["mean_difference"], abs_tol=1e-12),
                "paired mean changed",
            )
            comparisons[metric][name] = {
                k: v
                for k, v in item.items()
                if k not in ("per_question_mean_difference", "source_cluster_summaries")
            }
    arm_summary = {}
    for arm in ARMS:
        arm_summary[LABELS[arm]] = {
            metric: {"mean": statistics.mean(v), "sample_sd": statistics.stdev(v), "seed_values": v}
            for metric in ("execution_accuracy", "program_accuracy")
            for v in [
                [
                    models[f"seed{s}/{arm}"]["metrics"][metric]["complete_dataset_mean"]
                    for s in SEEDS
                ]
            ]
        }

    points, builds = {}, {}
    task_ids = registration["calibration_task_ids"]
    require(len(task_ids) == len(set(task_ids)) == 120, "calibration roster changed")
    for seed in SEEDS:
        builds[str(seed)] = {}
        for mech, conditions in CONDITIONS.items():
            build = read(RUN / f"mechanisms/seed{seed}/{mech}/result/record.json")
            builds[str(seed)][mech] = {
                k: build[k]
                for k in (
                    "id",
                    "start_step",
                    "end_step",
                    "actual_extra_training_steps",
                    "API_calls",
                    "new_feedback_sessions",
                )
            }
            if mech == "C_direction":
                builds[str(seed)][mech].update(
                    {k: build[k]["mu_weighted"] for k in ("positive_change", "reverse_change")}
                )
            else:
                builds[str(seed)][mech].update(
                    N_activated=build["N_activated"],
                    same_point_check=build["same_point_check"],
                    distribution_change=build["arithmetic"]["difference"]["mu_weighted"],
                )
            for condition in conditions:
                key = f"seed{seed}/{mech}/{condition}"
                point = read(
                    RUN / f"mechanisms/seed{seed}/evaluation/{mech}/{condition}/scores/record.json"
                )
                require(
                    point["denominator"] == 360
                    and point["unknown"] == 0
                    and point["registration_id"] == registration["id"],
                    "incomplete mechanism score",
                )
                require(
                    point["seed"] == seed
                    and point["mechanism"] == mech
                    and point["condition"] == condition,
                    "mechanism coordinate changed",
                )
                lookup = {(row["draw"], row["task_id"]): row for row in point["rows"]}
                require(len(lookup) == len(point["rows"]) == 360, "duplicate mechanism coordinate")
                draws = {}
                total = 0
                for draw in range(3):
                    vals = outcomes([lookup[(draw, task_id)] for task_id in task_ids])
                    total += sum(vals[0])
                    draws[str(draw)] = {
                        "denominator": 120,
                        "correct": int(sum(vals[0])),
                        "mean": sum(vals[0]) / 120,
                        "outcome_codes": codes(vals),
                    }
                require(math.isclose(total / 360, point["mean"]), "mechanism mean mismatch")
                expected = (
                    mechanism["seeds"][str(seed)]["C"]["means"][condition]
                    if mech == "C_direction"
                    else mechanism["seeds"][str(seed)]["N_means"][condition]
                )
                require(math.isclose(expected, point["mean"]), "mechanism aggregate mismatch")
                points[key] = {
                    "score_id": point["id"],
                    "seal_id": point["seal_id"],
                    "denominator": 360,
                    "correct": int(total),
                    "mean": point["mean"],
                    "draws": draws,
                }
    return {
        "schema": "finqa_v18_completed_report_evidence.v1",
        "completion": completion,
        "report_scope": (
            "Completed fixed V18 five-arm experiment and V22 evaluation continuation; "
            "descriptive analysis only"
        ),
        "source_manifest": sources,
        "checks": {
            "source_content_ids_and_final_dev_report_hash_bindings": True,
            "dev_rosters_counts_binary_scores_and_paired_effects": True,
            "mechanism_rosters_counts_draws_and_aggregate": True,
            "tensor_or_episode_reaudit_performed": False,
            "private_references_read": False,
            "new_API_or_GPU_calls": 0,
        },
        "statistics_contract": paired["statistics_contract"],
        "outcome_code_definition": (
            "Character per roster position: execution_correct + 2 * program_correct; "
            "integers 0..3. Not raw predictions."
        ),
        "Base_metrics": base["metrics"],
        "Base_rerun": False,
        "dev_task_keys": dev_roster,
        "dev_source_group_count": paired["source_group_count"],
        "models": models,
        "arm_summary": arm_summary,
        "comparisons": comparisons,
        "Static_minus_Base_ordinary_learning": paired["Static_minus_Base_ordinary_learning"],
        "mechanism_registered_aggregate": mechanism,
        "mechanism_builds": builds,
        "calibration_task_ids": task_ids,
        "mechanism_points": points,
        "draw_split_scope": (
            "Post-hoc descriptive decomposition only; draw0 stochastic seed11, "
            "draw1 stochastic seed29, draw2 greedy; original mixed360 estimand unchanged."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify the existing report evidence against original records without writing.",
    )
    args = parser.parse_args()
    evidence = extract()
    raw = json.dumps(evidence, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.check:
        require(OUTPUT.read_text() == raw, "report evidence differs from current bound sources")
    else:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        with OUTPUT.open("x") as stream:
            stream.write(raw)
    print(
        json.dumps(
            {
                "path": str(OUTPUT),
                "source_count": len(evidence["source_manifest"]),
                "models": len(evidence["models"]),
                "mechanism_points": len(evidence["mechanism_points"]),
                "mode": "checked" if args.check else "created",
            }
        )
    )


if __name__ == "__main__":
    main()
