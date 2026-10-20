"""V63's six new endpoints and 24 fixed generation jobs.

Only b=1 C1/C05 are generated or scored.  The nine old endpoints are immutable
read-only references.  Private scoring is gated by the real successful exits
of every new training and generation worker, not a panel-local early result.
"""

from __future__ import annotations

import argparse
import asyncio
import fcntl
import gc
import importlib
import json
import os
from pathlib import Path

import finqa_v63_binding as binding

binding.install_scientific_paths()

import finqa_v63_statistics as stats
import finqa_v54_evaluation as original

RunConfig = original.RunConfig
digest, require = binding.digest, stats.require
bound, checked, file_binding = original.bound, binding.checked, binding.file_ref
checked_file, publish = original.checked_file, binding.publish
_public_source = original._public_source
_panel_private_bundles = original._panel_private_bundles
SEEDS, ARMS, FEEDBACK_BATCH = stats.SEEDS, stats.ARMS, stats.FEEDBACK_BATCH
GREEDY_SEED, DRAW_SEEDS = original.GREEDY_SEED, original.DRAW_SEEDS
PRIMARY_PANEL = original.PRIMARY_PANEL
PANEL_SPECS = tuple(spec for spec in original.PANEL_SPECS if spec[1] == 894)


def _snapshot_state(reference, seed, step, final):
    state = original._snapshot_state(reference, seed, step, final)
    require(state["outer_done"] == [298],
            "both new b1 branches retain pre596 outer history; old C1 outer cannot be inherited")
    return state


def panel_config(panel_id, draw_seed):
    require(panel_id in {spec[0] for spec in PANEL_SPECS},
            "unregistered V63 panel: no step745 or new test generation")
    return original.panel_config(panel_id, draw_seed)


def evaluation_contract():
    panels = {name: dict(step=step, role=role, tasks_per_draw=n, draw_seeds=list(draws),
        temperature=temperature, models=6, sessions=6 * n * len(draws),
        configs={str(d): panel_config(name, d).model_dump(mode="json") for d in draws},
        purpose="primary" if name == PRIMARY_PANEL else "predeclared diagnosis")
        for name, step, role, n, draws, temperature in PANEL_SPECS}
    return dict(
        schema="v63_balanced_feedback_batch_evaluation_contract.v1",
        seeds=list(SEEDS), arms=list(ARMS), feedback_batch=FEEDBACK_BATCH,
        panels=panels, primary_panel=PRIMARY_PANEL,
        total_sessions=7458, generation_jobs=24, new_feedback_sessions=4200,
        total_new_sessions_including_feedback=11658,
        logical_endpoint_conditions=15, reused_old_endpoint_conditions=9,
        new_training_branches=6, independent_parent_count=3,
        required_step894_snapshot_count=6, step745_new_generation=0,
        before_any_generation="all six new b1 branches complete and six step894 snapshots sealed",
        before_any_private_scoring="all 24 new generation jobs sealed and actual successful exits observed",
        old_results_read_only=True, old_hold_new_generation=0, old_hold_rescoring=0,
        old_new_batch_pooling=False, best_of_old_new_selection=False,
        stochastic_temperature_identical_for_all_arms=1.0,
        feedback_seeds_are_not_evaluation_seeds=True,
        old_test1147_new_generation=0, API_calls=0, native_scorer_reused=True,
        unknown_as_zero=False,
        partial_results_must_not_influence_remaining_training_or_generation=True,
        statistics=stats.statistics_contract(),
    )


def planned_jobs():
    jobs = {}
    for panel, step, role, n, draws, _ in PANEL_SPECS:
        for seed in SEEDS:
            for arm in ARMS:
                for draw in draws:
                    key = f"{panel}_seed{seed}_{arm}_b1_draw{draw}"
                    jobs[key] = dict(
                        job_id=key, stage="generate", memory_phase="generate",
                        seed=seed, arm=arm, feedback_batch=FEEDBACK_BATCH,
                        panel=panel, step=step, draw_seed=draw, role=role,
                        denominator=n, config=panel_config(panel, draw).model_dump(mode="json"))
    require(len(jobs) == 24 and sum(row["denominator"] for row in jobs.values()) == 7458,
            "V63 evaluation dose changed")
    return jobs


def _training():
    return importlib.import_module("finqa_v63_training")


def _runtime():
    _training().runtime()
    return importlib.import_module("trusted_synthesis.finance_research.v9_final_evaluation")


