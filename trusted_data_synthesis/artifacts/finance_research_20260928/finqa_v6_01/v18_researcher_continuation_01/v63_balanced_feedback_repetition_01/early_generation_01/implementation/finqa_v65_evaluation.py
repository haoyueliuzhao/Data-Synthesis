"""Five accepted V63 branches: unchanged public generation, no scoring.

This independently registered generation-only exception does not change the
original 24-job scientific budget or the model/panel/draw identities. The
twenty sealed artifacts must later be adopted read-only, never regenerated.
"""
from __future__ import annotations

import asyncio
import fcntl
import gc
import importlib
import os
from pathlib import Path

import finqa_v65_binding as binding

original = binding.source_module("finqa_v63_evaluation")
require, checked, publish = binding.require, binding.checked, binding.publish
digest, file_binding = binding.digest, binding.file_ref
RunConfig = original.RunConfig
PANEL_SPECS, FEEDBACK_BATCH = original.PANEL_SPECS, original.FEEDBACK_BATCH
ELIGIBLE_COORDINATES = ((137, "C1"), (137, "C05"), (251, "C1"), (251, "C05"), (389, "C1"))


def planned_jobs():
    jobs = {key: dict(job) for key, job in original.planned_jobs().items()
            if (job["seed"], job["arm"]) in ELIGIBLE_COORDINATES}
    require(len(jobs) == 20 and sum(job["denominator"] for job in jobs.values()) == 6215,
            "V65 allows exactly twenty original jobs and 6215 generation sessions")
    return jobs


def evaluation_contract():
    return dict(schema="v65_five_complete_branches_generation_only.v1",
        generation_jobs=20, total_sessions=6215, feedback_batch=1, snapshot_step=894,
        eligible_coordinates=[original.stats.coordinate(seed, arm) for seed, arm in ELIGIBLE_COORDINATES],
        deferred_coordinate=original.stats.coordinate(389, "C05"),
        original_generation_jobs=24, original_total_sessions=7458,
        original_scientific_budget_unchanged=True,
        original_model_identity_point_id_and_decoding_unchanged=True,
        explicit_generation_barrier_exception=True,
        before_generation="five eligible branches each have accepted actual exit zero and sealed step894",
        private_scoring_authorized=False, scoring_calls=0, private_references_read=False,
        summaries_and_new_accuracy_comparisons_authorized=False,
        later_full_evaluation_requires_read_only_adoption_of_these_artifacts=True,
        complete_provider_returns_and_episodes_never_regenerated=True,
        unknown_calls_block_automatic_resume=True,
        partial_results_must_not_influence_remaining_training_or_generation=True)


def _protocol(root):
    require(Path(root).resolve() == Path(binding.ROOT).resolve(),
            "V65 generation writes require their independent registered root")
    protocol = checked(Path(root) / "protocol/record.json")
    require(protocol["evaluation"] == evaluation_contract(),
            "the generation-only exception or its twenty-job dose changed")
    return protocol


def _science_protocol(protocol):
    reference = protocol["science_protocol_ref"]
    require(Path(reference["path"]).resolve() == Path(binding.SCIENTIFIC_ROOT).resolve() / "protocol/record.json",
            "original scientific protocol cannot be replaced by the early-generation protocol")
    science = binding.read_ref(reference)
    require(science["evaluation"] == original.evaluation_contract(),
            "original six-branch scientific evaluation contract changed")
    return science


def _same_reference(left, right):
    return (Path(left["path"]).resolve(), left["sha256"]) == (
        Path(right["path"]).resolve(), right["sha256"])


def _read_at(reference, expected):
    require(Path(reference["path"]).resolve() == Path(expected).resolve(),
            "eligible training evidence must retain its original scientific path")
    return binding.read_ref(reference)


