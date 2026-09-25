"""Reproduce the completed B study report from sealed small JSON, without model calls."""

# ruff: noqa: E501 -- exact evidence bindings and fixed experimental scope
import argparse
import json
import math
from collections import Counter
from datetime import datetime
from fractions import Fraction
from pathlib import Path

import fixed_kernel_B_report_statistics_20260925 as statistics

from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p

SCRIPT = "trusted_data_synthesis/scripts/audit_fixed_kernel_B_confirmation_20260925.py"
HELPER = "trusted_data_synthesis/scripts/fixed_kernel_B_report_statistics_20260925.py"
RAW = Path(
    "/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/delayed_C_B_confirmation_cache_20260922"
)
OUTPUT = "trusted_data_synthesis/docs/audit_reports/B_confirmation_20260925/evidence.json"


def scalar(value):
    return float(Fraction(value)) if isinstance(value, str) else float(value)


class Evidence:
    def __init__(self, raw):
        self.raw, self.values, self.references = raw, {}, {}

    def read(self, name):
        if name not in self.values:
            payload = (self.raw / name).read_bytes()
            value = json.loads(payload)
            if value.get("schema_version", "").startswith("fixed_kernel_value.v1."):
                p.checked(value, value["id"].split(":", 1)[0])
            self.values[name] = value
            self.references[name] = dict(
                sha256=p.sha(payload), bytes=len(payload), record_id=value.get("id")
            )
        return self.values[name]


def proxy_summary(e, plan):
    binding = plan["materials"]["binding"]
    prior, mu, controls = binding["prior"], binding["mu"], binding["control_tasks"]
    summaries = []
    for seed in plan["seeds"]:
        folder = f"outer/B_delayed_c_{seed}/"
        report, guard, scale, update, gj = [
            e.read(folder + name + ".json")
            for name in ("report", "numeric_guard", "C_scale", "distribution_update", "gJ")
        ]
        nxt = update["pi_next"]
        p.require(
            report["complete"]
            and report["numeric_guard_passed"]
            and guard["passed"]
            and report["distribution_update_id"] == update["id"],
            "B_report.complete_bound_outer",
        )
        p.require(
            set(nxt) == set(prior) and all(set(nxt[x]) == set(prior[x]) for x in prior),
            "B_report.unchanged_distribution_support",
        )
        tv = {
            x: 0.5 * math.fsum(abs(scalar(nxt[x][z]) - scalar(a)) for z, a in states.items())
            for x, states in prior.items()
        }
        kl = {
            x: math.fsum(
                scalar(nxt[x][z]) * math.log(scalar(nxt[x][z]) / scalar(a))
                for z, a in states.items()
            )
            for x, states in prior.items()
        }
        p.require(all(tv[x] == 0 for x in controls), "B_report.controls_numerically_unchanged")
        concentration = report["positive_feedback_concentration"]
        summaries.append(
            dict(
                seed=seed,
                outer_report_id=report["id"],
                qualified_feedback=report["qualified"],
                feedback_denominator=360,
                replay_responses=report["required_replay_responses"],
                feedback_generate_calls=report["generate_calls"],
                C_relative_weighted_RMS_error=guard["C_comparison"]["relative_weighted_RMS"],
                C_sign_disagreements=guard["C_comparison"]["sign_disagreements"],
                pi_reference_weighted_TV_error=guard["pi_reference_weighted_TV"],
                numeric_guard_passed=guard["passed"],
                original_Adam_used=guard["original_Adam_used_for_actual_update"],
                stable_reference_not_substituted=guard["reference_not_substituted"],
                contribution_RMS_R=scale["R"],
                T_C_min=min(scale["T_C"].values()),
                T_C_max=max(scale["T_C"].values()),
                temperature_floor=scale["temperature"]["RMS_floor"],
                feedback_accounting=gj["accounting"],
                positive_unique_tasks=concentration["positive_unique_tasks"],
                positive_unique_CIKs=concentration["positive_unique_CIKs"],
                largest_positive_CIK_share=concentration["largest_CIK_share"],
                largest_positive_task_share=concentration["largest_task_share"],
                cross_repeat_reliability=concentration["new_point_cross_repeat_reliability"],
                actual_mu_weighted_TV=math.fsum(scalar(mu[x]) * value for x, value in tv.items()),
                max_task_TV=max(tv.values()),
                actual_mu_weighted_KL_next_prior=math.fsum(
                    scalar(mu[x]) * value for x, value in kl.items()
                ),
                max_task_KL_next_prior=max(kl.values()),
                controls_changed=0,
                maximum_optimality_residual=update["numeric_core_update"][
                    "maximum_optimality_residual"
                ],
                actual_distribution_change_is_descriptive_not_effect_confirmation=True,
            )
        )
    return summaries