def _protocol(root):
    require(Path(root).resolve() == Path(binding.ROOT).resolve(),
            "V63 evaluation only operates in its independent registered root")
    protocol = checked(Path(root) / "protocol/record.json")
    require(protocol["evaluation"] == evaluation_contract(), "prospective V63 evaluation contract changed")
    return protocol


def _old_path(reference, expected):
    require(Path(reference["path"]).resolve() == Path(expected).resolve(),
            "old evaluation reference must resolve to its registered original path")
    return checked_file(reference)


def _old_registration(protocol):
    old_root = Path(binding.OLD_ROOT).resolve()
    path = _old_path(protocol["old_evaluation_registration"],
                     old_root / "evaluations/registration/record.json")
    plan = checked(path)
    require(plan["contract"]["primary_panel"] == PRIMARY_PANEL
            and plan["contract"]["seeds"] == list(SEEDS)
            and plan["contract"]["arms"] == list(stats.original.ARMS),
            "the original nine-condition evaluation registration is required")
    return plan


def _old_summary(protocol, panel, old_plan):
    reference = protocol["old_evaluation_summaries"][panel]
    path = _old_path(reference, Path(binding.OLD_ROOT) / "evaluations/panels" / panel / "summary/record.json")
    value = checked(path)
    require(value["panel"] == panel and value["registration_id"] == old_plan["id"]
            and value["independent_parent_count"] == 3
            and set(value["model_reports"]) == {
                stats.original.coordinate(seed, arm) for seed in SEEDS for arm in stats.original.ARMS},
            "old panel must retain all nine original models and the original registration")
    return value


def generation_barrier(root, *, branch_reader=None):
    root = Path(root).resolve()
    protocol = _protocol(root)
    seal_path = root / "training_barrier/record.json"
    seal = checked(seal_path)
    require(seal["protocol_id"] == protocol["id"]
            and seal["all_six_new_branches_complete"] is True
            and seal["all_six_894_snapshots_sealed"] is True
            and seal["all_dispatched_training_workers_exited"] is True
            and seal["active_children"] == [],
            "all six new branches require actual successful training exits before generation")
    reader = branch_reader or _training().checked_branch_result
    branches, snapshots = {}, {}
    require(set(seal["branch_records"]) == {stats.coordinate(s, a) for s in SEEDS for a in ARMS},
            "training barrier must cover exactly the six new b1 branches")
    for seed in SEEDS:
        for arm in ARMS:
            key = stats.coordinate(seed, arm)
            result = reader(root, seed, arm)
            require(result.get("schema") == "v63_fixed_q_branch_complete.v1"
                    and result["status"] == "COMPLETE" and result["seed"] == seed
                    and result["arm"] == arm and type(result.get("feedback_batch")) is int
                    and result["feedback_batch"] == FEEDBACK_BATCH
                    and result["optimizer_updates"] == 298
                    and result["new_optimizer_updates"] == 298
                    and "894" in result["snapshots"],
                    "six complete new b1 fixed-window branches and step894 snapshots required")
            path = root / "branches" / f"seed{seed}" / arm / "completed/record.json"
            require(checked(path) == result, "branch reader and durable completed result differ")
            branches[key] = file_binding(path)
            require(seal["branch_records"][key] == branches[key],
                    "controller training-exit seal and complete branch bytes differ")
            reference = result["snapshots"]["894"]
            require(reference.get("state_sha256") and reference.get("actual_state_digest")
                    and reference.get("record_sha256"), "actual step894 checkpoint bytes required")
            snapshots[f"{key}/step894"] = reference
    return publish(root / "evaluations/training_barrier/record.json", dict(
        schema="v63_six_new_training_branches_sealed.v1", protocol_id=protocol["id"],
        controller_training_barrier=file_binding(seal_path),
        branches=branches, snapshots=snapshots, new_branches=6, snapshot_count=6,
        feedback_batch=FEEDBACK_BATCH, generation_started=False, private_references_read=False))


