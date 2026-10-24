"""Three fixed greedy endpoints, then one all-exits-gated CPU-only analysis.

Imports are deliberately lazy. The historical native harness/scorer is reused,
but its fixed step894/C-only checkpoint loader and multi-arm selection are not.
"""
from __future__ import annotations

import asyncio
import gc
import importlib
from pathlib import Path

import finqa_v71_binding as binding

require, checked, publish = binding.require, binding.checked, binding.publish
GREEDY_SEED = 20260928
PANELS = ((1192, "calibration", 120), (1490, "calibration", 120), (1490, "development", 883))


def _original():
    return binding.source_module("finqa_v63_evaluation")


def _runtime():
    return _original()._runtime()


def panel_config(role):
    require(role in ("calibration", "development"), "only original cal/dev greedy cohorts")
    return dict(harness_id="bigfinance-derived-vtdo-v7", submission_profile="finqa-public-reasoning-v2",
                local_tool_protocol="qwen2.5-native-tool-call-v1", max_steps=32, max_new_tokens=2048,
                context_limit=24576, temperature=0.0, top_p=1.0, top_k=0, seed=GREEDY_SEED,
                tier="EVAL_NATIVE", role=role, api_model="deepseek-flash")


def planned_jobs():
    jobs = {}
    for step, role, denominator in PANELS:
        key = f"step{step}.{'cal' if role == 'calibration' else 'dev'}_greedy"
        jobs[key] = dict(job_id=key, id=key, kind="generate", memory_phase="generate", stage="generate",
                         seed=137, arm="Fixed894", step=step, role=role, denominator=denominator,
                         draw_seed=GREEDY_SEED, panel=key, config=panel_config(role))
    return jobs


def evaluation_contract():
    return dict(schema="v71_single_path_fixed_endpoint_evaluation.v1", jobs=planned_jobs(),
                generation_jobs=3, total_sessions=1123, calibration_sessions=240,
                development_sessions=883, baseline_step=894, baseline_seed=137,
                baseline_arm="C1", baseline_feedback_batch=1, baseline_EA_correct=dict(calibration=67, development=525),
                baseline_regeneration=False, baseline_rescoring=False, Full_regeneration=False, Full_rescoring=False, final_endpoint=1490,
                applied_new_outer_updates=0, condition="fixed_pi894",
                main_estimands=dict(adaptive="(Full1490_correct-Fixed1490_correct)/883",
                                    fixed="(Fixed1490_correct-baseline894_correct)/883"),
                fixed_native_state_arm="C-only", comparator_uses_more_total_compute=True,
                dev1192_evaluated=False, per_update_C_or_N_effect_identified=False,
                before_generation="corresponding preceding 298-update train worker accepted actual exit zero",
                before_private_scoring="all 5 training/generation jobs accepted actual exit zero",
                intermediate_score_selection=False, partial_scores_influence_training=False,
                stochastic_evaluation=False, test_evaluation=False, source_cluster_bootstrap=False,
                cross_seed_confidence_interval=False, full_denominators=True, unknown_as_zero=False,
                native_scorer_reused=True, automatic_extension=False,
                canonical_episode_encoding="native Episode.model_dump(mode=json)",
                complete_returns_never_regenerated=True, unknown_call_auto_retry=False,
                independent_cpu_analysis=dict(max_RSS_GiB=64, minimum_effective_host_free_GiB=96,
                                              CUDA_visible_devices="", controller_observes_actual_exit=True),
                single_parent_conditional_path_difference=True, development_evidence_only=True)


def canonical_episode_payload(episode):
    value = episode if isinstance(episode, dict) else episode.model_dump(mode="json")
    require(isinstance(value, dict), "native Episode must serialize to a JSON object")
    return value


def canonical_episode_hash(episode):
    return binding.digest(canonical_episode_payload(episode))


