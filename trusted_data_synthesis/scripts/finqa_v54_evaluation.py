"""V54 sealed 745/894 panels using the original public harness and native metric.

Registration and progress inspect public artifacts only. No generation can start
before all nine logical branches and eighteen actual snapshots are sealed. Each
predeclared panel is complete across all arms/seeds/draws before private scoring.
"""

from __future__ import annotations

import argparse
import asyncio
import fcntl
import gc
import hashlib
import importlib
import json
import os
import sys
from pathlib import Path

import finqa_v54_statistics as stats

# The original training loader rejects a mixed workspace/frozen package. Set
# the source before importing even lightweight contracts or storage helpers.
FROZEN_SOURCE = Path("/data1/zhuxinrui/projects/Data-Synthesis/.codex-worktrees/"
                    "finqa-v18-researcher-continuation-20260930/trusted_data_synthesis/src")
for _name, _module in tuple(sys.modules.items()):
    if _name == "trusted_synthesis" or _name.startswith("trusted_synthesis."):
        _file = getattr(_module, "__file__", None)
        if _file is not None and not Path(_file).resolve().is_relative_to(FROZEN_SOURCE.resolve()):
            raise ValueError("V54 evaluation rejects an already imported non-frozen scientific package")
sys.path.insert(0, str(FROZEN_SOURCE))

from trusted_synthesis.finance_research.contracts import RunConfig, digest
from trusted_synthesis.finance_research.storage import read_json
from trusted_synthesis.core.immutable_artifacts import write_immutable_artifact_directory

SEEDS, ARMS = stats.SEEDS, stats.ARMS
require = stats.require
GREEDY_SEED = 20260928
DRAW_SEEDS = (11, 29)
PANEL_SPECS = (
    ("step745_calibration120_greedy", 745, "calibration", 120, (GREEDY_SEED,), 0.0),
    ("step894_calibration120_greedy", 894, "calibration", 120, (GREEDY_SEED,), 0.0),
    ("step894_calibration120_random_T1", 894, "calibration", 120, DRAW_SEEDS, 1.0),
    ("step894_dev883_greedy", 894, "development", 883, (GREEDY_SEED,), 0.0),
)
PRIMARY_PANEL = "step894_dev883_greedy"


def bound(value):
    return {**value, "id": digest(value)}


def checked(path):
    value = read_json(path)
    require(value.get("id") == digest({k: v for k, v in value.items() if k != "id"}),
            "immutable V54 record identity changed: " + str(path))
    return value


def file_binding(path):
    path = Path(path).resolve()
    return dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def checked_file(reference):
    require(file_binding(reference["path"])["sha256"] == reference["sha256"],
            "registered evaluation artifact bytes changed")
    return Path(reference["path"])


def publish(path, value):
    path = Path(path)
    value = value if "id" in value else bound(value)
    if path.exists():
        require(read_json(path) == value, "cannot replace immutable evaluation evidence")
    else:
        write_immutable_artifact_directory(path.parent, {path.name: json.dumps(
            value, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False).encode()})
    return value


def panel_config(panel_id, draw_seed):
    spec = next((s for s in PANEL_SPECS if s[0] == panel_id), None)
    require(spec is not None and draw_seed in spec[4], "unregistered evaluation panel/draw")
    return RunConfig(harness_id="bigfinance-derived-vtdo-v7",
        submission_profile="finqa-public-reasoning-v2", role=spec[2], tier="EVAL_NATIVE",
        local_tool_protocol="qwen2.5-native-tool-call-v1", seed=draw_seed,
        temperature=spec[5], top_p=1, top_k=0, max_steps=32, max_new_tokens=2048,
        context_limit=24576, api_model="deepseek-flash")