def extract(root, raw):
    root, raw = Path(root).resolve(), Path(raw).resolve()
    e = Evidence(raw)
    plan, report, complete = [
        e.read(name) for name in ("protocol.json", "report.json", "complete.json")
    ]
    publication, seal = e.read("publication.json"), e.read("confirmation_generation_seal.json")
    revision = e.read("revisions/control_guard_20260924/registration.json")
    link = e.read("revisions/control_guard_20260924/completion_link.json")
    p.require(
        report == complete
        and report["protocol_id"] == plan["id"]
        and report["status"] == "COMPLETE_B_MAIN_CONFIRMATION",
        "B_report.completed_same_registered_study",
    )
    p.require(
        publication["status"] == "PUBLISHED" and publication["report_id"] == report["id"],
        "B_report.published_completed_report",
    )
    p.require(
        link["revision_id"] == revision["id"]
        and link["scientific_report_id"] == report["id"]
        and link["protocol_id"] == plan["id"],
        "B_report.revision_disclosed",
    )
    p.require(
        p.sha(raw / "protocol.json") == revision["protocol_sha256"],
        "B_report.original_protocol_bytes",
    )
    for name, digest in {**plan["scientific_sources"], **revision["new_sources"]}.items():
        p.require(p.sha(root / name) == digest, "B_report.frozen_execution_source:" + name)
    e.read("revisions/control_guard_20260924/resume_applied.json")
    e.read("revisions/control_guard_20260924/archive/needs_attention_resolved.json")
    training, prefixes, totals, effective = [], {}, Counter(), Counter()
    for job in plan["training_jobs"]:
        key = job["key"]
        value = e.read(f"jobs/{key}/report.json")
        p.require(
            value["complete"]
            and value["plan_id"] == plan["id"]
            and value["job_key"] == key
            and value["completed_updates"] == job["stop"],
            "B_report.completed_training_job",
        )
        steps = {int(path.stem) for path in (raw / "jobs" / key / "updates").glob("*.pt")}
        p.require(
            steps == set(range(job["start"] + 1, job["stop"] + 1)),
            "B_report.complete_checkpoint_filename_range",
        )
        totals.update(value["physical_job_totals"])
        training.append(
            dict(
                key=key,
                seed=job["seed"],
                condition=job["condition"],
                completed_updates=value["completed_updates"],
                committed_physical_updates=len(steps),
                report_id=value["id"],
                checkpoint_sha256_recorded=value["checkpoint_sha256"],
                snapshot_id=value["snapshot_id"],
            )
        )
        if job["condition"] == "prefix":
            prefixes[job["seed"]] = value
        else:
            effective.update(value["effective_totals"])
    for job in plan["training_jobs"]:
        if job["condition"] == "prefix":
            continue
        key, prefix = job["key"], prefixes[job["seed"]]
        branch, point = (
            e.read(f"jobs/{key}/branch_binding.json"),
            e.read(f"points/{key}/point.json"),
        )
        p.require(
            branch["prefix_checkpoint_sha256"] == prefix["checkpoint_sha256"]
            and branch["prefix_snapshot_id"] == prefix["snapshot_id"]
            and branch["rng_complete"]
            and branch["starts_from_real_model_Adam_and_RNG"]
            and not branch["virtual_point_used_for_SFT"],
            "B_report.actual_shared_prefix_identity",
        )
        p.require(
            point["shared_prefix_binding_id"] == branch["id"]
            and point["training_report_id"] == e.read(f"jobs/{key}/report.json")["id"]
            and point["step"] == 400,
            "B_report.unique_final400_point",
        )
    p.require(
        sum(row["committed_physical_updates"] for row in training) == 1800,
        "B_report.1800_physical_updates",
    )
    p.require(
        totals["sequence_tokens"] == plan["effective_budget"]["physical_SFT_sequence_tokens_base"]
        and totals["target_tokens"] == plan["effective_budget"]["physical_SFT_target_tokens_base"],
        "B_report.physical_training_token_budget",
    )
    p.require(
        effective["sequence_tokens"] == plan["effective_budget"]["effective_model_sequence_tokens"]
        and effective["target_tokens"] == plan["effective_budget"]["effective_model_target_tokens"],
        "B_report.effective_training_token_budget",
    )
    budget = e.read("budget/state.json")
    cohorts, committed = [], {}
    for phase, conditions, count in (
        ("feedback", ("delayed_c",), 360),
        ("confirm", ("static", "delayed_c"), 720),
    ):
        for condition in conditions:
            for seed in plan["seeds"]:
                key = f"B_{condition}_{seed}"
                folder = f"generation/{phase}/{key}/"
                generated, scored = (
                    e.read(folder + "generation_manifest.json"),
                    e.read(folder + "scoring_report.json"),
                )
                rows = generated["trajectories"]
                p.require(
                    generated["complete"]
                    and scored["complete"]
                    and len(rows) == scored["denominator"] == count
                    and scored["generation_manifest_id"] == generated["id"]
                    and scored["point_id"] == generated["point_id"],
                    "B_report.complete_cohort_identity",
                )
                p.require(
                    [row["job"]["index"] for row in rows] == list(range(count)),
                    "B_report.exact_cohort_indices",
                )
                calls, tokens = (
                    sum(row["actual_generate_calls"] for row in rows),
                    sum(row["generated_tokens"] for row in rows),
                )
                p.require(
                    calls == generated["total_generate_calls"]
                    and tokens == generated["total_generated_tokens"],
                    "B_report.committed_generation_accounting",
                )
                for row in rows:
                    meter_key = row["point_id"] + ":" + str(row["job"]["index"])
                    p.require(
                        meter_key not in committed, "B_report.unique_committed_generation_identity"
                    )
                    committed[meter_key] = dict(
                        record_id=row["id"], calls=row["actual_generate_calls"]
                    )
                cohorts.append(
                    dict(
                        key=key,
                        phase=phase,
                        seed=seed,
                        condition=condition,
                        sessions=count,
                        qualified=scored["qualified"],
                        generate_calls=calls,
                        generated_tokens=tokens,
                        legal_context_rejection_sessions=sum(
                            bool(row["legal_context_rejection"]) for row in rows
                        ),
                        summed_session_elapsed_seconds=sum(row["elapsed_seconds"] for row in rows),
                        generation_manifest_id=generated["id"],
                        scoring_report_id=scored["id"],
                    )
                )
    p.require(
        committed == budget["committed_generation"] and len(committed) == 5400,
        "B_report.all_committed_sessions_match_budget",
    )
    for kind in (
        "optimizer",
        "population",
        "feedback_response",
        "generate_call",
        "score_case",
        "worker_start",
    ):
        p.require(
            budget["counts"][kind] <= plan["physical_budget"][kind + "_cap"],
            "B_report.within_physical_budget:" + kind,
        )
    results = [
        e.read(str(path.relative_to(raw))) for path in sorted((raw / "results").glob("*/*.json"))
    ]
    p.require(
        len(results) == budget["counts"]["worker_start"],
        "B_report.every_charged_worker_has_terminal_result",
    )
    by_code = Counter(row["returncode"] for row in results)
    worker_hours = Counter()
    for row in results:
        seconds = (
            datetime.fromisoformat(row["finished_at"]) - datetime.fromisoformat(row["started_at"])
        ).total_seconds()
        p.require(seconds >= 0, "B_report.nonnegative_worker_interval")
        worker_hours[row["kind"]] += seconds / 3600
    restarts = []
    for line in (raw / "coordinator.log").read_text().splitlines():
        if line.startswith("{"):
            value = json.loads(line)
            if value.get("event") == "B_controller_resource_restart":
                restarts.append(dict(at=value["at"], error=value["error"]))
    failed = [row for row in results if row["returncode"] not in (0, 43)]
    p.require(
        len(failed) == 1
        and failed[0]["key"] == "B_delayed_c_11"
        and failed[0]["attempt"] == 1
        and failed[0]["error"] == "ValueError('fixed_kernel.B_training.control_prior_unchanged')",
        "B_report.only_disclosed_nonresource_failure",
    )
    score_results = [row for row in results if row["key"].startswith("score_confirm_")]
    p.require(
        len(score_results) == 6
        and all(row["returncode"] == 0 and row["started_at"] > seal["at"] for row in score_results),
        "B_report.all_private_confirmation_scoring_after_global_seal",
    )
    p.require(
        seal["complete"]
        and seal["all_generation_workers_exited"]
        and seal["total_trajectories"] == 4320,
        "B_report.all4320_sealed",
    )
    for row in seal["models"]:
        p.require(
            p.sha(Path(row["generation_manifest_path"])) == row["generation_manifest_sha256"],
            "B_report.sealed_generation_manifest_bytes",
        )
    successful = [row for row in results if row["returncode"] == 0]

    def times(prefix):
        rows = [row for row in successful if row["key"].startswith(prefix)]
        return dict(
            start=min(row["started_at"] for row in rows),
            finish=max(row["finished_at"] for row in rows),
        )

    timeline = dict(
        protocol_frozen=plan["at"],
        initial_training=times("B_prefix_"),
        static_tails=times("B_static_"),
        delayed_tails=times("B_delayed_c_"),
        final_generation=times("confirm_"),
        global_seal=seal["at"],
        confirmation_scoring=times("score_confirm_"),
        report_complete=report["at"],
        publication=publication["at"],
        revision_registered=revision["at"],
    )
    timeline["initial_training_to_publication_hours"] = (
        datetime.fromisoformat(publication["at"])
        - datetime.fromisoformat(timeline["initial_training"]["start"])
    ).total_seconds() / 3600
    watchdog = e.read("watchdog_status.json")
    p.require(
        watchdog["returncode"] == 0 and not e.read("control/state.json")["active"],
        "B_report_controller_completed",
    )
    for name in ("confirm_views/admission.json", "confirm_views/manifest.json"):
        e.read(name)
    analysis = statistics.extract(root, raw)
    p.require(
        not report["positive_effect_confirmed"] and report["point_estimate"] == 1 / 144,
        "B_report_preserve_registered_nonconfirmation",
    )
    return p.record(
        "B_completed_study_audit_evidence",
        protocol_id=plan["id"],
        scientific_report_id=report["id"],
        publication_commit=publication["commit"],
        revision_id=revision["id"],
        audit_code_sha256={name: p.sha(root / name) for name in (SCRIPT, HELPER)},
        verification_scope=dict(
            small_JSON_records_and_saved_scores=True,
            original_code_hashes_checked=True,
            checkpoint_filename_ranges_checked=True,
            large_tensor_files_loaded=False,
            tensor_file_hashes_recomputed=False,
            gzip_sessions_opened=False,
            private_bundles_opened=False,
            new_training_or_generation_or_scoring=False,
            frozen_bootstrap_recomputed_from_saved_Q=True,
        ),
        statistics=analysis,
        training=training,
        physical_SFT_totals=dict(totals),
        effective_final_model_totals=dict(effective),
        cohorts=cohorts,
        proxy_diagnostics=proxy_summary(e, plan),
        resources=dict(
            reservations=budget["counts"],
            physical_caps=plan["physical_budget"],
            committed_sessions=len(committed),
            committed_generate_calls=sum(row["calls"] for row in committed.values()),
            uncommitted_generate_call_reservation_difference=budget["counts"]["generate_call"]
            - sum(row["calls"] for row in committed.values()),
            worker_results_by_returncode={str(k): v for k, v in sorted(by_code.items())},
            capacity_yields_by_kind=dict(
                Counter(row["kind"] for row in results if row["returncode"] == 43)
            ),
            preserved_failures=[
                dict(
                    key=row["key"],
                    attempt=row["attempt"],
                    error=row["error"],
                    finished_at=row["finished_at"],
                )
                for row in failed
            ],
            worker_interval_hours_by_kind=dict(worker_hours),
            GPU_worker_interval_hours=sum(
                value for kind, value in worker_hours.items() if kind != "score"
            ),
            worker_interval_not_GPU_busy_time_or_exclusive_allocation=True,
            controller_resource_restarts=restarts,
        ),
        timeline=timeline,
        evidence_files=e.references,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--raw", type=Path, default=RAW)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    evidence = extract(root, args.raw)
    output = args.output or root / OUTPUT
    if output.exists():
        p.require(p.read_json(output) == evidence, "B_report.reproduced_identical_evidence")
    else:
        p.write_once(output, evidence)
    print(
        json.dumps(
            dict(
                id=evidence["id"],
                evidence_files=len(evidence["evidence_files"]),
                output=str(output),
                resources=evidence["resources"],
            ),
            ensure_ascii=False,
        )
    )