def prepare_jobs(root):
    """Prepare the exact 24 generation runs after all six training exits."""
    root = Path(root).resolve()
    protocol, barrier, final = _protocol(root), generation_barrier(root), _runtime()
    registration = root / "evaluations/registration/record.json"
    if registration.exists():
        plan = checked_plan(root)
    else:
        source, cohorts = _public_source(protocol, final)
        old_plan = _old_registration(protocol)
        require(old_plan["snapshot"] == source["snapshot"]
                and old_plan["snapshot_id"] == source["snapshot_id"]
                and old_plan["role_plan"] == source["role_plan"]
                and old_plan["cohorts"] == cohorts,
                "new evaluation must use the original dev/cal cohorts, order and source groups")
        for panel, *_ in PANEL_SPECS:
            _old_summary(protocol, panel, old_plan)
            require(old_plan["contract"]["panels"][panel]["configs"]
                    == evaluation_contract()["panels"][panel]["configs"],
                    "new and old conditions must use identical evaluation decoding")
        original_identity = next(iter(source["jobs"].values()))["model_identity"]
        snapshot_jobs = {}
        for seed in SEEDS:
            for arm in ARMS:
                key = f"{stats.coordinate(seed, arm)}/step894"
                reference = barrier["snapshots"][key]
                state = _snapshot_state(reference, seed, 894, final)
                identity = final.ModelIdentity(
                    backend="local_torch", model_id=source["assets"]["base_binding"]["id"],
                    point_id="v63-b1-evaluation:" + digest(dict(
                        protocol_id=protocol["id"], seed=seed, arm=arm,
                        feedback_batch=FEEDBACK_BATCH, step=894, checkpoint=reference)),
                    parameter_digest=final.parameter_digest(state["parameters"]),
                    tokenizer_digest=original_identity["tokenizer_digest"],
                    chat_template_digest=original_identity["chat_template_digest"])
                snapshot_jobs[key] = dict(checkpoint=reference, model_identity=identity.model_dump(mode="json"))
                del state
        jobs = {key: {**job, **snapshot_jobs[f"{stats.coordinate(job['seed'], job['arm'])}/step894"]}
                for key, job in planned_jobs().items()}
        plan = publish(registration, dict(
            schema="v63_b1_evaluation_registration.v1", protocol_id=protocol["id"],
            feedback_batch=FEEDBACK_BATCH, contract=evaluation_contract(),
            training_barrier=file_binding(root / "evaluations/training_barrier/record.json"),
            original_evaluation_source=protocol["evaluation_source_registration"],
            old_evaluation_registration=protocol["old_evaluation_registration"],
            old_evaluation_summaries=protocol["old_evaluation_summaries"],
            assets=source["assets"], snapshot=source["snapshot"], snapshot_id=source["snapshot_id"],
            role_plan=source["role_plan"], runtime_binding=final.runtime_binding(),
            source_binding={Path(__file__).name: file_binding(__file__)["sha256"],
                            Path(stats.__file__).name: file_binding(stats.__file__)["sha256"]},
            cohorts=cohorts, jobs=jobs, private_references_read=False, generation_calls=0))
    require(barrier["id"] == checked(checked_file(plan["training_barrier"]))["id"],
            "training barrier changed before run preparation")
    for job in plan["jobs"].values():
        directory = generation_root(root, job)
        if (directory / "run.json").exists():
            inspect_job(root, plan, job, final=final)
        else:
            final.prepare_run(plan["snapshot"], plan["role_plan"], directory, role=job["role"],
                config=RunConfig.model_validate(job["config"]),
                identity=final.ModelIdentity.model_validate(job["model_identity"]),
                task_keys=plan["cohorts"][job["role"]]["tasks"])
    return plan


def checked_plan(root):
    root = Path(root).resolve()
    protocol, final = _protocol(root), _runtime()
    plan = checked(root / "evaluations/registration/record.json")
    require(plan["protocol_id"] == protocol["id"] and plan["contract"] == evaluation_contract()
            and plan["feedback_batch"] == FEEDBACK_BATCH
            and plan["runtime_binding"] == final.runtime_binding()
            and plan["source_binding"] == {
                Path(__file__).name: file_binding(__file__)["sha256"],
                Path(stats.__file__).name: file_binding(stats.__file__)["sha256"]}
            and plan["old_evaluation_registration"] == protocol["old_evaluation_registration"]
            and plan["old_evaluation_summaries"] == protocol["old_evaluation_summaries"],
            "frozen V63 evaluation implementation or source registration changed")
    planned = planned_jobs()
    require(set(plan["jobs"]) == set(planned) and all(
        all(plan["jobs"][key][field] == value for field, value in job.items())
        for key, job in planned.items()), "new evaluation batch, queue or configuration changed")
    barrier = checked(checked_file(plan["training_barrier"]))
    require(barrier["protocol_id"] == protocol["id"] and len(barrier["branches"]) == 6
            and len(barrier["snapshots"]) == 6 and barrier["feedback_batch"] == FEEDBACK_BATCH,
            "all-six-new-branch training seal missing")
    for reference in barrier["branches"].values():
        checked_file(reference)
    checked_file(barrier["controller_training_barrier"])
    return plan