def evaluation_contract():
    panels = {name: dict(step=step, role=role, tasks_per_draw=n, draw_seeds=list(draws),
        temperature=temperature, models=9, sessions=9 * n * len(draws),
        configs={str(d): panel_config(name, d).model_dump(mode="json") for d in draws},
        purpose="primary" if name == PRIMARY_PANEL else "predeclared diagnosis")
        for name, step, role, n, draws, temperature in PANEL_SPECS}
    return dict(schema="v54_fixed_evaluation_contract.v1", seeds=list(SEEDS), arms=list(ARMS),
        panels=panels, primary_panel=PRIMARY_PANEL, total_sessions=12267,
        new_feedback_sessions=2100, total_new_sessions_including_feedback=14367,
        logical_training_branches=9, required_snapshot_count=18, generation_jobs=45,
        before_any_generation="all nine branches complete and eighteen 745/894 snapshots sealed",
        before_any_private_scoring="entire predeclared panel across all nine models and draws sealed",
        stochastic_temperature_identical_for_all_arms=1.0,
        step745_checkpoint_selection=False, old_test1147_new_generation=0,
        API_calls=0, native_scorer_reused=True, unknown_as_zero=False,
        partial_results_must_not_influence_remaining_training_or_generation=True,
        statistics=stats.statistics_contract())


def planned_jobs():
    result = {}
    for panel_id, step, role, n, draws, _ in PANEL_SPECS:
        for seed in SEEDS:
            for arm in ARMS:
                for draw in draws:
                    key = f"{panel_id}_seed{seed}_{arm}_draw{draw}"
                    result[key] = dict(job_id=key, stage="generate", memory_phase="generate",
                        seed=seed, arm=arm, panel=panel_id, step=step, draw_seed=draw,
                        role=role, denominator=n, config=panel_config(panel_id, draw).model_dump(mode="json"))
    require(len(result) == 45 and sum(j["denominator"] for j in result.values()) == 12267,
            "V54 evaluation dose changed")
    return result


def _runtime():
    _training().runtime()
    return importlib.import_module("trusted_synthesis.finance_research.v9_final_evaluation")


def _training():
    return importlib.import_module("finqa_v54_training")


def _protocol(root):
    protocol = checked(Path(root) / "protocol/record.json")
    require(protocol["evaluation"] == evaluation_contract(), "prospective evaluation contract changed")
    return protocol


def generation_barrier(root, *, branch_reader=None):
    root = Path(root).resolve()
    protocol = _protocol(root)
    controller_seal_path = root / "training_barrier/record.json"
    controller_seal = checked(controller_seal_path)
    require(controller_seal["protocol_id"] == protocol["id"]
            and controller_seal["all_nine_logical_branches_complete"] is True
            and controller_seal["all_18_snapshots_sealed"] is True
            and controller_seal["all_dispatched_training_workers_exited"] is True
            and controller_seal["active_children"] == [],
            "controller must seal successful training exits before evaluation generation")
    reader = branch_reader or _training().checked_branch_result
    branches, snapshots = {}, {}
    for seed in SEEDS:
        for arm in ARMS:
            key = stats.coordinate(seed, arm)
            result = reader(root, seed, arm)
            require(result["status"] == "COMPLETE" and result["seed"] == seed
                    and result["arm"] == arm and result["optimizer_updates"] == 298
                    and set(result["snapshots"]) == {"745", "894"},
                    "all nine complete fixed-window branches and both snapshots are required")
            path = root / "branches" / f"seed{seed}" / arm / "completed/record.json"
            require(checked(path) == result, "branch reader and durable completed record differ")
            branches[key] = file_binding(path)
            recorded = controller_seal["branch_records"][key]
            require(Path(recorded["path"]).resolve() == path.resolve()
                    and recorded["sha256"] == branches[key]["sha256"],
                    "controller training-exit seal and branch results differ")
            for step in (745, 894):
                reference = result["snapshots"][str(step)]
                require(reference.get("state_sha256") and reference.get("actual_state_digest")
                        and reference.get("record_sha256"), "actual snapshot bytes must be bound")
                snapshots[f"{key}/step{step}"] = reference
    require(len(branches) == 9 and len(snapshots) == 18, "complete training barrier required")
    return publish(root / "evaluations/training_barrier/record.json", dict(
        schema="v54_all_training_and_snapshots_sealed.v1", protocol_id=protocol["id"],
        controller_training_barrier=file_binding(controller_seal_path),
        branches=branches, snapshots=snapshots, logical_branches=9, snapshot_count=18,
        generation_started=False, private_references_read=False))