def _protocol(root):
    require(Path(root).resolve() == binding.ROOT.resolve(), "foreign V71 evaluation root")
    protocol = checked(Path(root) / "protocol/record.json")
    require(protocol["evaluation"] == evaluation_contract(), "fixed V71 evaluation contract changed")
    return protocol


def _job(job):
    planned = planned_jobs()
    require(job["job_id"] in planned and all(job.get(k) == v for k, v in planned[job["job_id"]].items()),
            "unregistered endpoint, dose or decoding")
    return planned[job["job_id"]]


def job_root(root, job):
    return Path(root) / "evaluations/jobs" / job["job_id"]


def generation_root(root, job):
    return job_root(root, job) / "shards" / job["panel"] / "generation"


def _same_reference(left, right):
    return Path(left["path"]).resolve() == Path(right["path"]).resolve() and left["sha256"] == right["sha256"]


def _check_stop(root):
    require(not (Path(root) / "STOP").exists()
            and not (Path(root) / "control/stop_requested/record.json").exists(),
            "explicit STOP forbids continuing CPU evaluation analysis")


def _accepted(root, job_id, directory, protocol):
    accepted = checked(directory / "accepted/record.json")
    result = binding.read_ref(accepted["result"])
    actual = binding.read_ref(accepted["actual_exit"])
    exit_path = Path(accepted["actual_exit"]["path"]).resolve()
    require(exit_path.is_relative_to((directory / "attempts").resolve()), "actual exit escaped its job")
    launch = checked(exit_path.parent.parent / "launch/record.json")
    require(accepted["protocol_id"] == result["protocol_id"] == actual["protocol_id"] == protocol["id"]
            and accepted["job_id"] == result["job_id"] == actual["job_id"] == job_id
            and accepted["actual_exit_zero"] is True and accepted["resources_passed"] is True
            and result["status"] == "COMPLETE" and accepted["result_id"] == result["id"]
            and actual["returncode"] == 0 and actual["actual_waitpid_observed"] is True
            and (actual["pid"], actual["birth"]) == (launch["pid"], launch["birth"])
            and _same_reference(accepted["result"], binding.entry(directory / "result/record.json")),
            "job needs bound result, resource acceptance and identity-matched actual exit zero")
    return accepted, result


def _training_snapshot(root, job, protocol):
    start = job["step"] - 298
    directory = Path(root) / "points" / f"step{start:04d}" / "train"
    accepted, result = _accepted(root, f"step{start}.train", directory, protocol)
    completed = checked(directory / "completed/record.json")
    require(completed["protocol_id"] == protocol["id"] and completed["status"] == "COMPLETE"
            and completed["seed"] == 137 and completed["arm"] == "Fixed894"
            and completed["initial_step"] == start and completed["final_step"] == job["step"]
            and completed["optimizer_updates"] == 298 and completed["outer_updates"] == 0
            and completed["fixed_distribution_digest"] == completed["distribution_digest"]
            and result["final_checkpoint"] == completed["final_checkpoint"]
            and _same_reference(result["branch_result"], binding.entry(directory / "completed/record.json")),
            "generation requires exactly the registered completed fixed-distribution training window")
    return completed["final_checkpoint"], dict(accepted=binding.entry(directory / "accepted/record.json"),
        result=accepted["result"], completed=binding.entry(directory / "completed/record.json"))


def _snapshot_state(reference, step):
    training = importlib.import_module("finqa_v71_training")
    _, rt = training.runtime()
    state = training.read_checkpoint(reference, rt)
    state = training.validate_point_state(state, step, rt)
    context = checked(binding.ROOT / "points/step0894/context/record.json")
    training.assert_fixed_state(state, context, rt)
    return state


