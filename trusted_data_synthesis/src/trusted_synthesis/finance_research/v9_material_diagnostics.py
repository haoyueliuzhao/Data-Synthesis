"""Zero-model read-only diagnostics of the fixed material and finite task schedule."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from fractions import Fraction
from pathlib import Path

from .contracts import digest
from .v8_training_driver import _publish, _require
from .v9_conditional_training import build_task_schedule, load_training_pool


def schedule_exposure(task_ids, seed):
    schedule = build_task_schedule(task_ids, seed)
    exposure = {t: Fraction(0) for t in task_ids}
    tails, visits = Counter(), Counter()
    for batch in schedule["batches"]:
        size = len(batch["task_ids"])
        for task in batch["task_ids"]:
            exposure[task] += Fraction(1, size)
            tails[task] += size < 5
            visits[task] += 1
    steps, N = len(schedule["batches"]), len(task_ids)
    _require(
        set(visits.values()) == {10} and sum(exposure.values()) == steps,
        "frozen ten-epoch exposure conservation failed",
    )
    return dict(
        seed=seed,
        schedule_sha256=schedule["schedule_sha256"],
        updates=steps,
        per_task={
            t: dict(
                visits=visits[t],
                tail_batch_visits=tails[t],
                c_x=str(exposure[t]),
                normalized_step_weight=str(exposure[t] / steps),
            )
            for t in task_ids
        },
        sum_c_x=str(sum(exposure.values())),
        min_c_x=str(min(exposure.values())),
        max_c_x=str(max(exposure.values())),
        expected_c_x_under_uniform_permutation=str(Fraction(steps, N)),
        exact_equal_finite_exposure=len(set(exposure.values())) == 1,
        finite_exposure_is_not_an_Adam_equivalence=True,
    )


def manual_dose(prior, chi, mu):
    _require(set(prior) == set(chi) == set(mu), "unchanged task domain required")
    tasks, total_plus, total_minus = {}, Fraction(0), Fraction(0)
    for task, row in prior.items():
        r = {z: Fraction(str(p)) for z, p in row.items()}
        _require(
            set(r) == set(chi[task])
            and sum(r.values()) == 1
            and all(type(v) is int and v in (0, 1) for v in chi[task].values()),
            "registered positive prior and binary chi required",
        )
        p = sum((v for z, v in r.items() if chi[task][z] == 1), Fraction(0))
        plus, minus = 2 * p / (1 + p), p / (2 - p)
        tv_plus, tv_minus = p * (1 - p) / (1 + p), p * (1 - p) / (2 - p)
        qplus = {z: v * (2 if chi[task][z] else 1) / (1 + p) for z, v in r.items()}
        qminus = {z: v * (1 if chi[task][z] else 2) / (2 - p) for z, v in r.items()}
        _require(
            sum(abs(qplus[z] - r[z]) for z in r) / 2 == tv_plus
            and sum(abs(qminus[z] - r[z]) for z in r) / 2 == tv_minus,
            "Manual TV identity failed",
        )
        tasks[task] = dict(
            p=str(p),
            p_plus=str(plus),
            p_minus=str(minus),
            TV_plus=str(tv_plus),
            TV_minus=str(tv_minus),
            q_plus={z: str(v) for z, v in qplus.items()},
            q_minus={z: str(v) for z, v in qminus.items()},
        )
        total_plus += Fraction(str(mu[task])) * tv_plus
        total_minus += Fraction(str(mu[task])) * tv_minus
    return dict(
        per_task=tasks,
        mu_weighted_TV_plus=str(total_plus),
        mu_weighted_TV_minus=str(total_minus),
        alpha=2,
        Manual_minus_is_equal_TV_C_reverse=False,
    )


def _summary(values):
    return dict(
        count=len(values),
        total=sum(values),
        minimum=min(values) if values else None,
        maximum=max(values) if values else None,
        mean=str(Fraction(sum(values), len(values))) if values else None,
    )


def diagnose_pool(pool, lineage_by_task):
    """Use verified complete rows, including zero-target context; never shorten material."""
    _require(set(pool.task_ids) <= set(lineage_by_task), "all training source lineages required")
    schedules = {str(seed): schedule_exposure(pool.task_ids, seed) for seed in (11, 29, 47)}
    across = {}
    for task in pool.task_ids:
        values = [Fraction(s["per_task"][task]["c_x"]) for s in schedules.values()]
        across[task] = dict(
            c_x_range=str(max(values) - min(values)),
            tail_visits_by_seed={
                seed: row["per_task"][task]["tail_batch_visits"] for seed, row in schedules.items()
            },
        )
    groups, levels, lengths, targets, packages, token_layers = (
        Counter(),
        Counter(),
        [],
        [],
        [],
        Counter(),
    )
    per_task = {}
    for task in pool.task_ids:
        lineage = lineage_by_task[task]
        lineage = lineage.model_dump(mode="json") if hasattr(lineage, "model_dump") else lineage
        groups[lineage["source_group"]] += 1
        levels[lineage["source_group_level"]] += 1
        rows = [
            row
            for package in pool.packages
            if package["task_id"] == task
            for row in pool._rows[package["package_id"]]
        ]
        per_task[task] = dict(
            source_group=lineage["source_group"],
            source_group_level=lineage["source_group_level"],
            company=lineage.get("company"),
            report=lineage.get("report"),
            year=lineage.get("year"),
            lineage_sha256=digest(lineage),
            complete_sequence_lengths=[len(row["input_ids"]) for row in rows],
            supervised_tokens=sum(len(row["target_ids"]) for row in rows),
        )
        for row in rows:
            lengths.append(len(row["input_ids"]))
            targets.append(len(row["target_ids"]))
            for layer, positions in row["layer_target_positions"].items():
                token_layers[layer] += len(positions)
    packages = [p["whole_package_target_tokens"] for p in pool.packages]
    prior = pool._manifest.registration
    body = dict(
        schema="v9_frozen_material_zero_model_diagnostics.v1",
        pool_id=pool.cache_id,
        N=len(pool.task_ids),
        package_count=len(pool.packages),
        schedule_exposure=schedules,
        across_seed_exposure=across,
        manual_dose=manual_dose(prior.pi0, pool.chi, prior.mu),
        source_groups=dict(groups),
        source_group_levels=dict(levels),
        per_task=per_task,
        complete_response_row_sequence_tokens=_summary(lengths),
        supervised_tokens_per_row=_summary(targets),
        whole_package_supervised_tokens=_summary(packages),
        supervised_token_layers=dict(token_layers),
        reason_layer="R+U",
        separate_R_U_claimed=False,
        no_task_package_or_weight_changes=True,
        model_calls=0,
        Student_results_used=False,
        production_material=pool.production_verified,
        interpretation=(
            "Uniform mu defines full-population G. Actual Adam uses fixed shuffled batches; "
            "ten visits do not imply equal finite c_x or an equivalent population update."
        ),
    )
    return body | dict(id=digest(body))


def run(binding_path, output):
    from .storage import load_public_snapshot

    binding_path = Path(binding_path).resolve()
    pool = load_training_pool(binding_path)
    binding = json.loads(binding_path.read_bytes())
    parent = Path(binding["generation_protocol"]["path"])
    if not parent.is_absolute():
        parent = binding_path.parent / parent
    generation = json.loads(parent.read_bytes())  # Already byte-bound by strict loader.
    _, tasks, lineages = load_public_snapshot(generation["snapshot"])
    report = diagnose_pool(
        pool, {t.task_id: lineage for t, lineage in zip(tasks, lineages, strict=True)}
    )
    _publish(output, report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binding", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(run(args.binding, args.output), ensure_ascii=False))


if __name__ == "__main__":
    main()