def generation_barrier(root, *, branch_reader=None):
    """Validate all five independent accepted exits, not a completion boolean."""
    root = Path(root).resolve()
    protocol = _protocol(root)
    science = _science_protocol(protocol)
    scientific_root = Path(binding.SCIENTIFIC_ROOT).resolve()
    evidence = protocol["eligible_training_branches"]
    keys = {original.stats.coordinate(seed, arm) for seed, arm in ELIGIBLE_COORDINATES}
    require(set(evidence) == keys, "the early-generation exception covers exactly five complete branches")
    branches, snapshots = {}, {}
    for seed, arm in ELIGIBLE_COORDINATES:
        key = original.stats.coordinate(seed, arm)
        refs = evidence[key]
        stage = scientific_root / f"stages/seed{seed}/train_{arm}"
        branch_path = scientific_root / f"branches/seed{seed}/{arm}/completed/record.json"
        branch = _read_at(refs["branch"], branch_path)
        result = _read_at(refs["result"], stage / "result/record.json")
        accepted = _read_at(refs["accepted"], stage / "accepted/record.json")
        exit_path = Path(refs["actual_exit"]["path"]).resolve()
        require(exit_path.is_relative_to(stage / "attempts")
                and exit_path.name == "record.json" and exit_path.parent.name == "actual_exit",
                "actual training exit must belong to its dispatched attempt")
        actual = binding.read_ref(refs["actual_exit"])
        launch = _read_at(refs["launch"], exit_path.parent.parent / "launch/record.json")
        if branch_reader is not None:
            require(branch_reader(scientific_root, seed, arm) == branch,
                    "branch reader and immutable training result differ")
        jobid = f"seed{seed}.train_{arm}"
        require(branch.get("schema") == "v63_fixed_q_branch_complete.v1"
                and branch["protocol_id"] == result["protocol_id"] == accepted["protocol_id"]
                == actual["protocol_id"] == launch["protocol_id"] == science["id"]
                and branch["status"] == result["status"] == "COMPLETE"
                and (branch["seed"], branch["arm"], branch["feedback_batch"]) == (seed, arm, 1)
                and (result["seed"], result["arm"], result["stage"]) == (seed, arm, f"train_{arm}")
                and branch["optimizer_updates"] == branch["new_optimizer_updates"] == 298
                and result["optimizer_updates"] == result["new_optimizer_updates"] == 298
                and result["final_step"] == 894 and result["resources"]["all_gates_passed"] is True
                and _same_reference(result["branch_result"], refs["branch"])
                and result["branch_result"]["id"] == branch["id"],
                "each admitted model must be its original complete 298-update step894 branch")
        require(accepted["job_id"] == actual["job_id"] == jobid
                and launch["job"].get("job_id", launch["job"].get("id")) == jobid
                and accepted["result_id"] == result["id"]
                and _same_reference(accepted["result"], refs["result"])
                and _same_reference(accepted["actual_exit"], refs["actual_exit"])
                and accepted["actual_exit_zero"] is True and accepted["resources_passed"] is True
                and actual["actual_waitpid_observed"] is True and actual["returncode"] == 0
                and (actual["pid"], actual["birth"]) == (launch["pid"], launch["birth"])
                and actual["attempt"] == launch["attempt"] == accepted["attempt"],
                "every eligible branch needs its own accepted, identity-matched actual successful exit")
        reference = branch["snapshots"]["894"]
        require(reference.get("state_sha256") and reference.get("actual_state_digest")
                and reference.get("record_sha256"), "actual step894 checkpoint bytes must remain bound")
        branches[key] = refs["branch"]
        snapshots[key + "/step894"] = reference
    return publish(root / "evaluations/training_barrier/record.json", dict(
        schema="v65_five_actual_training_exits_sealed.v1", protocol_id=protocol["id"],
        scientific_protocol_id=science["id"], eligible_training_branches=evidence,
        branches=branches, snapshots=snapshots, new_branches=5, snapshot_count=5,
        feedback_batch=1, original_six_branch_barrier_not_claimed_passed=True,
        private_references_read=False, scoring_calls=0))


def _runtime():
    return original._runtime()


def _snapshot_state(reference, seed, step, final):
    require(step == 894, "V65 generation only uses the original step894 checkpoint")
    return original._snapshot_state(reference, seed, step, final)


def _implementation_binding():
    return {name: binding.sha(Path(__file__).with_name(name)) for name in
            ("finqa_v65_evaluation.py", "finqa_v65_worker.py")}