def _public_source(protocol, final):
    source_ref = protocol["evaluation_source_registration"]
    source = checked(checked_file(source_ref))
    require(source["config"] == final.base.evaluation_config().model_dump(mode="json"),
            "original greedy harness or token limits changed")
    current = final.runtime_binding()
    require(all(current.get(name) == sha for name, sha in source["evaluation_source_sha256"].items()),
            "original parser, public harness, provider or native metric source changed")
    manifest, public, lineages = final.load_public_snapshot(source["snapshot"])
    require(manifest["id"] == source["snapshot_id"], "original public snapshot changed")
    final.verify_role_plan(source["role_plan"], public, lineages)
    cohorts = {}
    for role, denominator in (("calibration", 120), ("development", 883)):
        chosen = [(t, lineage) for t, lineage in zip(public, lineages, strict=True)
                  if source["role_plan"]["assignments"][final.task_key(t)] == role]
        require(len(chosen) == denominator and all(t.dataset == "finqa" for t, _ in chosen),
                "fixed original calibration120/dev883 role roster changed")
        keys = [final.task_key(t) for t, _ in chosen]
        if role == "development":
            require(keys == source["tasks"] and all(l.original_split == "dev" for _, l in chosen),
                    "complete original dev883 order required")
        cohorts[role] = dict(tasks=keys, denominator=denominator,
            source_groups={final.task_key(t): dict(group=l.source_group, level=l.source_group_level)
                           for t, l in chosen})
    return source, cohorts


def _snapshot_state(reference, seed, step, final):
    path = Path(reference["path"])
    require(hashlib.sha256((path / "record.json").read_bytes()).hexdigest() == reference["record_sha256"]
            and hashlib.sha256((path / "state.pt").read_bytes()).hexdigest() == reference["state_sha256"],
            "sealed 745/894 checkpoint bytes changed")
    state = final.torch.load(path / "state.pt", map_location="cpu", weights_only=False)
    require(state["seed"] == seed and state["step"] == step
            and state["schema"] == "v8_committed_training_state.v1"
            and final._tree_digest(state) == reference["actual_state_digest"],
            "actual checkpoint is not the registered real training point")
    return state


