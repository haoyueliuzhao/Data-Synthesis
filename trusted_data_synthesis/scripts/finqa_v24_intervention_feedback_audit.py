#!/usr/bin/env python3
"""Read-only V18 intervention-dose and feedback-signal audit; no model imports.

Only original support, outer JSON, sealed feedback and original same-point N
JSON records are read. Public grouping is frozen by the companion audit first.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from fractions import Fraction
from pathlib import Path

SEEDS = (11, 29, 47)
STEPS = (298, 596, 894, 1192)
FIELDS = ("company", "report_group", "year", "intent_proxy", "input_size_bin", "question_size_bin")
TOL = 1e-12  # Conditional row TV, not task-weighted TV.
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = (
    ROOT
    / "trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01"
    / "v18_researcher_continuation_01"
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def number(value):
    require(not isinstance(value, bool), "boolean is not a probability")
    result = float(Fraction(value)) if isinstance(value, str) else float(value)
    require(math.isfinite(result), "nonfinite numeric input")
    return result


def read_record(path, sources, expected_sha=None):
    path = Path(path)
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    require(
        expected_sha is None or sha == expected_sha, "registered source SHA mismatch: " + str(path)
    )
    value = json.loads(raw)
    sources[str(path)] = {"path": str(path), "sha256": sha, "bytes": len(raw)}
    if isinstance(value, dict) and "id" in value:
        sources[str(path)]["id"] = value["id"]
    return value


def canonical(task):
    return task if task.startswith("finqa/") else "finqa/" + task


def normalized_concentration(weights):
    total = math.fsum(weights.values())
    values = sorted((value / total for value in weights.values()), reverse=True) if total else []
    top = sorted(weights.items(), key=lambda x: (-x[1], x[0]))[:10]
    hhi = math.fsum(p * p for p in values)
    return {
        "total": total,
        "nonzero_groups": sum(v > 0 for v in weights.values()),
        "HHI": hhi if total else None,
        "effective_number_inverse_HHI": 1 / hhi if hhi else None,
        **{f"top{k}_share": math.fsum(values[:k]) if total else None for k in (1, 5, 10)},
        "top10": [
            {"group": key, "mass": value, "share": value / total if total else None}
            for key, value in top
        ],
        "mass": dict(sorted(weights.items())),
    }


def grouped_mass(weights, features):
    result = {"task": normalized_concentration(weights)}
    for field in FIELDS:
        groups = defaultdict(float)
        for task, weight in weights.items():
            key = canonical(task)
            require(
                key in features and field in features[key], "missing frozen public feature: " + key
            )
            groups[str(features[key][field])] += weight
        result[field] = normalized_concentration(groups)
    return result


def validate_distribution(q, support):
    require(set(q) == set(support), "distribution task support differs")
    for task, row in q.items():
        require(set(row) == set(support[task]["states"]), "distribution state support differs")
        require(all(number(v) > 0 for v in row.values()), "nonpositive probability")
        require(abs(math.fsum(map(number, row.values())) - 1) < 1e-10, "non-simplex distribution")


def prior_from_support(support):
    prior = {}
    for task, value in support.items():
        counts = value["states"]
        require(sum(counts.values()) == value["n_x"], "package multiplicity differs")
        require(set(counts) == set(value["chi"]), "chi/state support differs")
        require(all(type(n) is int and n > 0 for n in counts.values()), "invalid package count")
        prior[task] = {z: str(Fraction(n, value["n_x"])) for z, n in counts.items()}
    return prior


def manual_distribution(prior, support, sign):
    result = {}
    for task, row in prior.items():
        chi = support[task]["chi"]
        if len(set(chi.values())) == 1:
            result[task] = dict(row)
        else:
            require(set(chi.values()) == {0, 1}, "manual contrast requires binary chi")
            values = {z: number(p) * 2 ** (sign * chi[z]) for z, p in row.items()}
            total = math.fsum(values.values())
            result[task] = {z: p / total for z, p in values.items()}
    return result


def task_dose(before, after, mu, support, features, tolerance=TOL):
    validate_distribution(before, support)
    validate_distribution(after, support)
    tv = {
        task: 0.5
        * math.fsum(abs(number(after[task][z]) - number(before[task][z])) for z in before[task])
        for task in before
    }
    weights = {task: number(mu[task]) * value for task, value in tv.items()}
    moved = sorted(task for task, value in tv.items() if value > tolerance)
    return {
        "weighted_TV": math.fsum(weights.values()),
        "effective_moved_tasks": len(moved),
        "effective_moved_task_ids": moved,
        "effective_moved_task_mass_mu": math.fsum(number(mu[t]) for t in moved),
        "effective_moved_definition": (
            f"conditional row TV > {tolerance:g}; no threshold on weighted dose"
        ),
        "task_TV": tv,
        "task_dose": weights,
        "grouped_dose": grouped_mass(weights, features),
    }


def empirical_mass(q, support, mu, features):
    """Each of n_xz packages has weight mu*pi/n_xz; sum is exactly mu."""
    validate_distribution(q, support)
    task_mass, chi_mass = {}, {"0": 0.0, "1": 0.0, "null_registered_singleton": 0.0}
    package_weight_range = []
    chi_by_group = {field: defaultdict(lambda: defaultdict(float)) for field in FIELDS}
    for task, row in q.items():
        mass = []
        for z, p in row.items():
            n = support[task]["states"][z]
            package_weight = number(mu[task]) * number(p) / n
            mass.append(n * package_weight)
            package_weight_range.append(package_weight)
            chi = support[task]["chi"][z]
            require(chi is None or (type(chi) is int and chi in (0, 1)), "invalid frozen chi")
            if chi is None:
                require(len(row) == 1, "null chi outside registered singleton")
            label = "null_registered_singleton" if chi is None else str(chi)
            chi_mass[label] += n * package_weight
            for field in FIELDS:
                chi_by_group[field][str(features[canonical(task)][field])][label] += (
                    n * package_weight
                )
        task_mass[task] = math.fsum(mass)
    error = max(abs(task_mass[t] - number(mu[t])) for t in mu)
    require(error < 1e-12, "task empirical mass differs from registered mu")
    return {
        "total_mass": math.fsum(task_mass.values()),
        "max_abs_task_mass_minus_mu": error,
        "task_attribute_group_mass_equals_mu": True,
        "chi_supervision_mass": chi_mass,
        "package_weight_min": min(package_weight_range),
        "package_weight_max": max(package_weight_range),
        "chi_supervision_mass_by_public_group": {
            field: {group: dict(values) for group, values in sorted(groups.items())}
            for field, groups in chi_by_group.items()
        },
    }


def feedback_join(draws, rewards, intent, evidence, expected_tasks, expected_seeds=(11, 29)):
    """Join compact sealed-run task/seed/point rosters to original scores.

    Does not reload full trajectories or recompute their individual file hashes.
    Original producer concatenates draw0 then draw1 in sealed episode-key order.
    """
    n = len(expected_tasks) * len(expected_seeds)
    require(
        rewards["cohort_seal_sha256"]
        == evidence["feedback_seal_sha256"]
        == evidence["feedback_report"]["cohort_seal_sha256"],
        "feedback seal binding mismatch",
    )
    require(
        n == intent["denominator"] == evidence["actual_feedback_denominator"],
        "incomplete feedback cohort",
    )
    require(
        intent["source_manifest_sha256"] == evidence["feedback_report"]["source_manifest_sha256"],
        "feedback source manifest mismatch",
    )
    require(
        set(map(canonical, intent["task_ids"])) == set(map(canonical, expected_tasks))
        and set(intent["seeds"]) == set(expected_seeds),
        "feedback intent roster mismatch",
    )
    require(len(rewards["rewards"]) == len(rewards["scores"]) == n, "feedback lengths differ")
    require(
        digest(rewards["rewards"]) == evidence["feedback_report"]["reward_sha256"],
        "reward vector digest mismatch",
    )
    roster = []
    require(len(draws) == len(expected_seeds), "draw count mismatch")
    for (run, seal), expected_seed in zip(draws, expected_seeds, strict=True):
        require(
            digest({k: v for k, v in run.items() if k != "id"}) == run["id"],
            "run content identity mismatch",
        )
        require(
            digest({k: v for k, v in seal.items() if k != "id"}) == seal["id"],
            "generation seal identity mismatch",
        )
        require(
            seal["run_id"] == run["id"]
            and seal["complete"] is True
            and seal["all_provider_calls_settled"] is True,
            "generation not completely sealed",
        )
        require(
            run["provider"] == intent["identity"] and run["config"]["seed"] == expected_seed,
            "draw point/seed identity mismatch",
        )
        require(
            run["source_manifest_sha256"] == intent["source_manifest_sha256"],
            "draw source manifest mismatch",
        )
        require(run["role"] == run["config"]["role"] == "feedback", "wrong feedback role")
        require(
            run["registered_denominator"] == seal["registered_denominator"] == len(expected_tasks)
            and len(run["tasks"]) == len(expected_tasks)
            and set(run["tasks"]) == set(map(canonical, expected_tasks)),
            "draw task roster mismatch",
        )
        keys = [
            digest(
                {
                    "dataset": "finqa",
                    "task_id": task.removeprefix("finqa/"),
                    "seed": expected_seed,
                    "point_id": run["provider"]["point_id"],
                }
            )
            for task in run["tasks"]
        ]
        require(
            keys == run["episode_keys"] == [x["key"] for x in seal["episodes"]],
            "episode task/seed key order mismatch",
        )
        require(len(set(keys)) == len(expected_tasks), "duplicate registered episode key")
        roster.extend((task, expected_seed) for task in run["tasks"])
    result = {}
    for (task, seed), reward, score in zip(
        roster, rewards["rewards"], rewards["scores"], strict=True
    ):
        require(canonical(score["task_id"]) == task, "native reward task order mismatch")
        require(type(reward) in (int, float) and reward in (0, 1), "nonbinary native reward")
        require(
            number(score["native"]["execution_accuracy"]) == reward, "native score/reward mismatch"
        )
        require((canonical(task), seed) not in result, "duplicate task/seed feedback")
        result[canonical(task), seed] = int(reward)
    require(
        set(result) == {(canonical(t), s) for t in expected_tasks for s in expected_seeds},
        "feedback task/seed cohort differs",
    )
    # No regenerated scoring or replay, and no answer/private-reference access.
    return result


def pair_overlap(joined, seeds=(11, 29)):
    success = [
        {task for (task, seed), reward in joined.items() if seed == s and reward} for s in seeds
    ]
    tasks = {t for t, _ in joined}
    both, either = success[0] & success[1], success[0] | success[1]
    return {
        "task_denominator": len(tasks),
        "repeat_seeds": list(seeds),
        "success_counts": [len(x) for x in success],
        "both": len(both),
        "either": len(either),
        "neither": len(tasks - either),
        "exactly_one": len(either - both),
        "Jaccard": len(both) / len(either) if either else None,
        "both_task_keys": sorted(both),
        "either_task_keys": sorted(either),
    }


def feedback_worker(args):
    root, item, expected_tasks = args
    sources = {}
    outer = read_record(Path(root) / item["outer_source"], sources)
    require(
        (outer["arm"], outer["seed"], outer["step"]) == (item["arm"], item["seed"], item["step"]),
        "outer provenance identity mismatch",
    )
    reward_path = Path(root) / item["native_rewards_source"]
    feedback_root = reward_path.parent.parent
    reward = read_record(reward_path, sources)
    intent = read_record(feedback_root / "intent/record.json", sources)
    draws = [
        (
            read_record(feedback_root / f"draw{i}/run.json", sources),
            read_record(feedback_root / f"draw{i}/generation_seal/seal.json", sources),
        )
        for i in range(2)
    ]
    joined = feedback_join(draws, reward, intent, outer["evidence"], expected_tasks)
    require(
        reward["cohort_seal_sha256"] == item["cohort_seal_sha256"],
        "runtime evidence feedback seal differs",
    )
    return {
        "arm": item["arm"],
        "seed": item["seed"],
        "step": item["step"],
        "seal_sha256": reward["cohort_seal_sha256"],
        "denominator": len(joined),
        "point_id": intent["identity"]["point_id"],
        "source_manifest_sha256": intent["source_manifest_sha256"],
        "positive_rewards": sum(joined.values()),
        "pair_overlap": pair_overlap(joined),
        "task_positive_counts": {
            t: sum(joined[t, s] for s in (11, 29)) for t in sorted(expected_tasks)
        },
        "status_counts": dict(Counter(s["status"] for s in reward["scores"])),
        "sources": sources,
    }


def feedback_summary(rows, task_keys, features):
    exposures = {t: len(rows) * 2 for t in task_keys}
    positive = {t: sum(r["task_positive_counts"][t] for r in rows) for t in task_keys}
    groups = grouped_mass(positive, features)
    family = {}
    for field in FIELDS:
        denoms, nums, counts = Counter(), Counter(), Counter()
        for task in task_keys:
            group = str(features[task][field])
            counts[group] += 1
            denoms[group] += exposures[task]
            nums[group] += positive[task]
        family[field] = {
            g: {
                "tasks": counts[g],
                "exposures": denoms[g],
                "positive_rewards": nums[g],
                "success_rate": nums[g] / denoms[g],
                "positive_count_share": nums[g] / sum(positive.values())
                if sum(positive.values())
                else None,
            }
            for g in sorted(counts)
        }
    return {
        "outer_count": len(rows),
        "tasks": len(task_keys),
        "reward_denominator": sum(exposures.values()),
        "positive_rewards": sum(positive.values()),
        "zero_rewards": sum(exposures.values()) - sum(positive.values()),
        "positive_frequency_histogram": dict(sorted(Counter(positive.values()).items())),
        "never_positive_tasks": sum(v == 0 for v in positive.values()),
        "always_positive_tasks": sum(positive[t] == exposures[t] for t in task_keys),
        "task_exposure_count": exposures,
        "task_positive_counts": positive,
        "positive_count_mass": groups,
        "family_success_rates": family,
        "interpretation": (
            "Positive-reward count mass, not gradient magnitude or causal contribution; "
            "all exposures retained."
        ),
    }


def audit(source_root, public_path, protocol_path, workers=3):
    sources = {}
    public = read_record(public_path, sources)
    protocol = read_record(protocol_path, sources)
    require(public["protocol_id"] == protocol["id"], "frozen public grouping protocol mismatch")
    features = public["features"]
    runtime = read_record(
        source_root / "final_report_20261005/runtime_training_evidence.json", sources
    )
    registration = read_record(
        source_root / "training/five_arm_training/registration/record.json", sources
    )
    binding = read_record(
        registration["material_binding"]["path"],
        sources,
        registration["material_binding"]["sha256"],
    )
    support_record = read_record(
        binding["support_manifest"]["path"], sources, binding["support_manifest"]["sha256"]
    )
    support, mu = support_record["task_support"], support_record["mu"]
    require(
        len(support) == 744 and set(support) == set(mu) == set(support_record["training_task_ids"]),
        "V18 support changed",
    )
    require(all(Fraction(v) == Fraction(1, 744) for v in mu.values()), "V18 task mu changed")
    prior = prior_from_support(support)
    train_ids = set(map(canonical, support))
    require(train_ids <= set(features), "training public features incomplete")
    feedback_sets = [
        set(v)
        for k, v in public["populations"].items()
        if "feedback" in k.lower() and len(v) == 350
    ]
    require(
        len(feedback_sets) >= 1 and all(x == feedback_sets[0] for x in feedback_sets),
        "fixed feedback350 roster missing/ambiguous",
    )
    feedback_tasks = sorted(feedback_sets[0])
    static_mass = empirical_mass(prior, support, mu, features)
    manual = {}
    for arm, sign in (("Manual+", 1), ("Manual-", -1)):
        q = manual_distribution(prior, support, sign)
        manual[arm] = {
            "dose_from_prior": task_dose(prior, q, mu, support, features),
            "empirical_mass": empirical_mass(q, support, mu, features),
        }
    items = runtime["outer_diagnostics"]
    expected = {(a, s, step) for a in ("C-only", "Full") for s in SEEDS for step in STEPS}
    require(
        len(items) == 24 and {(i["arm"], i["seed"], i["step"]) for i in items} == expected,
        "original 24 outer cohort incomplete",
    )
    outer_rows, aggregate = [], defaultdict(lambda: defaultdict(float))
    for arm in ("C-only", "Full"):
        for seed in SEEDS:
            before = prior
            for item in sorted(
                (i for i in items if i["arm"] == arm and i["seed"] == seed), key=lambda i: i["step"]
            ):
                record = read_record(source_root / item["outer_source"], sources)
                require(
                    (record["arm"], record["seed"], record["step"]) == (arm, seed, item["step"]),
                    "outer identity mismatch",
                )
                require(
                    record["actual_state_digest"] == item["outer_state_digest"],
                    "outer state digest mismatch",
                )
                evidence = record["evidence"]
                distribution = evidence["distribution"]
                require(
                    distribution["id"] == item["distribution_update_id"], "distribution id mismatch"
                )
                after = distribution["pi_next"]
                dose = task_dose(before, after, mu, support, features)
                require(
                    abs(dose["weighted_TV"] - distribution["weighted_TV"]) < 1e-12,
                    "saved weighted TV mismatch",
                )
                c_active = sorted(
                    t
                    for t, row in evidence["C"].items()
                    if any(abs(number(x)) > TOL for x in row.values())
                )
                require(set(evidence["C"]) == set(support), "C support mismatch")
                controls = distribution["control_tasks"]
                require(
                    all(
                        all(number(after[t][z]) == number(before[t][z]) for z in before[t])
                        for t in controls
                    ),
                    "saved control changed",
                )
                row = {
                    "arm": arm,
                    "seed": seed,
                    "step": item["step"],
                    "source": item["outer_source"],
                    "distribution_update_id": distribution["id"],
                    "state_digest": record["actual_state_digest"],
                    "dose_from_previous_outer_or_prior": dose,
                    "net_dose_from_prior": task_dose(prior, after, mu, support, features),
                    "empirical_mass": empirical_mass(after, support, mu, features),
                    "nonzero_C_task_count": len(c_active),
                    "nonzero_C_task_ids": c_active,
                    "C_nonzero_definition": f"any |C_xz| > {TOL:g}",
                    "control_task_count": len(controls),
                    "controls_preserved_verified": True,
                    "declared_controls_exactly_preserved": distribution[
                        "controls_exactly_preserved"
                    ],
                }
                outer_rows.append(row)
                for t, value in dose["task_dose"].items():
                    aggregate[arm][t] += value
                    aggregate[f"{arm}:seed{seed}"][t] += value
                before = after
    n_rows = []
    for seed in SEEDS:
        cbuild = read_record(
            source_root / f"mechanisms/seed{seed}/C_direction/result/record.json", sources
        )
        nbuild = read_record(
            source_root / f"mechanisms/seed{seed}/N_same_point/result/record.json", sources
        )
        require(
            cbuild["prior"] == prior and cbuild["seed"] == nbuild["seed"] == seed,
            "same-point prior/seed differs",
        )
        require(
            nbuild["start_step"] == 596 and nbuild["end_step"] == 745, "same-point interval differs"
        )
        qc, qn = nbuild["arithmetic"]["C_only"], nbuild["arithmetic"]["Full"]
        original_c = next(
            i for i in items if i["arm"] == "C-only" and i["seed"] == seed and i["step"] == 596
        )
        c_outer = read_record(source_root / original_c["outer_source"], sources)
        require(
            qc == c_outer["evidence"]["distribution"]["pi_next"]
            and nbuild["source_outer"]["actual_state_digest"] == c_outer["actual_state_digest"],
            "same-point original C anchor differs",
        )
        n_rows.append(
            {
                "seed": seed,
                "N_effect_qN_minus_qC": task_dose(qc, qn, mu, support, features),
                "C_empirical_mass": empirical_mass(qc, support, mu, features),
                "N_empirical_mass": empirical_mass(qn, support, mu, features),
            }
        )
    jobs = [(str(source_root), item, feedback_tasks) for item in items]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        feedback_rows = list(pool.map(feedback_worker, jobs))
    for row in feedback_rows:
        sources.update(row.pop("sources"))
    feedback = feedback_summary(feedback_rows, feedback_tasks, features)
    require(
        feedback["reward_denominator"] == 16800 and feedback["positive_rewards"] == 6490,
        "original feedback totals differ",
    )
    feedback["by_arm"] = {
        a: feedback_summary([r for r in feedback_rows if r["arm"] == a], feedback_tasks, features)
        for a in ("C-only", "Full")
    }
    feedback["by_arm_seed"] = {
        f"{a}:seed{s}": feedback_summary(
            [r for r in feedback_rows if (r["arm"], r["seed"]) == (a, s)], feedback_tasks, features
        )
        for a in ("C-only", "Full")
        for s in SEEDS
    }
    feedback["outer_rows"] = feedback_rows
    support_summary = {
        "tasks": len(support),
        "packages": sum(s["n_x"] for s in support.values()),
        "singleton_state_tasks": sum(len(s["states"]) == 1 for s in support.values()),
        "multistate_tasks": sum(len(s["states"]) > 1 for s in support.values()),
        "manual_chi_flexible_tasks": sum(len(set(s["chi"].values())) > 1 for s in support.values()),
        "registered_null_chi_singletons": sum(
            set(s["chi"].values()) == {None} for s in support.values()
        ),
        "task_mu": "1/744",
        "task_mu_group_mass": grouped_mass({t: number(v) for t, v in mu.items()}, features),
        "state_count_histogram": dict(
            sorted(Counter(len(s["states"]) for s in support.values()).items())
        ),
        "package_count_histogram": dict(
            sorted(Counter(s["n_x"] for s in support.values()).items())
        ),
    }
    result = {
        "schema": "finqa_v24_intervention_feedback_audit.v1",
        "protocol_id": protocol["id"],
        "scope": (
            "Original completed V18 only; no V23 data, test outputs, tensors, "
            "private references, GPU, API, re-scoring, or mutation."
        ),
        "definitions": {
            "task_empirical_mass": "mu(x)=1/744",
            "package_empirical_mass": (
                "mu(x)*pi(z|x)/n_xz; n_xz packages in state z; normalized per-package target loss"
            ),
            "task_intervention_dose": "d_x=mu(x)*TV(pi_next(.|x),pi_before(.|x))",
            "group_invariance": (
                "For any task-level public group, summing package weights equals sum_x mu(x) "
                "independently of pi; package/token counts are not extra task training mass."
            ),
            "stepwise_sum_caveat": (
                "Sum of stepwise TVs across updates is cumulative path movement, "
                "not net TV, unique moved mass, or an independent sample size."
            ),
            "feedback_caveat": (
                "Positive reward counts identify nonzero score-function opportunities, "
                "not gradient norms; task repeated exposures are dependent."
            ),
            "chi_caveat": (
                "Chi is frozen process mapping, "
                "not independently established semantic quality or external accuracy."
            ),
        },
        "support": support_summary,
        "Static_empirical_mass": static_mass,
        "manual": manual,
        "outer_rows": outer_rows,
        "cumulative_stepwise_dose": {
            key: grouped_mass(dict(value), features) for key, value in aggregate.items()
        },
        "original_N_same_point_separate": n_rows,
        "feedback": feedback,
        "checks": {
            "all_task_attribute_empirical_mass_equal_mu": True,
            "all_original_24_outer_weighted_TV_recomputed": True,
            "all_feedback_cohort_seal_bindings_and_compact_draw_task_seed_keys_matched": True,
            "individual_feedback_trajectories_rehashed_or_replayed": False,
            "full_350_by_48_feedback_denominator_retained": True,
            "no_feedback_gradient_or_generation_replay": True,
        },
        "sources": list(sources.values()),
    }
    result["id"] = digest(result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--audit-root", type=Path)
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    audit_root = args.audit_root or args.source_root / "v24_data_distribution_audit_01"
    require(args.workers >= 1, "workers must be positive")
    result = audit(
        args.source_root,
        audit_root / "public_features.json",
        audit_root / "grouping_protocol.json",
        args.workers,
    )
    output = audit_root / "intervention_feedback.json"
    payload = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if output.exists():
        require(
            output.read_text() == payload,
            "existing immutable audit output differs; choose a new audit directory",
        )
    else:
        with output.open("x") as stream:
            stream.write(payload)
    print(
        json.dumps(
            {
                "output": str(output),
                "id": result["id"],
                "support": {
                    k: result["support"][k]
                    for k in (
                        "tasks",
                        "packages",
                        "singleton_state_tasks",
                        "multistate_tasks",
                        "manual_chi_flexible_tasks",
                    )
                },
                "feedback_rewards": result["feedback"]["reward_denominator"],
                "feedback_positives": result["feedback"]["positive_rewards"],
            }
        )
    )


if __name__ == "__main__":
    main()