def job_root(root, job):
    return Path(root) / "evaluations/jobs" / job["job_id"]


def generation_root(root, job):
    return job_root(root, job) / "shards" / job["panel"] / "generation"


def inspect_job(root, plan, job, *, final=None):
    final = final or _runtime()
    return final.base.inspect_shard(job_root(root, job),
        dict(runtime_binding=plan["runtime_binding"], config=job["config"],
             model_identity=job["model_identity"], snapshot_id=plan["snapshot_id"]),
        dict(key=job["panel"], task_keys=plan["cohorts"][job["role"]]["tasks"]))


def seal_job(root, plan, job, *, final=None):
    final = final or _runtime()
    run, seal, episodes = final.sealed_episodes(generation_root(root, job))
    require(job["feedback_batch"] == FEEDBACK_BATCH
            and run["tasks"] == plan["cohorts"][job["role"]]["tasks"]
            and len(episodes) == job["denominator"] and run["config"] == job["config"]
            and run["provider"] == job["model_identity"] and run["role"] == job["role"],
            "complete registered new-batch model/panel/draw required")
    value = publish(job_root(root, job) / "whole_queue_seal/record.json", dict(
        schema="v63_b1_model_panel_draw_seal.v1", registration_id=plan["id"],
        job_id=job["job_id"], feedback_batch=FEEDBACK_BATCH,
        checkpoint=job["checkpoint"], denominator=job["denominator"],
        run_id=run["id"], generation_seal_id=seal["id"],
        generation_seal=file_binding(generation_root(root, job) / "generation_seal/seal.json"),
        episode_sha256=[digest(e) for e in episodes], all_provider_calls_settled=True,
        private_references_read=False))
    return value, episodes