def _model_identity(final, source, reference, state, science_id, seed, arm):
    identity = next(iter(source["jobs"].values()))["model_identity"]
    return final.ModelIdentity(backend="local_torch", model_id=source["assets"]["base_binding"]["id"],
        point_id="v63-b1-evaluation:" + digest(dict(protocol_id=science_id, seed=seed, arm=arm,
            feedback_batch=1, step=894, checkpoint=reference)),
        parameter_digest=final.parameter_digest(state["parameters"]),
        tokenizer_digest=identity["tokenizer_digest"], chat_template_digest=identity["chat_template_digest"]
    ).model_dump(mode="json")


def prepare_jobs(root):
    root = Path(root).resolve()
    protocol, final = _protocol(root), _runtime()
    science, barrier = _science_protocol(protocol), generation_barrier(root)
    registration = root / "evaluations/registration/record.json"
    if registration.exists():
        plan = checked_plan(root)
    else:
        source, cohorts = original._public_source(science, final)
        old_plan = original._old_registration(science)
        require(old_plan["snapshot"] == source["snapshot"]
                and old_plan["snapshot_id"] == source["snapshot_id"]
                and old_plan["role_plan"] == source["role_plan"] and old_plan["cohorts"] == cohorts,
                "early generation must retain the original public cohorts, task order and source groups")
        for panel, *_ in PANEL_SPECS:
            require(old_plan["contract"]["panels"][panel]["configs"]
                    == science["evaluation"]["panels"][panel]["configs"],
                    "old and new generation decoding must remain identical")
        snapshot_jobs = {}
        for seed, arm in ELIGIBLE_COORDINATES:
            key = original.stats.coordinate(seed, arm) + "/step894"
            reference = barrier["snapshots"][key]
            state = _snapshot_state(reference, seed, 894, final)
            snapshot_jobs[key] = dict(checkpoint=reference,
                model_identity=_model_identity(final, source, reference, state, science["id"], seed, arm))
            del state
        jobs = {key: {**job, **snapshot_jobs[original.stats.coordinate(job["seed"], job["arm"]) + "/step894"]}
                for key, job in planned_jobs().items()}
        plan = publish(registration, dict(schema="v65_generation_only_registration.v1",
            protocol_id=protocol["id"], scientific_protocol_id=science["id"], feedback_batch=1,
            contract=evaluation_contract(), training_barrier=file_binding(
                root / "evaluations/training_barrier/record.json"),
            original_evaluation_source=science["evaluation_source_registration"],
            old_evaluation_registration=science["old_evaluation_registration"],
            assets=source["assets"], snapshot=source["snapshot"], snapshot_id=source["snapshot_id"],
            role_plan=source["role_plan"], runtime_binding=final.runtime_binding(),
            source_binding=_implementation_binding(), cohorts=cohorts, jobs=jobs,
            private_references_read=False, generation_calls=0, scoring_calls=0))
    require(binding.read_ref(plan["training_barrier"])["id"] == barrier["id"],
            "five-branch actual-exit evidence changed before generation preparation")
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
    protocol, final = _protocol(root), _runtime()
    science = _science_protocol(protocol)
    plan = checked(Path(root) / "evaluations/registration/record.json")
    require(plan["schema"] == "v65_generation_only_registration.v1"
            and plan["protocol_id"] == protocol["id"] and plan["scientific_protocol_id"] == science["id"]
            and plan["contract"] == evaluation_contract() and plan["feedback_batch"] == 1
            and plan["runtime_binding"] == final.runtime_binding()
            and plan["source_binding"] == _implementation_binding()
            and plan["original_evaluation_source"] == science["evaluation_source_registration"]
            and plan["old_evaluation_registration"] == science["old_evaluation_registration"]
            and plan["private_references_read"] is False and plan["scoring_calls"] == 0,
            "V65 frozen generation registration or original scientific sources changed")
    planned = planned_jobs()
    require(set(plan["jobs"]) == set(planned) and all(
        all(plan["jobs"][key][field] == value for field, value in job.items())
        for key, job in planned.items()), "V65 generation dose or exact decoding changed")
    barrier = binding.read_ref(plan["training_barrier"])
    require(Path(plan["training_barrier"]["path"]).resolve() ==
            Path(root).resolve() / "evaluations/training_barrier/record.json"
            and barrier["protocol_id"] == protocol["id"] and barrier["scientific_protocol_id"] == science["id"]
            and barrier["eligible_training_branches"] == protocol["eligible_training_branches"]
            and len(barrier["branches"]) == len(barrier["snapshots"]) == 5,
            "the five accepted training exits must remain bound to this registration")
    for key, job in plan["jobs"].items():
        coordinate = original.stats.coordinate(job["seed"], job["arm"])
        require(job["checkpoint"] == barrier["snapshots"][coordinate + "/step894"]
                and job["model_identity"]["point_id"] == "v63-b1-evaluation:" + digest(dict(
                    protocol_id=science["id"], seed=job["seed"], arm=job["arm"], feedback_batch=1,
                    step=894, checkpoint=job["checkpoint"])),
                "original V63 model/checkpoint identity must not become an early-generation identity")
    return plan