def _prepare(root, job, protocol, final):
    reference, train_binding = _training_snapshot(root, job, protocol)
    path = job_root(root, job) / "registration/record.json"
    if path.exists():
        plan = checked(path)
        require(plan["protocol_id"] == protocol["id"] and plan["job"] == _job(job)
                and plan["checkpoint"] == reference and plan["training"] == train_binding
                and plan["runtime_binding"] == final.runtime_binding(), "saved evaluation registration changed")
        return plan
    source, cohorts = _original()._public_source(protocol, final)
    old_panel = "step894_calibration120_greedy" if job["role"] == "calibration" else "step894_dev883_greedy"
    require(job["config"] == _original().panel_config(old_panel, GREEDY_SEED).model_dump(mode="json"),
            "registered decoding differs from the original greedy cohort")
    state = _snapshot_state(reference, job["step"])
    original_identity = next(iter(source["jobs"].values()))["model_identity"]
    identity = final.ModelIdentity(backend="local_torch", model_id=source["assets"]["base_binding"]["id"],
        point_id="v71-Fixed894-evaluation:" + binding.digest(dict(protocol_id=protocol["id"],
            seed=137, arm="Fixed894", step=job["step"], checkpoint=reference)),
        parameter_digest=final.parameter_digest(state["parameters"]),
        tokenizer_digest=original_identity["tokenizer_digest"],
        chat_template_digest=original_identity["chat_template_digest"]).model_dump(mode="json")
    del state
    gc.collect()
    return publish(path, dict(schema="v71_endpoint_generation_registration.v1", protocol_id=protocol["id"],
        job=_job(job), checkpoint=reference, training=train_binding, model_identity=identity,
        assets=source["assets"], snapshot=source["snapshot"], snapshot_id=source["snapshot_id"],
        role_plan=source["role_plan"], cohort=cohorts[job["role"]], runtime_binding=final.runtime_binding(),
        source_registration=protocol["evaluation_source_registration"], private_references_read=False))


def _inspect(root, job, plan, final):
    return final.base.inspect_shard(job_root(root, job),
        dict(runtime_binding=plan["runtime_binding"], config=job["config"],
             model_identity=plan["model_identity"], snapshot_id=plan["snapshot_id"]),
        dict(key=job["panel"], task_keys=plan["cohort"]["tasks"]))


def audit_job_resume(root, job):
    _job(job)
    directory = generation_root(root, job)
    if not (directory / "run.json").exists():
        return dict(resume_allowed=True, unknown_calls=0, progress_units=0, evidence=[],
                    durable_progress_digest=binding.digest([]), complete_stage=False)
    protocol = _protocol(root)
    plan = checked(job_root(root, job) / "registration/record.json")
    require(plan["protocol_id"] == protocol["id"] and plan["job"] == _job(job), "resume registration changed")
    final = _runtime()
    _inspect(root, job, plan, final)
    return binding.old_module("finqa_v56_feedback").audit_resume(directory)


def _seal(root, job, plan, final):
    run, seal, episodes = final.sealed_episodes(generation_root(root, job))
    require(run["tasks"] == plan["cohort"]["tasks"] and len(episodes) == job["denominator"]
            and run["config"] == job["config"] and run["provider"] == plan["model_identity"]
            and run["role"] == job["role"], "native sealed generation identity or complete dose differs")
    value = publish(job_root(root, job) / "whole_queue_seal/record.json", dict(
        schema="v71_fixed_endpoint_generation_seal.v1", protocol_id=plan["protocol_id"],
        registration_id=plan["id"], job_id=job["job_id"], checkpoint=plan["checkpoint"],
        denominator=job["denominator"], run_id=run["id"], generation_seal_id=seal["id"],
        generation_seal=binding.file_ref(generation_root(root, job) / "generation_seal/seal.json"),
        episode_sha256=[canonical_episode_hash(episode) for episode in episodes],
        all_provider_calls_settled=True, private_references_read=False))
    return value, episodes


