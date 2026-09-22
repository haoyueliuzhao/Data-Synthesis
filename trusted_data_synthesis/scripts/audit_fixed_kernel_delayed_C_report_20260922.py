"""Read-only metadata audit/export. Never load tensors, generate, score, or launch workers."""

import argparse
import hashlib
import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

BASE = Path("trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value")
A = BASE / "anchored_sources_20260916"
SEEDS = (11, 29, 47)
GROUPS = ("composition_required", "dual_sufficient", "other_financial")
RAW_DEFAULT = (
    Path("/data1/zhuxinrui/projects/Data-Synthesis") / BASE / "delayed_C_recovery_cache_20260921"
)


def require(value, message):
    if not value:
        raise ValueError("audit_report." + message)


def canonical(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


class Evidence:
    def __init__(self, root, raw):
        self.root, self.raw, self.rows, self.cache = root, raw, {}, {}

    def read(self, path, *, index=True):
        path = Path(path)
        if path in self.cache:
            return self.cache[path]
        payload = path.read_bytes()
        value = json.loads(payload)
        identity_checked = False
        if isinstance(value, dict) and "id" in value and "schema_version" in value:
            prefix = "fixed_kernel_value.v1."
            if value["schema_version"].startswith(prefix):
                kind = value["schema_version"][len(prefix) :]
                body = {key: item for key, item in value.items() if key != "id"}
                require(
                    value["id"] == kind + ":" + digest(canonical(body)),
                    "record_identity:" + str(path),
                )
                identity_checked = True
        label = (
            "ROOT/" + str(path.relative_to(self.root))
            if path.is_relative_to(self.root)
            else "RAW/" + str(path.relative_to(self.raw))
        )
        if index:
            self.rows[label] = dict(
                path=label,
                bytes=len(payload),
                sha256=digest(payload),
                record_id=value.get("id") if isinstance(value, dict) else None,
                content_id_checked=identity_checked,
            )
        self.cache[path] = value
        return value


def outcomes(rows, tasks, *, field="Q"):
    require(len(rows) == len(tasks) == 180, "fixed180")
    result = {}
    for row in rows:
        task = row["task_id"]
        require(task not in result and task in tasks, "unique_registered_task")
        require(
            row["group"] == tasks[task] and row[field] in (0, 1, False, True),
            "fixed_group_and_binary_score",
        )
        result[task] = int(row[field])
    require(set(result) == set(tasks), "complete_task_set")
    return result


def paired(left, right):
    require(set(left) == set(right), "paired_task_set")
    counts = Counter((left[task], right[task]) for task in left)
    return dict(
        static0_delayed1=counts[0, 1],
        static1_delayed0=counts[1, 0],
        both1=counts[1, 1],
        both0=counts[0, 0],
        net=sum(right.values()) - sum(left.values()),
        denominator=len(left),
    )


def audit(root, raw):
    e = Evidence(root, raw)
    original, recovery = root / A / "delayed_C_20260919", root / A / "delayed_C_recovery_20260921"
    control = raw / "aggressive_autorun_20260921"
    plan = e.read(original / "plan.json")
    recovery_plan = e.read(recovery / "plan.json")
    final = e.read(recovery / "report.json")
    require(final == e.read(control / "complete.json"), "published_and_persistent_completion_match")
    require(
        final["original_plan_id"] == plan["id"]
        and final["recovery_plan_id"] == recovery_plan["id"],
        "plan_lineage",
    )
    tasks = {row["task_id"]: row["group"] for row in plan["tasks"]}
    require(
        Counter(tasks.values()) == Counter({group: 60 for group in GROUPS}), "three_fixed_groups"
    )
    parent = e.read(root / A / "registered_A/plan.json")
    require(
        {row["task_id"]: row["group"] for row in parent["tasks"]} == tasks, "same_baseline_tasks"
    )
    require(
        not set(tasks).intersection(plan["training_groups"]),
        "distinct_SFT_and_development_task_IDs",
    )
    original_matrix = e.read(root / A / "registered_A/report.json")
    static = e.read(root / BASE / "given_sources_value_20260915/report.json")
    scores, score_ids = {}, {}
    for seed in SEEDS:
        model = next(row for row in static["models"] if row["model_key"] == f"A_alpha0_{seed}")
        scores["Static", seed] = outcomes(model["outcomes"], tasks, field="financial_valid")
        score_ids["Static", seed] = static["id"]
        for condition, key in (("C-only", "c_only"), ("Full", "full")):
            report = e.read(
                root
                / A
                / "registered_A/runs"
                / f"A_{key}_{seed}"
                / "final_greedy/scoring_report.json"
            )
            scores[condition, seed] = outcomes(report["scores"], tasks)
            require(
                report["complete"]
                and report["denominator"] == 180
                and report["qualified"] == sum(scores[condition, seed].values()),
                "baseline_score_total",
            )
            run_report = e.read(root / A / "registered_A/runs" / f"A_{key}_{seed}" / "report.json")
            matrix_row = next(
                row for row in original_matrix["runs"] if row["run"]["key"] == f"A_{key}_{seed}"
            )
            require(
                run_report["id"] == matrix_row["id"]
                and run_report["run"]["seed"] == seed
                and run_report["final_assessment_report_id"] == report["id"]
                and run_report["final_point_id"] == report["point_id"]
                and run_report["final_qualified"]
                == matrix_row["final_qualified"]
                == report["qualified"],
                "baseline_run_score_matrix_join",
            )
            score_ids[condition, seed] = report["id"]
    run_rows, generation_rows, guards, distributions = [], [], [], []
    for seed in SEEDS:
        key = f"A_delayed_c_{seed}"
        run_dir = (original if seed == 11 else recovery) / "runs" / key
        run_report = e.read(run_dir / "report.json")
        generated = e.read(run_dir / "final_greedy/generation_manifest.json")
        scored = e.read(run_dir / "final_greedy/scoring_report.json")
        score = outcomes(scored["scores"], tasks)
        scores["Delayed-C", seed] = score
        score_ids["Delayed-C", seed] = scored["id"]
        require(
            run_report["final_assessment_report_id"] == scored["id"]
            and scored["generation_manifest_id"] == generated["id"],
            "generation_score_run_chain",
        )
        require(
            run_report["final_point_id"] == scored["point_id"] == generated["point_id"],
            "sole_final_point",
        )
        require(
            scored["source_manifest_id"]
            == generated["source_manifest_id"]
            == plan["source_manifest_id"],
            "same_source_manifest",
        )
        require(
            scored["complete"]
            and generated["complete"]
            and not generated["stochastic"]
            and scored["denominator"] == 180
            and len(generated["trajectories"]) == 180,
            "complete_fixed_final",
        )
        require(
            sum(score.values()) == scored["qualified"] == run_report["final_qualified"],
            "run_score_sum",
        )
        require(
            scored["financial_rule_unchanged"]
            and scored["scoring_after_all_generation_complete"]
            and scored["confirm_tasks_opened"] == 0,
            "score_scope",
        )
        items = {row["job"]["index"]: row for row in generated["trajectories"]}
        require(set(items) == set(range(180)), "all_final_indices")
        for row in scored["scores"]:
            item = items[row["index"]]
            require(
                item["session_id"] == row["session_id"]
                and item["job"]["task"]["task_id"] == row["task_id"]
                and item["point_id"] == generated["point_id"],
                "sealed_session_join",
            )
        run_rows.append(
            dict(
                seed=seed,
                qualified=sum(score.values()),
                denominator=180,
                run_report_id=run_report["id"],
                point_id=generated["point_id"],
                generation_at=generated["at"],
                scoring_finished_at=scored["finished_at"],
                completed_at=run_report["at"],
            )
        )
        for phase_name, path in (
            ("final", run_dir / "final_greedy"),
            ("feedback", original / "runs" / key / "rounds/epoch5/feedback"),
        ):
            manifest = e.read(path / "generation_manifest.json")
            assessment = e.read(path / "scoring_report.json")
            require(
                assessment["generation_manifest_id"] == manifest["id"], "phase_manifest_score_join"
            )
            require(
                len(manifest["trajectories"]) == (180 if phase_name == "final" else 360),
                "phase_fixed_sessions",
            )
            require(
                manifest["total_generate_calls"]
                == sum(row["actual_generate_calls"] for row in manifest["trajectories"]),
                "generate_call_sum",
            )
            require(
                manifest["total_generated_tokens"]
                == sum(row["generated_tokens"] for row in manifest["trajectories"]),
                "generated_token_sum",
            )
            generation_rows.append(
                dict(
                    seed=seed,
                    phase=phase_name,
                    sessions=len(manifest["trajectories"]),
                    calls=manifest["total_generate_calls"],
                    generated_tokens=manifest["total_generated_tokens"],
                    qualified=assessment["qualified"],
                    generation_manifest_id=manifest["id"],
                    scoring_report_id=assessment["id"],
                )
            )
        guard_root = run_dir if seed == 29 else original / "runs" / key
        guard = e.read(guard_root / "rounds/epoch5/numeric_guard.json")
        require(guard["passed"], "new_point_numeric_guard")
        guards.append(dict(seed=seed, **guard))
        update = e.read(guard_root / "rounds/epoch5/distribution_update.json")
        core = update["numeric_core_update"]
        require(
            core["controls_exactly_preserved"] and not update["novelty_active"],
            "C_only_preserves_controls",
        )
        distributions.append(
            dict(
                seed=seed,
                id=update["id"],
                status=update["status"],
                global_weighted_RMS=core["temperature"]["global_weighted_RMS"],
                weighted_TV=core["weighted_TV"],
                weighted_KL_next_current=core["weighted_KL_next_current"],
                weighted_KL_next_prior=core["weighted_KL_next_prior"],
                weighted_entropy=core["weighted_entropy"],
                maximum_optimality_residual=core["maximum_optimality_residual"],
                controls_exactly_preserved=core["controls_exactly_preserved"],
                novelty_active=update["novelty_active"],
            )
        )
    table = []
    for condition, total_key in (
        ("Static", "Static_qualified"),
        ("C-only", "original_C_only_qualified"),
        ("Full", "original_Full_qualified"),
        ("Delayed-C", "Delayed_C_qualified"),
    ):
        values = {str(seed): sum(scores[condition, seed].values()) for seed in SEEDS}
        total = sum(values.values())
        require(total == final[total_key], "matrix_total:" + condition)
        if condition in ("Static", "C-only", "Full"):
            old_key = {
                "Static": "Static_qualified",
                "C-only": "C_only_qualified",
                "Full": "Full_qualified",
            }[condition]
            require(total == original_matrix[old_key], "unchanged_original_matrix")
        table.append(
            dict(
                condition=condition,
                per_seed=values,
                qualified=total,
                denominator=540,
                rate=total / 540,
            )
        )
    pairs = [
        dict(seed=seed, **paired(scores["Static", seed], scores["Delayed-C", seed]))
        for seed in SEEDS
    ]
    groups = []
    for seed in SEEDS:
        for group in GROUPS:
            selected = {
                condition: {
                    task: value
                    for task, value in scores[condition, seed].items()
                    if tasks[task] == group
                }
                for condition in ("Static", "C-only", "Full", "Delayed-C")
            }
            groups.append(
                dict(
                    seed=seed,
                    group=group,
                    qualified={condition: sum(row.values()) for condition, row in selected.items()},
                    **paired(selected["Static"], selected["Delayed-C"]),
                )
            )
    task_pattern = Counter()
    for task in tasks:
        signs = {scores["Delayed-C", seed][task] - scores["Static", seed][task] for seed in SEEDS}
        task_pattern[
            "unchanged_all_seeds"
            if signs == {0}
            else "mixed_signs"
            if {-1, 1} <= signs
            else "nonnegative_only"
            if 1 in signs
            else "nonpositive_only"
        ] += 1
    equivalence = [
        e.read(path)
        for path in sorted((recovery / "runs/A_delayed_c_47/replay_equivalence").glob("*.json"))
    ]
    require([row["step"] for row in equivalence] == list(range(201, 304)), "all_103_replayed_steps")
    require(
        all(
            row["exact_report_id"]
            and row["original_update_id"] == row["resumed_update_id"]
            and row["maximum_absolute_difference"] == 0
            for row in equivalence
        ),
        "exact_saved_replay_reports",
    )
    replay = dict(
        steps=103,
        first=201,
        last=303,
        all_exact_report_id=True,
        maximum_absolute_difference=max(row["maximum_absolute_difference"] for row in equivalence),
        atol=recovery_plan["replay_equivalence"]["atol"],
        rtol=recovery_plan["replay_equivalence"]["rtol"],
    )
    metadata = {}
    for label, path in (
        ("proxy_plan", root / A / "proxy_direction_audit_20260919/plan.json"),
        ("proxy_report", root / A / "proxy_direction_audit_20260919/report.json"),
        ("actual_admission", original / "admission.json"),
        ("original_worker_failure", original / "runs/A_delayed_c_29/failure.json"),
        ("original_failure", original / "coordinator_failure.json"),
        ("sft_capacity_amendment", recovery / "gpu5_sft_capacity_20260921/registration.json"),
        ("autorun_amendment", control / "registration.json"),
        ("gpu7_amendment", control / "gpu7_seed47_attempt_20260922/registration.json"),
        ("watchdog_status", control / "watchdog_status.json"),
    ):
        row = e.read(path)
        metadata[label] = {
            key: row[key]
            for key in (
                "id",
                "at",
                "status",
                "coordinator_returncode",
                "all_twelve_numeric_points_passed",
                "actual_extra_resources",
                "direction_audit_completed",
                "direction_stability_not_assumed",
            )
            if key in row
        }
    require(metadata["watchdog_status"]["coordinator_returncode"] == 0, "normal_supervisor_exit")
    require(metadata["proxy_report"]["all_twelve_numeric_points_passed"], "prior_numeric_admission")
    require(
        final["development_is_not_independent_confirmation"]
        and not final["B_or_confirmation_started"],
        "honest_scope",
    )
    difference = sum(row["net"] for row in pairs)
    require(
        difference == final["Delayed_C_qualified"] - final["Static_qualified"]
        and difference / 540 == final["primary_mean_difference"],
        "primary_difference",
    )
    require(
        sum(row["sessions"] for row in generation_rows) == plan["new_sessions_total"]
        and sum(row["calls"] for row in generation_rows) <= plan["new_generate_cap"],
        "generation_registered_budget",
    )
    ledgers = []
    for label, run_dir, first, last in (
        ("original_seed11", original / "runs/A_delayed_c_11", 1, 400),
        ("original_seed29", original / "runs/A_delayed_c_29", 1, 200),
        ("original_seed47", original / "runs/A_delayed_c_47", 1, 303),
        ("recovered_seed29", recovery / "runs/A_delayed_c_29", 201, 400),
        ("recovered_seed47", recovery / "runs/A_delayed_c_47", 201, 400),
    ):
        paths = sorted((run_dir / "updates").glob("*/report.json"))
        require(
            [int(path.parent.name) for path in paths] == list(range(first, last + 1)),
            "contiguous_completed_updates:" + label,
        )
        totals, inventory = Counter(), []
        for path in paths:
            value = e.read(path, index=False)
            totals.update(
                {
                    name: value[name]
                    for name in (
                        "packages_completed",
                        "rows_completed",
                        "sequence_tokens",
                        "target_tokens",
                    )
                }
            )
            inventory.append(
                dict(
                    path="ROOT/" + str(path.relative_to(root)),
                    sha256=digest(path.read_bytes()),
                    record_id=value["id"],
                )
            )
        ledgers.append(
            dict(
                label=label,
                completed_updates=len(paths),
                first=first,
                last=last,
                **dict(totals),
                inventory_sha256=digest(canonical(inventory)),
            )
        )
    require(
        sum(row["completed_updates"] for row in ledgers)
        == final["physical_completed_optimizer_updates_lower_bound"],
        "physical_completed_update_ledger",
    )
    result_counts = Counter(
        e.read(path)["returncode"] for path in sorted((control / "results").glob("*/*.json"))
    )
    gpu7_records = []
    for index in range(169, 180):
        directory = (
            raw / "A_delayed_c_47/durable_final_greedy/resume_attempts" / f"0007_{index:04d}"
        )
        meter = e.read(directory / "meter.json")
        completed = e.read(directory / "completed" / f"{index:04d}.json")
        require(meter["index"] == completed["job"]["index"] == index, "gpu7_trial_fixed_indices")
        require(
            meter["generate_call_intents"]
            == meter["generate_calls_returned"]
            == completed["actual_generate_calls"],
            "gpu7_meter_completed_join",
        )
        gpu7_records.append(completed)
    return dict(
        schema_version="delayed_C_postrun_metadata_audit.v1",
        created_at=datetime.now(timezone.utc).isoformat(),
        audit_base_commit=subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip(),
        audit_script_sha256=digest(Path(__file__).read_bytes()),
        paths=dict(ROOT=str(root), RAW=str(raw)),
        scope=(
            "metadata and sealed score arithmetic only; no session rescore, tensor load, "
            "GPU execution, API request, or new experiment"
        ),
        all_checks_passed=True,
        summary_id=final["id"],
        plan_id=plan["id"],
        recovery_plan_id=recovery_plan["id"],
        conditions=table,
        runs=run_rows,
        paired_vs_static=pairs,
        groups=groups,
        task_pattern_across_three_seeds=dict(task_pattern),
        generation_accounting=generation_rows,
        training_report_ledgers=ledgers,
        autorun_result_returncode_counts=dict(result_counts),
        gpu7_trial=dict(
            completed_sessions=len(gpu7_records),
            calls=sum(row["actual_generate_calls"] for row in gpu7_records),
            generated_tokens=sum(row["generated_tokens"] for row in gpu7_records),
        ),
        replay_equivalence=replay,
        new_point_numeric_guards=guards,
        distribution_update_diagnostics=distributions,
        score_record_ids=[
            dict(condition=condition, seed=seed, id=identity)
            for (condition, seed), identity in score_ids.items()
        ],
        original_budget={
            key: plan[key]
            for key in (
                "new_optimizer_updates",
                "new_feedback_sessions",
                "new_final_greedy_sessions",
                "new_generate_cap",
                "SFT_sequence_tokens",
                "SFT_supervision_tokens",
                "extra_class_sequence_tokens",
            )
        },
        recovery_budget=recovery_plan["budget"],
        completion_accounting={
            key: final[key]
            for key in (
                "effective_optimizer_updates",
                "physical_completed_optimizer_updates_lower_bound",
                "physical_exact_count_not_claimed",
                "known_additional_repeated_completed_updates",
                "interrupted_update_intents_with_unknown_completion_count",
                "interrupted_final_generate_call_upper_bound",
            )
        },
        metadata=metadata,
        evidence=list(e.rows.values()),
        limitations=[
            "No fresh tensor or optimizer-state checksum validation",
            "No raw session replay or private rescoring",
            "No independent confirmation",
            "540 observations repeat 180 tasks across 3 seeds",
            "Byte hashes and record IDs establish local consistency, not third-party attestation",
            "Worker result.at may be start time; use event/manifest/score completion timestamps",
        ],
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--raw-root", type=Path, default=RAW_DEFAULT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(args.root.resolve(), args.raw_root.resolve())
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
        print(
            json.dumps(
                dict(
                    output=str(args.output),
                    all_checks_passed=True,
                    evidence_files=len(result["evidence"]),
                    conditions=result["conditions"],
                ),
                ensure_ascii=False,
            )
        )
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