def job_root(root, job):
    require(Path(root).resolve() == Path(binding.ROOT).resolve(), "V65 job must stay in the independent root")
    planned = planned_jobs()
    require(job["job_id"] in planned and all(job.get(field) == value
            for field, value in planned[job["job_id"]].items()), "unregistered early-generation job")
    return Path(root).resolve() / "evaluations/jobs" / job["job_id"]


job_directory = job_root


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
    require(job["feedback_batch"] == 1 and run["tasks"] == plan["cohorts"][job["role"]]["tasks"]
            and len(episodes) == job["denominator"] and run["config"] == job["config"]
            and run["provider"] == job["model_identity"] and run["role"] == job["role"],
            "complete original model/panel/draw and exact public task order are required")
    value = publish(job_root(root, job) / "whole_queue_seal/record.json", dict(
        schema="v65_generation_only_model_panel_draw_seal.v1", registration_id=plan["id"],
        scientific_protocol_id=plan["scientific_protocol_id"], job_id=job["job_id"], feedback_batch=1,
        checkpoint=job["checkpoint"], denominator=job["denominator"], run_id=run["id"],
        generation_seal_id=seal["id"], generation_seal=file_binding(
            generation_root(root, job) / "generation_seal/seal.json"),
        episode_sha256=[digest(episode) for episode in episodes], all_provider_calls_settled=True,
        private_references_read=False, scoring_calls=0, later_read_only_adoption_required=True))
    return value, episodes


def worker(root, jobid, gpu, *, execution_context=None):
    """Only native durable generation; no private-reference or scoring path."""
    root = Path(root).resolve()
    plan, final = checked_plan(root), _runtime()
    require(jobid in plan["jobs"], "unregistered early-generation worker")
    job = dict(plan["jobs"][jobid], kind="generate")
    directory = job_root(root, job)
    worker_api = importlib.import_module("finqa_v65_worker")
    attempt = worker_api.checked_attempt_directory(root, job, os.environ.get("V63_ATTEMPT_DIR"))
    try:
        with (directory / "worker.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            progress = worker_api.audit_job_resume(root, job)
            require(progress["resume_allowed"] and progress["unknown_calls"] == 0,
                    "UNKNOWN or changed evaluation state cannot be automatically resumed")
            if (directory / "result/record.json").exists():
                seal_job(root, plan, job, final=final)
                return worker_api.reuse_complete_result(root, job, attempt)
            state = _snapshot_state(job["checkpoint"], job["seed"], 894, final)
            resource_module = importlib.import_module("finqa_v65_runtime")
            context = execution_context or resource_module.execution_context
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
                    durable = binding.source_module("finqa_v63_worker_audit").durable
                    asyncio.run(durable.execute_run_resumable(
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
                schema="v65_generation_only_job_result.v1", registration_id=plan["id"],
                scientific_protocol_id=plan["scientific_protocol_id"], feedback_batch=1,
                job_id=jobid, status="COMPLETE", resources=resource_report,
                whole_queue_seal=file_binding(directory / "whole_queue_seal/record.json"),
                whole_queue_seal_id=seal["id"], sessions=job["denominator"],
                actual_new_response_calls=response_calls, new_API_calls=0,
                scoring_calls=0, private_references_read=False))
            publish(attempt / "completed/record.json", dict(
                schema="v65_generation_only_attempt_complete.v1", protocol_id=_protocol(root)["id"],
                feedback_batch=1, result=file_binding(directory / "result/record.json"),
                new_actual_response_calls=response_calls, private_references_read=False, scoring_calls=0))
            return result
    except BaseException as error:
        worker_api.record_attempt_failure(root, job, attempt, error)
        raise