def run(root, job, gpu, attempt_root, guard):
    """Worker owns resources/result/actual exit; this body only generates/seals."""
    _job(job)
    protocol, final = _protocol(root), _runtime()
    guard.check("before_endpoint_registration", boundary=True)
    plan = _prepare(root, job, protocol, final)
    directory = generation_root(root, job)
    if not (directory / "run.json").exists():
        final.prepare_run(plan["snapshot"], plan["role_plan"], directory, role=job["role"],
            config=_original().RunConfig.model_validate(job["config"]),
            identity=final.ModelIdentity.model_validate(plan["model_identity"]), task_keys=plan["cohort"]["tasks"])
    audit = audit_job_resume(root, job)
    require(audit["resume_allowed"] and audit["unknown_calls"] == 0,
            "UNKNOWN or changed endpoint output cannot be retried")
    response_calls = 0
    if not audit["complete_stage"]:
        state = _snapshot_state(plan["checkpoint"], job["step"])
        guard.check("before_evaluation_model_load", boundary=True)
        provider = final.load_final_provider(dict(assets=plan["assets"], config=job["config"]),
            dict(job, model_identity=plan["model_identity"]), state)
        del state
        guard.check("after_evaluation_model_load", boundary=True)
        original_chat = provider.chat
        async def observed_chat(*args, **kwargs):
            guard.check("before_evaluation_response", boundary=True)
            return await original_chat(*args, **kwargs)
        def stopped():
            if guard.stop.requested:
                raise importlib.import_module("finqa_v71_resources").ExplicitStop("explicit evaluation stop")
        provider.chat = observed_chat
        try:
            asyncio.run(binding.old_module("finqa_v56_feedback").execute_run_resumable(directory, provider,
                attempt_root=Path(attempt_root) / "generation", stop_check=stopped,
                after_return=lambda event: guard.check("after_durable_evaluation_return", boundary=True)))
            response_calls = provider.actual_model_calls
        finally:
            provider.chat = original_chat
            del provider, original_chat
            gc.collect()
            final.torch.cuda.empty_cache()
        guard.check("after_evaluation_model_release", boundary=True)
    seal, _ = _seal(root, job, plan, final)
    return dict(registration_id=plan["id"], whole_queue_seal=binding.entry(job_root(root, job) / "whole_queue_seal/record.json"),
                whole_queue_seal_id=seal["id"], sessions=job["denominator"],
                actual_new_response_calls=response_calls, scoring_calls=0, private_references_read=False,
                new_API_calls=0, model_released=True)


def generation_exit_barrier(root, protocol):
    base = importlib.import_module("finqa_v71_queue_base")
    jobs = base.all_jobs()
    barrier = checked(Path(root) / "all_jobs_exit_barrier/record.json")
    require(barrier["protocol_id"] == protocol["id"] and barrier["active_workers"] == []
            and len(jobs) == 5 and set(barrier["accepted_jobs"]) == set(barrier["actual_exits"]) == set(jobs),
            "all 5 fixed jobs and real exits must precede private scoring")
    for key, job in jobs.items():
        directory = base.job_directory(root, job)
        accepted, result = _accepted(root, key, directory, protocol)
        require(barrier["accepted_jobs"][key] == binding.entry(directory / "accepted/record.json")
                and barrier["actual_exits"][key] == accepted["actual_exit"], "all-exits barrier bytes changed")
        if job["kind"] == "generate":
            seal = binding.read_ref(result["whole_queue_seal"])
            require(_same_reference(result["whole_queue_seal"], binding.entry(directory / "whole_queue_seal/record.json"))
                    and result["sessions"] == seal["denominator"] == job["denominator"]
                    and result["registration_id"] == seal["registration_id"]
                    and result["whole_queue_seal_id"] == seal["id"] and seal["job_id"] == key,
                    "accepted generation exit must bind the complete registered endpoint seal")
    return binding.entry(Path(root) / "all_jobs_exit_barrier/record.json")


def paired_result(rows, baseline_rows, denominator):
    stats = _original().stats
    require([row["task_key"] for row in rows] == [row["task_key"] for row in baseline_rows],
            "baseline and endpoint task/draw order changed")
    result = stats.paired_transitions(rows, baseline_rows, denominator)
    if result["status"] == "COMPLETE":
        transitions = result["transitions"]
        result.update(new_correct=transitions["I->R"] + transitions["W->R"],
                      lost_correct=transitions["R->I"] + transitions["R->W"],
                      net_correct=result["numerator"])
    else:
        result.update(new_correct=None, lost_correct=None, net_correct=None)
    return result