def worker(root, jobid, gpu, *, execution_context=None):
    """One generation attempt; resumable native output, no private scoring."""
    root = Path(root).resolve()
    plan, final = checked_plan(root), _runtime()
    require(jobid in plan["jobs"], "unregistered V63 evaluation worker")
    job = dict(plan["jobs"][jobid], kind="generate")
    directory = job_root(root, job)
    worker_api = importlib.import_module("finqa_v63_worker")
    attempt = Path(os.environ["V63_ATTEMPT_DIR"]).resolve()
    require(attempt.parent == directory / "attempts"
            and attempt.name == os.environ["V63_ATTEMPT_ID"]
            and attempt.name.startswith("attempt") and attempt.name[7:].isdigit(),
            "evaluation requires its independent dispatched V63 attempt directory")
    try:
        with (directory / "worker.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            progress = worker_api.audit_job_resume(root, job)
            require(progress["resume_allowed"] and progress["unknown_calls"] == 0,
                    "UNKNOWN or changed evaluation state cannot be automatically resumed")
            if (directory / "result/record.json").exists():
                accepted = checked(directory / "result/record.json")
                require(accepted["registration_id"] == plan["id"]
                        and accepted["feedback_batch"] == FEEDBACK_BATCH,
                        "saved evaluation result belongs to another condition")
                seal_job(root, plan, job, final=final)
                return worker_api.reuse_complete_result(root, job, attempt)
            state = _snapshot_state(job["checkpoint"], job["seed"], 894, final)
            resource_module = importlib.import_module("finqa_v63_runtime")
            context = execution_context or resource_module.execution_context
            provider = None
            with context(root, job, gpu) as resources:
                resources.check("before_evaluation_model_load", boundary=True)
                provider = final.load_final_provider(dict(assets=plan["assets"], config=job["config"]), job, state)
                del state
                resources.check("after_evaluation_model_load", boundary=True)
                original_chat = provider.chat

                async def observed_chat(*args, **kwargs):
                    resources.check("before_evaluation_response", boundary=True)
                    return await original_chat(*args, **kwargs)

                def stopped():
                    if resources.stop.requested:
                        raise resource_module.ExplicitStop("explicit stop before next evaluation episode")

                provider.chat = observed_chat
                try:
                    asyncio.run(importlib.import_module("finqa_v56_feedback").execute_run_resumable(
                        generation_root(root, job), provider, attempt_root=attempt / "generation",
                        stop_check=stopped,
                        after_return=lambda event: resources.check("after_durable_evaluation_response", boundary=True)))
                    response_calls = provider.actual_model_calls
                finally:
                    provider.chat = original_chat
                    del provider, original_chat
                    gc.collect()
                    final.torch.cuda.empty_cache()
                resources.check("after_evaluation_model_release", boundary=True)
            resource_report = resources.report()
            seal, _ = seal_job(root, plan, job, final=final)
            result = publish(directory / "result/record.json", dict(
                schema="v63_b1_evaluation_job_result.v1", registration_id=plan["id"],
                feedback_batch=FEEDBACK_BATCH, job_id=jobid, status="COMPLETE", resources=resource_report,
                whole_queue_seal=file_binding(directory / "whole_queue_seal/record.json"),
                whole_queue_seal_id=seal["id"], sessions=job["denominator"],
                actual_new_response_calls=response_calls, new_API_calls=0,
                scoring_calls=0, private_references_read=False))
            publish(attempt / "completed/record.json", dict(
                schema="v63_evaluation_attempt_complete.v1", protocol_id=_protocol(root)["id"],
                feedback_batch=FEEDBACK_BATCH, result=file_binding(directory / "result/record.json"),
                new_actual_response_calls=response_calls))
            return result
    except BaseException as error:
        worker_api.record_attempt_failure(root, job, attempt, error)
        raise


def generation_exit_barrier(root, plan):
    """Verify all 24 accepted real exits before any reference is opened."""
    root = Path(root).resolve()
    protocol = _protocol(root)
    path = root / "evaluation_barrier/record.json"
    barrier = checked(path)
    require(barrier["protocol_id"] == protocol["id"]
            and barrier["all_24_generation_jobs_complete"] is True
            and barrier["all_dispatched_evaluation_workers_exited"] is True
            and barrier["active_children"] == []
            and set(barrier["job_results"]) == set(plan["jobs"])
            and len(plan["jobs"]) == 24,
            "all 24 generation jobs require real successful exits before any scoring")
    accepted_refs = {}
    for key, job in plan["jobs"].items():
        directory = job_root(root, job)
        result_path = directory / "result/record.json"
        result_ref = file_binding(result_path)
        require(barrier["job_results"][key] == result_ref,
                "global generation-exit barrier result bytes changed")
        result = checked(result_path)
        accepted_path = directory / "accepted/record.json"
        accepted = checked(accepted_path)
        require(accepted["protocol_id"] == protocol["id"] and accepted["job_id"] == key
                and accepted["result"] == result_ref and accepted["result_id"] == result["id"]
                and accepted["actual_exit_zero"] is True and accepted["resources_passed"] is True
                and result["registration_id"] == plan["id"] and result["job_id"] == key
                and result["status"] == "COMPLETE" and result["feedback_batch"] == FEEDBACK_BATCH
                and result["sessions"] == job["denominator"],
                "every generation result needs its own accepted successful exit and resources")
        exit_path = checked_file(accepted["actual_exit"])
        require(exit_path.resolve().is_relative_to((directory / "attempts").resolve()),
                "generation exit must belong to that job's dispatched attempt")
        exit_record = checked(exit_path)
        require(exit_record["protocol_id"] == protocol["id"] and exit_record["job_id"] == key
                and exit_record["returncode"] == 0 and exit_record["actual_waitpid_observed"] is True,
                "generation process must actually exit successfully before scoring")
        launch = checked(exit_path.parent.parent / "launch/record.json")
        require((exit_record["pid"], exit_record["birth"]) == (launch["pid"], launch["birth"]),
                "actual generation exit and dispatched worker identity differ")
        accepted_refs[key] = file_binding(accepted_path)
    return publish(root / "evaluations/all_generation_exit_seal/record.json", dict(
        schema="v63_all_24_actual_generation_exits_sealed.v1",
        protocol_id=protocol["id"], registration_id=plan["id"],
        controller_generation_barrier=file_binding(path), accepted_jobs=accepted_refs,
        generation_jobs=24, new_sessions=7458, all_provider_calls_settled=True,
        private_references_read=False))


def seal_panel(root, panel, *, plan=None, final=None):
    plan, final = plan or checked_plan(root), final or _runtime()
    require(panel in plan["contract"]["panels"], "unregistered panel cannot be scored")
    global_seal = generation_exit_barrier(root, plan)
    jobs = {key: job for key, job in plan["jobs"].items() if job["panel"] == panel}
    spec = plan["contract"]["panels"][panel]
    require(len(jobs) == 6 * len(spec["draw_seeds"]), "full six-new-model/draw matrix required")
    episodes, seals = {}, {}
    for key, job in jobs.items():
        seal, episodes[key] = seal_job(root, plan, job, final=final)
        result = checked(job_root(root, job) / "result/record.json")
        require(result["whole_queue_seal_id"] == seal["id"], "accepted generation seal changed")
        seals[key] = file_binding(job_root(root, job) / "whole_queue_seal/record.json")
    panel_seal = publish(Path(root) / "evaluations/panels" / panel / "all_generation_seal/record.json", dict(
        schema="v63_complete_new_panel_generation_seal.v1", registration_id=plan["id"],
        panel=panel, model_count=6, feedback_batch=FEEDBACK_BATCH, jobs=seals,
        sessions=spec["sessions"], global_generation_exit_seal_id=global_seal["id"],
        all_provider_calls_settled=True, private_references_read=False))
    return panel_seal, episodes, jobs


def reused_old_reports(root, panel, plan, tasks, groups):
    """Read bound old native scores, never regenerate or rescore old episodes."""
    protocol = _protocol(root)
    old_plan = _old_registration(protocol)
    old_summary = _old_summary(protocol, panel, old_plan)
    require(old_plan["snapshot_id"] == plan["snapshot_id"]
            and old_plan["cohorts"] == plan["cohorts"]
            and old_plan["contract"]["panels"][panel]["configs"]
                == plan["contract"]["panels"][panel]["configs"]
            and old_summary["denominator"] == len(tasks),
            "old and new evaluation task/draw/decoding identities must agree")
    reports = {}
    for seed in SEEDS:
        for arm in stats.original.ARMS:
            key = stats.original.coordinate(seed, arm)
            reference = old_summary["model_reports"][key]
            expected = Path(binding.OLD_ROOT) / "evaluations/panels" / panel / "models" / f"seed{seed}" / arm / "record.json"
            report = checked(_old_path(reference, expected))
            require(report["registration_id"] == old_plan["id"]
                    and report["panel"] == panel and report["seed"] == seed and report["arm"] == arm
                    and report["all_generation_seal_id"] == old_summary["all_generation_seal_id"]
                    and report["denominator"] == len(tasks)
                    and [row["task_key"] for row in report["results"]] == tasks
                    and all(row["source_group"] == groups[row["task_key"]] for row in report["results"]),
                    "old report identity, task order or original source mapping changed")
            reports[key] = dict(report,
                feedback_batch=None if arm == "Hold" else 0, reused_old_hold=arm == "Hold",
                old_model_report=reference, old_summary_id=old_summary["id"],
                old_registration_id=old_plan["id"])
    return old_summary, reports


def score(root, panel, *, contracts_complete=None):
    """All six training and all 24 generation exits precede private scoring."""
    root = Path(root).resolve()
    plan, final = checked_plan(root), _runtime()
    score_root = root / "evaluations/panels" / panel
    score_root.mkdir(parents=True, exist_ok=True)
    with (score_root / "score.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        barrier, episodes, jobs = seal_panel(root, panel, plan=plan, final=final)
        summary_path = score_root / "summary/record.json"
        if summary_path.exists():
            saved = checked(summary_path)
            require(saved["registration_id"] == plan["id"] and saved["panel"] == panel
                    and saved["feedback_batch"] == FEEDBACK_BATCH
                    and saved["all_generation_seal_id"] == barrier["id"]
                    and saved["reused_old_summary"] == plan["old_evaluation_summaries"][panel]
                    and set(saved["model_reports"]) == {
                        stats.coordinate(s, a) for s in SEEDS for a in ARMS},
                    "saved new-batch summary binding changed")
            for reference in saved["model_reports"].values():
                checked_file(reference)
            checked_file(saved["reused_old_summary"])
            return saved
        manifest, public, lineages = final.load_public_snapshot(plan["snapshot"])
        require(manifest["id"] == plan["snapshot_id"], "scoring source snapshot changed")
        spec = plan["contract"]["panels"][panel]
        cohort, draws = plan["cohorts"][spec["role"]], spec["draw_seeds"]
        tasks = [f"draw{draw}/{key}" for draw in draws for key in cohort["tasks"]]
        groups = {f"draw{draw}/{key}": cohort["source_groups"][key]
                  for draw in draws for key in cohort["tasks"]}
        old_summary, old_reports = reused_old_reports(root, panel, plan, tasks, groups)
        bundles = _panel_private_bundles(final, plan, manifest, public, lineages, set(cohort["tasks"]))
        reports, references = {}, {}
        for seed in SEEDS:
            for arm in ARMS:
                key, rows = stats.coordinate(seed, arm), []
                report_path = score_root / "models" / f"seed{seed}" / arm / "record.json"
                if report_path.exists():
                    saved = checked(report_path)
                    require(saved["registration_id"] == plan["id"] and saved["panel"] == panel
                            and saved["seed"] == seed and saved["arm"] == arm
                            and saved["feedback_batch"] == FEEDBACK_BATCH
                            and saved["all_generation_seal_id"] == barrier["id"]
                            and saved["denominator"] == len(tasks)
                            and [row["task_key"] for row in saved["results"]] == tasks
                            and saved["metrics"] == stats.native_metrics(saved["results"], len(tasks)),
                            "saved new model scores changed before summary completion")
                    reports[key], references[key] = saved, file_binding(report_path)
                    continue
                for draw in draws:
                    job = next(job for job in jobs.values()
                               if (job["seed"], job["arm"], job["draw_seed"]) == (seed, arm, draw))
                    for task, episode in zip(cohort["tasks"], episodes[job["job_id"]], strict=True):
                        rows.append(dict(
                            task_key=f"draw{draw}/{task}", original_task_key=task, draw_seed=draw,
                            native=final.score_public_reasoning_program(bundles[task], episode),
                            stop_reason=episode.stop_reason, actual_model_calls=episode.actual_model_calls,
                            tool_call_count=len(episode.tool_events),
                            generated_token_count=sum(len(turn.receipt.raw_generated_token_ids)
                                for turn in episode.turns if turn.receipt is not None),
                            source_group=cohort["source_groups"][task]))
                report = dict(schema="v63_b1_fixed_panel_native_report.v1",
                    registration_id=plan["id"], panel=panel, seed=seed, arm=arm,
                    feedback_batch=FEEDBACK_BATCH, denominator=len(tasks),
                    all_generation_seal_id=barrier["id"], results=rows,
                    metrics=stats.native_metrics(rows, len(tasks)), unknown_as_zero=False)
                reports[key] = publish(report_path, report)
                references[key] = file_binding(report_path)
        holds = {stats.original.coordinate(seed, "Hold"): old_reports[stats.original.coordinate(seed, "Hold")]
                 for seed in SEEDS}
        summary = stats.paired_summary(reports, tasks, groups, denominator=len(tasks), old_hold_reports=holds)
        replication = stats.batch_replication_diagnostics(reports, old_reports, tasks, denominator=len(tasks))
        result = dict(schema="v63_b1_fixed_panel_summary.v1", registration_id=plan["id"],
            panel=panel, primary=panel == PRIMARY_PANEL, all_generation_seal_id=barrier["id"],
            model_reports=references, reused_old_model_reports=old_summary["model_reports"],
            reused_old_summary=plan["old_evaluation_summaries"][panel],
            reused_old_batch_comparisons=old_summary["comparisons"],
            same_temperature_batch_replication=replication,
            statistics=stats.statistics_contract(), **summary,
            main_denominator_is_tasks=spec["tasks_per_draw"], draws_per_task=len(draws),
            selection_or_optional_stopping=False, old_results_rescored=False, new_API_calls=0)
        if panel == PRIMARY_PANEL and contracts_complete is not None:
            result["advancement"] = stats.advancement(summary, contracts_complete=contracts_complete)
        return publish(summary_path, result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "worker", "score"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--job")
    parser.add_argument("--gpu", type=int)
    parser.add_argument("--panel", choices=[spec[0] for spec in PANEL_SPECS])
    args = parser.parse_args()
    if args.action == "prepare":
        result = prepare_jobs(args.root)
    elif args.action == "worker":
        require(args.job is not None and args.gpu is not None, "worker job and GPU required")
        result = worker(args.root, args.job, args.gpu)
    else:
        require(args.panel is not None, "registered panel required")
        result = score(args.root, args.panel)
    print(json.dumps(dict(id=result["id"], schema=result["schema"]), sort_keys=True))


if __name__ == "__main__":
    main()