def prepare_jobs(root):
    """Materialize the fixed 45 runs only after the complete training barrier."""
    root = Path(root).resolve()
    protocol = _protocol(root)
    barrier = generation_barrier(root)
    final = _runtime()
    registration = root / "evaluations/registration/record.json"
    if registration.exists():
        plan = checked_plan(root)
    else:
        source, cohorts = _public_source(protocol, final)
        original_identity = next(iter(source["jobs"].values()))["model_identity"]
        snapshot_jobs = {}
        for seed in SEEDS:
            for arm in ARMS:
                for step in (745, 894):
                    key = f"{stats.coordinate(seed, arm)}/step{step}"
                    ref = barrier["snapshots"][key]
                    state = _snapshot_state(ref, seed, step, final)
                    identity = final.ModelIdentity(backend="local_torch",
                        model_id=source["assets"]["base_binding"]["id"],
                        point_id="v54-evaluation:" + digest(dict(protocol_id=protocol["id"],
                            seed=seed, arm=arm, step=step, checkpoint=ref)),
                        parameter_digest=final.parameter_digest(state["parameters"]),
                        tokenizer_digest=original_identity["tokenizer_digest"],
                        chat_template_digest=original_identity["chat_template_digest"])
                    snapshot_jobs[key] = dict(checkpoint=ref, model_identity=identity.model_dump(mode="json"))
                    del state
        jobs = {key: {**job, **snapshot_jobs[f"{stats.coordinate(job['seed'], job['arm'])}/step{job['step']}"]}
                for key, job in planned_jobs().items()}
        plan = publish(registration, dict(schema="v54_evaluation_registration.v1",
            protocol_id=protocol["id"], contract=evaluation_contract(),
            training_barrier=file_binding(root / "evaluations/training_barrier/record.json"),
            original_evaluation_source=protocol["evaluation_source_registration"],
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
            continue
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
            and plan["runtime_binding"] == final.runtime_binding()
            and plan["source_binding"] == {Path(__file__).name: file_binding(__file__)["sha256"],
                                          Path(stats.__file__).name: file_binding(stats.__file__)["sha256"]},
            "frozen V54 evaluation implementation or registration changed")
    require(set(plan["jobs"]) == set(planned_jobs()) and all(
        all(plan["jobs"][key][k] == v for k, v in job.items()) for key, job in planned_jobs().items()),
        "registered evaluation queue/configuration changed")
    barrier = checked(checked_file(plan["training_barrier"]))
    require(barrier["protocol_id"] == protocol["id"] and len(barrier["branches"]) == 9
            and len(barrier["snapshots"]) == 18, "all-branch training seal missing")
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
    require(run["tasks"] == plan["cohorts"][job["role"]]["tasks"]
            and len(episodes) == job["denominator"] and run["config"] == job["config"]
            and run["provider"] == job["model_identity"] and run["role"] == job["role"],
            "complete registered model/panel/draw required")
    value = publish(job_root(root, job) / "whole_queue_seal/record.json", dict(
        schema="v54_model_panel_draw_seal.v1", registration_id=plan["id"],
        job_id=job["job_id"], checkpoint=job["checkpoint"], denominator=job["denominator"],
        run_id=run["id"], generation_seal_id=seal["id"],
        generation_seal=file_binding(generation_root(root, job) / "generation_seal/seal.json"),
        episode_sha256=[digest(e) for e in episodes], all_provider_calls_settled=True,
        private_references_read=False))
    return value, episodes


def worker(root, jobid, gpu, *, execution_context=None):
    root = Path(root).resolve()
    protocol = _protocol(root)
    if "auto_recovery_policy" not in protocol:
        return _worker(root, jobid, gpu, execution_context=execution_context)
    require(jobid in planned_jobs(), "unregistered automatic evaluation job")
    job = dict(planned_jobs()[jobid], kind="generate")
    attempt = Path(os.environ["V56_ATTEMPT_DIR"]).resolve()
    require(attempt.parent == job_root(root, job) / "attempts"
            and attempt.name == os.environ["V56_ATTEMPT_ID"]
            and attempt.name.startswith("attempt") and attempt.name[7:].isdigit(),
            "automatic evaluation requires its dispatched independent attempt directory")
    try:
        return _worker(root, jobid, gpu, execution_context=execution_context, attempt_root=attempt)
    except BaseException as error:
        importlib.import_module("finqa_v56_worker").record_attempt_failure(root, job, attempt, error)
        raise


def _worker(root, jobid, gpu, *, execution_context=None, attempt_root=None):
    """One local GPU job, delegated resource lease/monitor, and no private scoring."""
    root = Path(root).resolve()
    plan, final = checked_plan(root), _runtime()
    require(jobid in plan["jobs"], "unregistered evaluation worker")
    job = plan["jobs"][jobid]
    directory = job_root(root, job)
    with (directory / "worker.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        automatic = attempt_root is not None
        if automatic:
            progress = importlib.import_module("finqa_v56_worker").audit_job_resume(root, dict(job, kind="generate"))
            require(progress["resume_allowed"] and progress["unknown_calls"] == 0,
                    "UNKNOWN or changed evaluation state cannot be automatically resumed")
        else:
            progress = inspect_job(root, plan, job, final=final)
        if not automatic and progress["sealed"]:
            require((directory / "result/record.json").exists(),
                    "sealed generation without accepted resource result needs explicit disposition")
            accepted = checked(directory / "result/record.json")
            seal, _ = seal_job(root, plan, job, final=final)
            require(accepted["whole_queue_seal_id"] == seal["id"], "accepted generation seal changed")
            return accepted
        state = _snapshot_state(job["checkpoint"], job["seed"], job["step"], final)
        if automatic and (directory / "result/record.json").exists():
            accepted = checked(directory / "result/record.json")
            require(accepted["registration_id"] == plan["id"], "saved evaluation result registration changed")
            seal_job(root, plan, job, final=final)
            del state
            return importlib.import_module("finqa_v56_worker").reuse_complete_result(
                root, dict(job, kind="generate"), attempt_root)
        resource_module = importlib.import_module("finqa_v56_runtime" if automatic else "finqa_v54_runtime")
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
                result = await original_chat(*args, **kwargs)
                if not automatic:
                    resources.check("after_evaluation_response", boundary=True)
                return result

            provider.chat = observed_chat
            try:
                if automatic:
                    def stopped():
                        if resources.stop.requested:
                            raise resource_module.ExplicitStop("explicit stop before next evaluation episode")

                    asyncio.run(importlib.import_module("finqa_v56_feedback").execute_run_resumable(
                        generation_root(root, job), provider, attempt_root=attempt_root / "generation",
                        stop_check=stopped,
                        after_return=lambda event: resources.check("after_durable_evaluation_response", boundary=True)))
                else:
                    asyncio.run(final.execute_run(generation_root(root, job), provider))
                response_calls = provider.actual_model_calls
            finally:
                provider.chat = original_chat
                del provider, original_chat
                gc.collect()
                final.torch.cuda.empty_cache()
            resources.check("after_evaluation_model_release", boundary=True)
        resource_report = resources.report()
        seal, _ = seal_job(root, plan, job, final=final)
        result = publish(directory / "result/record.json", dict(schema="v54_evaluation_job_result.v1",
            registration_id=plan["id"], job_id=jobid, status="COMPLETE", resources=resource_report,
            whole_queue_seal=file_binding(directory / "whole_queue_seal/record.json"),
            whole_queue_seal_id=seal["id"], sessions=job["denominator"],
            actual_new_response_calls=response_calls, new_API_calls=0,
            scoring_calls=0, private_references_read=False))
        if automatic:
            publish(attempt_root / "completed/record.json", dict(
                schema="v56_evaluation_attempt_complete.v1", protocol_id=_protocol(root)["id"],
                result=file_binding(directory / "result/record.json"), new_actual_response_calls=response_calls))
        return result


def seal_panel(root, panel, *, plan=None, final=None):
    plan, final = plan or checked_plan(root), final or _runtime()
    require(panel in plan["contract"]["panels"], "unregistered panel cannot be scored")
    jobs = {key: job for key, job in plan["jobs"].items() if job["panel"] == panel}
    spec = plan["contract"]["panels"][panel]
    require(len(jobs) == 9 * len(spec["draw_seeds"]), "full panel model/draw matrix required")
    episodes, seals = {}, {}
    for key, job in jobs.items():
        accepted = checked(job_root(root, job) / "result/record.json")
        require(accepted["status"] == "COMPLETE" and accepted["registration_id"] == plan["id"]
                and accepted["job_id"] == key, "accepted generation resource result required")
        _, episodes[key] = seal_job(root, plan, job, final=final)
        seals[key] = file_binding(job_root(root, job) / "whole_queue_seal/record.json")
    barrier = publish(Path(root) / "evaluations/panels" / panel / "all_generation_seal/record.json",
        dict(schema="v54_complete_panel_generation_seal.v1", registration_id=plan["id"],
             panel=panel, model_count=9, jobs=seals, sessions=spec["sessions"],
             all_provider_calls_settled=True, private_references_read=False))
    return barrier, episodes, jobs


def _panel_private_bundles(final, plan, manifest, public, lineages, wanted):
    """Verify the original file, parsing only this sealed panel's reference rows.

    The original snapshot is ordered by public task. Unselected references,
    including test1147, are never deserialized or passed to the scorer.
    """
    raw = (Path(plan["snapshot"]) / "private.references.jsonl").read_bytes()
    require(hashlib.sha256(raw).hexdigest()
            == manifest["files"]["private.references.jsonl"]["sha256"],
            "private reference file differs from original snapshot")
    lines = raw.splitlines()
    require(len(lines) == len(public) == len(lineages), "private/public snapshot row alignment changed")
    bundles = {}
    for task, lineage, line in zip(public, lineages, lines, strict=True):
        key = final.task_key(task)
        if key in wanted:
            reference = final.PrivateReference.model_validate_json(line)
            bundles[key] = final.TaskBundle(public=task, reference=reference, lineage=lineage)
    require(set(bundles) == wanted, "full fixed private scoring cohort required")
    return bundles


def score(root, panel, *, contracts_complete=None):
    """Open references only after every predeclared panel member has been sealed."""
    root = Path(root).resolve()
    plan, final = checked_plan(root), _runtime()
    score_root = root / "evaluations/panels" / panel
    score_root.mkdir(parents=True, exist_ok=True)
    with (score_root / "score.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        barrier, episodes, jobs = seal_panel(root, panel, plan=plan, final=final)
        manifest, public, lineages = final.load_public_snapshot(plan["snapshot"])
        require(manifest["id"] == plan["snapshot_id"], "scoring source snapshot changed")
        spec = plan["contract"]["panels"][panel]
        cohort = plan["cohorts"][spec["role"]]
        wanted = set(cohort["tasks"])
        bundles = _panel_private_bundles(final, plan, manifest, public, lineages, wanted)
        reports, bindings = {}, {}
        draws = spec["draw_seeds"]
        tasks = [f"draw{draw}/{key}" for draw in draws for key in cohort["tasks"]]
        groups = {f"draw{draw}/{key}": cohort["source_groups"][key]
                  for draw in draws for key in cohort["tasks"]}
        for seed in SEEDS:
            for arm in ARMS:
                key = stats.coordinate(seed, arm)
                rows = []
                for draw in draws:
                    job = next(job for job in jobs.values()
                               if (job["seed"], job["arm"], job["draw_seed"]) == (seed, arm, draw))
                    for task, episode in zip(cohort["tasks"], episodes[job["job_id"]], strict=True):
                        rows.append(dict(task_key=f"draw{draw}/{task}", original_task_key=task,
                            draw_seed=draw, native=final.score_public_reasoning_program(bundles[task], episode),
                            stop_reason=episode.stop_reason, actual_model_calls=episode.actual_model_calls,
                            tool_call_count=len(episode.tool_events),
                            generated_token_count=sum(len(turn.receipt.raw_generated_token_ids)
                                for turn in episode.turns if turn.receipt is not None),
                            source_group=cohort["source_groups"][task]))
                report = dict(schema="v54_fixed_panel_native_report.v1", registration_id=plan["id"],
                    panel=panel, seed=seed, arm=arm, denominator=len(tasks),
                    all_generation_seal_id=barrier["id"], results=rows,
                    metrics=stats.native_metrics(rows, len(tasks)), unknown_as_zero=False)
                reports[key] = publish(score_root / "models" / f"seed{seed}" / arm / "record.json", report)
                bindings[key] = file_binding(score_root / "models" / f"seed{seed}" / arm / "record.json")
        summary = stats.paired_summary(reports, tasks, groups, denominator=len(tasks))
        result = dict(schema="v54_fixed_panel_summary.v1", registration_id=plan["id"], panel=panel,
            primary=panel == PRIMARY_PANEL, all_generation_seal_id=barrier["id"],
            model_reports=bindings, statistics=stats.statistics_contract(), **summary,
            main_denominator_is_tasks=spec["tasks_per_draw"], draws_per_task=len(draws),
            selection_or_optional_stopping=False, new_API_calls=0)
        # Eligibility is recomputed by the controller after *all* scientific
        # contracts are checked; a diagnostic panel can never nominate a point.
        if panel == PRIMARY_PANEL and contracts_complete is not None:
            result["advancement"] = stats.advancement(summary, contracts_complete=contracts_complete)
        return publish(score_root / "summary/record.json", result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "worker", "score"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--job")
    parser.add_argument("--gpu", type=int)
    parser.add_argument("--panel", choices=[s[0] for s in PANEL_SPECS])
    args = parser.parse_args()
    if args.action == "prepare":
        value = prepare_jobs(args.root)
    elif args.action == "worker":
        require(args.job is not None and args.gpu is not None, "worker job and GPU required")
        value = worker(args.root, args.job, args.gpu)
    else:
        require(args.panel is not None, "complete registered scoring panel required")
        value = score(args.root, args.panel)
    print(json.dumps(dict(id=value["id"], schema=value["schema"]), sort_keys=True))


if __name__ == "__main__":
    main()