def _score_job(root, job, protocol, barrier_ref, final, guard=None):
    plan = checked(job_root(root, job) / "registration/record.json")
    require(plan["protocol_id"] == protocol["id"] and plan["job"] == _job(job), "scoring registration changed")
    seal, episodes = _seal(root, job, plan, final)
    baseline_ref = protocol["baseline_evaluation"]["model_reports"][job["role"]]
    baseline = binding.read_ref(baseline_ref)
    tasks = [f"draw{GREEDY_SEED}/{task}" for task in plan["cohort"]["tasks"]]
    require(baseline["coordinate"] == "seed137/C1" and baseline["feedback_batch"] == 1
            and baseline["denominator"] == job["denominator"]
            and [row["task_key"] for row in baseline["results"]] == tasks,
            "readonly C1/b1 baseline or paired cohort changed")
    path = job_root(root, job) / "native_scores/record.json"
    if path.exists():
        saved = checked(path)
        require(saved["protocol_id"] == protocol["id"] and saved["job_id"] == job["job_id"]
                and saved["generation_seal_id"] == seal["id"] and saved["baseline"] == baseline_ref
                and saved["all_jobs_exit_barrier"] == barrier_ref
                and saved["denominator"] == job["denominator"]
                and [row["task_key"] for row in saved["results"]] == tasks
                and saved["metrics"] == _original().stats.native_metrics(saved["results"], job["denominator"]),
                "saved endpoint native scores changed")
        return saved
    manifest, public, lineages = final.load_public_snapshot(plan["snapshot"])
    require(manifest["id"] == plan["snapshot_id"], "native scoring snapshot changed")
    bundles = _original()._panel_private_bundles(final, plan, manifest, public, lineages, set(plan["cohort"]["tasks"]))
    rows = []
    for ordinal, (task, episode) in enumerate(zip(plan["cohort"]["tasks"], episodes, strict=True)):
        _check_stop(root)
        if guard is not None:
            guard.check("before_native_score", boundary=True)
        row_path = job_root(root, job) / "native_rows" / f"row{ordinal:04d}" / "record.json"
        episode_sha = canonical_episode_hash(episode)
        if row_path.exists():
            saved_row = checked(row_path)
            require(saved_row["protocol_id"] == protocol["id"] and saved_row["job_id"] == job["job_id"]
                    and saved_row["episode_sha256"] == episode_sha and saved_row["ordinal"] == ordinal
                    and saved_row["generation_seal_id"] == seal["id"]
                    and saved_row["row"]["task_key"] == f"draw{GREEDY_SEED}/{task}",
                    "durable native score row changed; never rescore it")
            rows.append(saved_row["row"])
            continue
        row = dict(task_key=f"draw{GREEDY_SEED}/{task}", original_task_key=task, draw_seed=GREEDY_SEED,
            native=final.score_public_reasoning_program(bundles[task], episode),
            stop_reason=episode.stop_reason, actual_model_calls=episode.actual_model_calls,
            tool_call_count=len(episode.tool_events),
            generated_token_count=sum(len(t.receipt.raw_generated_token_ids) for t in episode.turns if t.receipt is not None),
            source_group=plan["cohort"]["source_groups"][task])
        publish(row_path, dict(schema="v71_durable_native_score_row.v1", protocol_id=protocol["id"],
            job_id=job["job_id"], ordinal=ordinal, episode_sha256=episode_sha,
            generation_seal_id=seal["id"], row=row))
        rows.append(row)
    metrics = _original().stats.native_metrics(rows, job["denominator"])
    paired = paired_result(rows, baseline["results"], job["denominator"])
    return publish(path, dict(schema="v71_fixed_endpoint_native_scores.v1", protocol_id=protocol["id"],
        job_id=job["job_id"], seed=137, arm="Fixed894", step=job["step"], role=job["role"],
        denominator=job["denominator"], generation_seal_id=seal["id"], all_jobs_exit_barrier=barrier_ref,
        baseline=baseline_ref, results=rows, metrics=metrics, paired_to_894=paired,
        status="COMPLETE" if paired["status"] == "COMPLETE" and all(
            metrics[name]["unknown"] == 0 for name in ("execution_accuracy", "program_accuracy")) else "INCOMPLETE_UNKNOWN",
        unknown_as_zero=False, baseline_rescored=False, checkpoint_selection=False))


def compare_reports(fixed, full, baseline):
    """Only saved native rows; orientation is stated for every paired matrix."""
    denominator = fixed["denominator"]
    require(full["denominator"] == baseline["denominator"] == denominator,
            "all paired panels retain one complete denominator")
    stats = _original().stats
    metrics = {name: stats.native_metrics(report["results"], denominator)
               for name, report in (("Fixed894", fixed), ("Full", full), ("baseline894", baseline))}
    pairs = {
        "Full_minus_Fixed894": paired_result(full["results"], fixed["results"], denominator),
        "Fixed894_minus_baseline894": paired_result(fixed["results"], baseline["results"], denominator),
        "Full_minus_baseline894": paired_result(full["results"], baseline["results"], denominator),
    }
    require(all(row["status"] == "COMPLETE" for row in pairs.values())
            and all(row[metric]["unknown"] == 0 for row in metrics.values()
                    for metric in ("execution_accuracy", "program_accuracy")),
            "UNKNOWN leaves paired comparisons incomplete; no imputation")
    pa = {}
    for label, candidate, reference in (("Full_minus_Fixed894", "Full", "Fixed894"),
            ("Fixed894_minus_baseline894", "Fixed894", "baseline894"),
            ("Full_minus_baseline894", "Full", "baseline894")):
        count = metrics[candidate]["program_accuracy"]["correct"] - metrics[reference]["program_accuracy"]["correct"]
        pa[label] = dict(numerator=count, denominator=denominator, difference=count / denominator,
                         difference_pp=100 * count / denominator)
    return dict(denominator=denominator, native_metrics=metrics, paired_execution=pairs,
                paired_program_accuracy=pa,
                transition_orientation="reference -> candidate as named by candidate_minus_reference",
                old_scores_rescored=False, unknown_as_zero=False)


def primary_estimands(comparison):
    require(comparison["denominator"] == 883, "primary estimands require dev883")
    metrics = comparison["native_metrics"]
    fixed = metrics["Fixed894"]["execution_accuracy"]["correct"]
    full = metrics["Full"]["execution_accuracy"]["correct"]
    baseline = metrics["baseline894"]["execution_accuracy"]["correct"]
    require(full == 371 and baseline == 525, "registered saved Full and baseline dev anchors changed")
    def value(count, formula):
        return dict(numerator=count, denominator=883, difference=count / 883,
                    difference_pp=100 * count / 883, formula=formula)
    if fixed >= baseline:
        outcome = "fixed_maintains_or_improves_baseline_Full_lower"
    elif fixed > full:
        outcome = "both_decline_Full_more"
    elif fixed == full:
        outcome = "equal_total_correct_not_equivalence"
    else:
        outcome = "Full_positive_increment_both_below_baseline"
    return dict(Fixed894_correct=fixed, Full_correct=full, baseline894_correct=baseline,
        delta_adaptive=value(full - fixed, "(371-H)/883"),
        delta_fixed=value(fixed - baseline, "(H-525)/883"),
        descriptive_case=outcome, inference_scope="one fixed parent, training RNG realization and development panel",
        independent_C_N_or_second_update_effect_identified=False,
        equality_implies_equivalence=False, stability_from_small_count_difference=False,
        advancement_threshold=None, automatic_followup=False)


def finish(root, guard=None):
    """One no-CUDA child, after the two train and three generation real exits."""
    _check_stop(root)
    protocol = _protocol(root)
    barrier_ref = generation_exit_barrier(root, protocol)
    summary_path = Path(root) / "evaluations/final_summary/record.json"
    if summary_path.exists():
        saved = checked(summary_path)
        require(saved["protocol_id"] == protocol["id"] and saved["all_jobs_exit_barrier"] == barrier_ref,
                "saved V71 final analysis binding changed")
        for reference in [*saved["model_reports"].values(), saved["failure_mechanisms"],
                          saved["existing_distribution_and_supervision"], saved["fixed_training_dynamics"]]:
            binding.read_ref(reference)
        return saved
    final, reports, comparisons = _runtime(), {}, {}
    for key, job in planned_jobs().items():
        _check_stop(root)
        report = _score_job(root, job, protocol, barrier_ref, final, guard)
        require(report["status"] == "COMPLETE", "native UNKNOWN blocks complete analysis; never rescore")
        reports[key] = binding.entry(job_root(root, job) / "native_scores/record.json")
        full = binding.read_ref(protocol["full_evaluation"]["model_reports"][key])
        baseline = binding.read_ref(protocol["baseline_evaluation"]["model_reports"][job["role"]])
        require(full["arm"] == "Full" and full["step"] == job["step"]
                and full["job_id"] == key and full["status"] == "COMPLETE",
                "fixed preselected Full comparator changed")
        comparisons[key] = compare_reports(report, full, baseline)
    failure = importlib.import_module("finqa_v71_failure_analysis").finish(root, reports, guard=guard)
    mechanism = importlib.import_module("finqa_v71_mechanism_analysis")
    existing_mechanism = binding.entry(Path(root) / "existing_mechanism_analysis/record.json")
    reader, dynamics = mechanism.Reader(), {}
    for start in (894, 1192):
        receipts = []
        for step in range(start + 1, start + 299):
            _check_stop(root)
            receipt = reader.read(Path(root) / "training" / f"step{step:04d}_step/record.json")
            require(receipt["step"] == step, "fixed saved training receipt order changed")
            receipts.append(receipt)
        dynamics[str(start)] = mechanism.training_dynamics(receipts)
    dynamics_path = Path(root) / "mechanism_analysis/fixed_training_dynamics/record.json"
    publish(dynamics_path, dict(schema="v71_saved_fixed_training_dynamics.v1", protocol_id=protocol["id"],
        optimizer_updates=596, windows=dynamics, source_receipts=list(reader.sources.values()),
        actual_saved_loss_not_gradient_attribution=True, new_model_computation=False))
    return publish(summary_path, dict(schema="v71_fixed_distribution_paired_final_analysis.v1", status="COMPLETE",
        protocol_id=protocol["id"], all_jobs_exit_barrier=barrier_ref, model_reports=reports,
        baseline=protocol["baseline_evaluation"], Full=protocol["full_evaluation"], comparisons=comparisons,
        primary_estimands=primary_estimands(comparisons["step1490.dev_greedy"]),
        failure_mechanisms=binding.entry(Path(root) / "mechanism_analysis/paired_invalid/record.json"),
        existing_distribution_and_supervision=existing_mechanism,
        fixed_training_dynamics=binding.entry(dynamics_path),
        failure_mechanism_id=failure["id"], new_evaluation_sessions=1123, new_outer_updates=0,
        optimizer_updates=596, task_exposures=2976, endpoint_selected_in_advance=1490,
        feedback_sessions=0, class_passes=0, VJP=0, replay_responses=0,
        dev1192_evaluated=False, individual_outer_or_C_N_causal_effect_identified=False,
        across_seed_stability_proved=False, development_evidence_only=True, automatic_followup=False,
        intermediate_accuracy_used_for_selection=False, baseline_rescored=False, Full_rescored=False))
