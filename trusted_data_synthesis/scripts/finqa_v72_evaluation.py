"""Three fixed greedy endpoints, then one all-exits-gated CPU-only analysis.

Imports are deliberately lazy. The historical native harness/scorer is reused,
but its fixed step894/C-only checkpoint loader and multi-arm selection are not.
"""
from __future__ import annotations

import asyncio
import gc
import importlib
from pathlib import Path

import finqa_v72_binding as binding

require, checked, publish = binding.require, binding.checked, binding.publish
GREEDY_SEED = 20260928
PANELS = ((1192, "development", 883), (1490, "calibration", 120), (1490, "development", 883))


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
        parent = step == 1192
        jobs[key] = dict(job_id=key, id=key, kind="generate", memory_phase="generate", stage="generate",
            seed=137, arm="Parent1192" if parent else "LowLR1192", step=step, role=role,
            algorithm="inherited_parent_evaluation" if parent else "low_lr_1e-5_from_fixed1192",
            denominator=denominator, draw_seed=GREEDY_SEED, panel=key, config=panel_config(role))
    return jobs


def evaluation_contract():
    return dict(schema="v72_parent_and_low_lr_endpoint_evaluation.v1", jobs=planned_jobs(),
        generation_jobs=3, total_sessions=1886, calibration_sessions=120, development_sessions=1766,
        baseline_step=894, baseline_seed=137, baseline_arm="C1", baseline_feedback_batch=1,
        baseline_EA_correct=dict(calibration=67, development=525),
        parent_step=1192, parent_calibration_correct=74, original_parent_lr=1e-4,
        new_parent_development_sessions=883, parent_untouched_checkpoint=True,
        low_lr=1e-5, final_endpoint=1490, high_lr_endpoint_correct=dict(calibration=56,development=377),
        baseline_regeneration=False, baseline_rescoring=False, parent_calibration_rescoring=False,
        high_lr_regeneration=False, high_lr_rescoring=False, Full1192_dev_generated=False,
        applied_new_outer_updates=0, condition="low_lr_1e-5_from_fixed1192",
        main_estimands=dict(lr="(L-377)/883",retention="(L-B)/883",old_window="(377-B)/883"),
        old_fixed_path_decomposition="-148=(B-525)+(377-B)",
        original_optimizer_moments_and_rng_preserved_before_lr_intervention=True,
        low_lr_after_complete_parent_restore=True, native_checkpoint_arm="C-only",
        parent_dev_generation_may_overlap_low_lr_training=True,
        parent_result_never_changes_parent_lr_or_endpoint=True,
        before_generation="parent: accepted V71 Fixed1192 original checkpoint; low endpoint: new train actual exit zero",
        before_private_scoring="all 4 training/generation jobs accepted actual exit zero",
        intermediate_score_selection=False, partial_scores_influence_training=False,
        stochastic_evaluation=False, test_evaluation=False, source_cluster_bootstrap=False,
        cross_seed_confidence_interval=False, full_denominators=True, unknown_as_zero=False,
        native_scorer_reused=True, automatic_extension=False,
        canonical_episode_encoding="native Episode.model_dump(mode=json)",
        complete_returns_never_regenerated=True, unknown_call_auto_retry=False,
        independent_cpu_analysis=dict(max_RSS_GiB=64,minimum_effective_host_free_GiB=96,
            CUDA_visible_devices="",controller_observes_actual_exit=True),
        original_native_failure_rules_unchanged=True, single_parent_conditional_lr_effect=True,
        learning_rate_grid_search=False, learning_rate_optimality_identified=False,
        development_evidence_only=True, automatic_Full_resume=False)


def canonical_episode_payload(episode):
    value = episode if isinstance(episode, dict) else episode.model_dump(mode="json")
    require(isinstance(value, dict), "native Episode must serialize to a JSON object")
    return value


def canonical_episode_hash(episode):
    return binding.digest(canonical_episode_payload(episode))


def _protocol(root):
    require(Path(root).resolve() == binding.ROOT.resolve(), "foreign V72 evaluation root")
    protocol = checked(Path(root) / "protocol/record.json")
    require(protocol["evaluation"] == evaluation_contract(), "fixed V72 evaluation contract changed")
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
    training = importlib.import_module("finqa_v72_training")
    if job["step"] == 1192:
        require(job["arm"] == "Parent1192", "original1192 evaluation arm changed")
        reference = training.initial_checkpoint()
        require(reference == protocol["initial_parent"]["checkpoint"],
                "parent evaluation cannot load an intervened or latest checkpoint")
        directory = binding.V71_ROOT / "points/step0894/train"
        parent_protocol = checked(binding.V71_ROOT / "protocol/record.json")
        require(parent_protocol["id"] == binding.V71_PROTOCOL_ID, "parent scientific protocol changed")
        accepted, result = _accepted(binding.V71_ROOT,"step894.train",directory,parent_protocol)
        completed = checked(directory / "completed/record.json")
        require(completed["arm"] == "Fixed894" and completed["initial_step"] == 894
                and completed["final_step"] == 1192 and completed["optimizer_updates"] == 298
                and completed["outer_updates"] == 0 and completed["final_checkpoint"] == reference
                and result["final_checkpoint"] == reference
                and _same_reference(result["branch_result"],binding.entry(directory / "completed/record.json")),
                "parent evaluation requires the original accepted Fixed1192 state")
    else:
        require(job["step"] == 1490 and job["arm"] == "LowLR1192", "unregistered evaluation endpoint")
        directory = Path(root) / "points/step1192/train"
        accepted, result = _accepted(root,"step1192.train",directory,protocol)
        completed = checked(directory / "completed/record.json")
        require(completed["protocol_id"] == protocol["id"] and completed["status"] == "COMPLETE"
                and completed["seed"] == 137 and completed["arm"] == "LowLR1192"
                and completed["initial_step"] == 1192 and completed["final_step"] == 1490
                and completed["optimizer_updates"] == 298 and completed["outer_updates"] == 0
                and completed["learning_rate"] == 1e-5 and completed["initial_learning_rate"] == 1e-4
                and completed["fixed_distribution_digest"] == completed["distribution_digest"]
                and result["final_checkpoint"] == completed["final_checkpoint"]
                and _same_reference(result["branch_result"],binding.entry(directory / "completed/record.json")),
                "new endpoint requires accepted298-update low-lr zero-outer training")
        reference = completed["final_checkpoint"]
    return reference, dict(accepted=binding.entry(directory / "accepted/record.json"),
        result=accepted["result"],completed=binding.entry(directory / "completed/record.json"))


def _snapshot_state(reference, step):
    training = importlib.import_module("finqa_v72_training")
    _, rt = training.runtime()
    state = training.read_checkpoint(reference, rt)
    if step == 1192:
        require(reference == training.initial_checkpoint(), "parent dev must use the original high-lr1192 checkpoint")
        training.validate_parent_state(state,rt)
    else:
        require(step == 1490, "unregistered low-lr endpoint")
        context = training.checked_window(binding.ROOT,1192)
        training.validate_low_lr_state(state,step,context,rt)
    return state


def _model_point_id(job, protocol, reference):
    return "v72-" + job["arm"] + "-evaluation:" + binding.digest(dict(
        protocol_id=protocol["id"],seed=137,arm=job["arm"],step=job["step"],checkpoint=reference))


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
        point_id=_model_point_id(job,protocol,reference),
        parameter_digest=final.parameter_digest(state["parameters"]),
        tokenizer_digest=original_identity["tokenizer_digest"],
        chat_template_digest=original_identity["chat_template_digest"]).model_dump(mode="json")
    del state
    gc.collect()
    return publish(path, dict(schema="v72_endpoint_generation_registration.v1", protocol_id=protocol["id"],
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
        schema="v72_fixed_endpoint_generation_seal.v1", protocol_id=plan["protocol_id"],
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
                raise importlib.import_module("finqa_v72_resources").ExplicitStop("explicit evaluation stop")
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
    base = importlib.import_module("finqa_v72_queue_base")
    jobs = base.all_jobs()
    barrier = checked(Path(root) / "all_jobs_exit_barrier/record.json")
    require(barrier["protocol_id"] == protocol["id"] and barrier["active_workers"] == []
            and len(jobs) == 4 and set(barrier["accepted_jobs"]) == set(barrier["actual_exits"]) == set(jobs),
            "all 4 fixed jobs and real exits must precede private scoring")
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
        publish(row_path, dict(schema="v72_durable_native_score_row.v1", protocol_id=protocol["id"],
            job_id=job["job_id"], ordinal=ordinal, episode_sha256=episode_sha,
            generation_seal_id=seal["id"], row=row))
        rows.append(row)
    metrics = _original().stats.native_metrics(rows, job["denominator"])
    paired = paired_result(rows, baseline["results"], job["denominator"])
    return publish(path, dict(schema="v72_fixed_endpoint_native_scores.v1", protocol_id=protocol["id"],
        job_id=job["job_id"], seed=137, arm=job["arm"], step=job["step"], role=job["role"],
        denominator=job["denominator"], generation_seal_id=seal["id"], all_jobs_exit_barrier=barrier_ref,
        baseline=baseline_ref, results=rows, metrics=metrics, paired_to_894=paired,
        status="COMPLETE" if paired["status"] == "COMPLETE" and all(
            metrics[name]["unknown"] == 0 for name in ("execution_accuracy", "program_accuracy")) else "INCOMPLETE_UNKNOWN",
        unknown_as_zero=False, baseline_rescored=False, checkpoint_selection=False))


def compare_reports(low, high, parent, baseline):
    """All paired conditions have one complete native task order and denominator."""
    denominator = low["denominator"]
    reports = dict(LowLR1490=low,HighLR1490=high,parent1192=parent,baseline894=baseline)
    require(all(report["denominator"] == denominator for report in reports.values()),
            "registered complete comparison denominators differ")
    stats = _original().stats
    metrics = {name:stats.native_metrics(report["results"],denominator) for name,report in reports.items()}
    pairs, pa = {}, {}
    for candidate, reference in (("LowLR1490","HighLR1490"),("LowLR1490","parent1192"),
            ("HighLR1490","parent1192"),("parent1192","baseline894"),
            ("HighLR1490","baseline894"),("LowLR1490","baseline894")):
        label = candidate + "_minus_" + reference
        pairs[label] = paired_result(reports[candidate]["results"],reports[reference]["results"],denominator)
        require(pairs[label]["status"] == "COMPLETE", "UNKNOWN leaves paired comparison incomplete")
        before = [row["native"]["native"]["program_accuracy"] for row in reports[reference]["results"]]
        after = [row["native"]["native"]["program_accuracy"] for row in reports[candidate]["results"]]
        require(all(value in (0,1) for value in before+after), "UNKNOWN program accuracy cannot be imputed")
        count = sum(after)-sum(before)
        pa[label] = dict(numerator=count,denominator=denominator,difference=count/denominator,
            difference_pp=100*count/denominator,
            new_correct=sum(b==0 and a==1 for b,a in zip(before,after,strict=True)),
            lost_correct=sum(b==1 and a==0 for b,a in zip(before,after,strict=True)),
            transitions={f"{b}->{a}":sum(x==b and y==a for x,y in zip(before,after,strict=True))
                         for b in (0,1) for a in (0,1)})
    require(all(row[metric]["unknown"] == 0 for row in metrics.values()
                for metric in ("execution_accuracy","program_accuracy")), "UNKNOWN retains full denominator")
    return dict(denominator=denominator,native_metrics=metrics,paired_execution=pairs,
        paired_program_accuracy=pa,transition_orientation="reference -> candidate; candidate_minus_reference",
        old_scores_rescored=False,unknown_as_zero=False)


def primary_estimands(comparison):
    require(comparison["denominator"] == 883, "primary estimands require dev883")
    metrics = comparison["native_metrics"]
    L,B,H,A = [metrics[name]["execution_accuracy"]["correct"] for name in
               ("LowLR1490","parent1192","HighLR1490","baseline894")]
    require(H == 377 and A == 525, "registered old fixed endpoint and baseline changed")
    def value(count,formula):
        return dict(numerator=count,denominator=883,difference=count/883,
                    difference_pp=100*count/883,formula=formula)
    if L <= H:
        case = "preset_lr_reduction_not_higher_than_original_endpoint"
    elif L < B:
        case = "reduction_mitigates_decline_but_does_not_retain_parent"
    elif L == B:
        case = "parent_total_retained_without_net_new_correct"
    else:
        case = "observed_correct_count_above_parent_and_original_endpoint"
    return dict(LowLR1490_correct=L,parent1192_correct=B,HighLR1490_correct=H,baseline894_correct=A,
        delta_LR=value(L-H,"(L-377)/883"),delta_retention=value(L-B,"(L-B)/883"),
        delta_old_window=value(H-B,"(377-B)/883"),
        original_fixed_path_decomposition=dict(first_window=B-A,last_window=H-B,total=H-A,
            exact_count_identity=(B-A)+(H-B)==-148,denominator=883,
            formula="-148=(B-525)+(377-B)",internal_causal_share=False),
        descriptive_count_case=case,parent_count_retained=L>=B,
        inference_scope="one1192parent, one training RNG realization and development panel",
        small_net_count_is_stable_improvement=False,equality_implies_equivalence=False,
        independent_C_N_or_root_cause_identified=False,learning_rate_optimality_identified=False,
        advancement_threshold=None,automatic_Full_resume=False,automatic_followup=False)


def finish(root,guard=None):
    """One no-CUDA child, after one train and all three generation real exits."""
    _check_stop(root)
    protocol = _protocol(root)
    barrier_ref = generation_exit_barrier(root,protocol)
    summary_path = Path(root) / "evaluations/final_summary/record.json"
    if summary_path.exists():
        saved = checked(summary_path)
        require(saved["protocol_id"] == protocol["id"] and saved["all_jobs_exit_barrier"] == barrier_ref,
                "saved V72 final analysis binding changed")
        for ref in [*saved["model_reports"].values(),saved["failure_mechanisms"],saved["low_lr_training_dynamics"]]:
            binding.read_ref(ref)
        return saved
    binding.read_ref(protocol["static_supervision_gate"])
    binding.read_ref(protocol["existing_analysis"])
    final,reports,values = _runtime(),{},{}
    for key,job in planned_jobs().items():
        _check_stop(root)
        report = _score_job(root,job,protocol,barrier_ref,final,guard)
        require(report["status"] == "COMPLETE", "nativeUNKNOWN blocks final analysis; never rescore")
        reports[key] = binding.entry(job_root(root,job) / "native_scores/record.json")
        values[key] = report
    comparisons = {}
    for role,key in (("development","step1490.dev_greedy"),("calibration","step1490.cal_greedy")):
        high = binding.read_ref(protocol["high_lr_evaluation"]["model_reports"][key])
        parent = values["step1192.dev_greedy"] if role == "development" else binding.read_ref(
            protocol["parent_evaluation"]["model_reports"]["calibration"])
        baseline = binding.read_ref(protocol["baseline_evaluation"]["model_reports"][role])
        require(high["arm"] == "Fixed894" and high["step"] == 1490 and high["job_id"] == key
                and high["status"] == parent["status"] == "COMPLETE" and parent["step"] == 1192,
                "fixed preselected parent/high-lr comparator changed")
        comparisons[role] = compare_reports(values[key],high,parent,baseline)
    failure = importlib.import_module("finqa_v72_failure_analysis").finish(root,reports,guard=guard)
    mechanism = binding.source_v71("finqa_v71_mechanism_analysis")
    reader,receipts = mechanism.Reader(),[]
    for step in range(1193,1491):
        _check_stop(root)
        receipt = reader.read(Path(root) / "training" / f"step{step:04d}_step/record.json")
        require(receipt["step"] == step, "low-lr trainingreceipt order changed")
        receipts.append(receipt)
    dynamics_path = Path(root) / "mechanism_analysis/low_lr_training_dynamics/record.json"
    publish(dynamics_path,dict(schema="v72_saved_low_lr_training_dynamics.v1",protocol_id=protocol["id"],
        optimizer_updates=298,window=mechanism.training_dynamics(receipts),
        source_receipts=list(reader.sources.values()),actual_saved_loss_not_gradient_attribution=True,
        new_model_computation=False))
    return publish(summary_path,dict(schema="v72_low_lr_parent_paired_final_analysis.v1",status="COMPLETE",
        protocol_id=protocol["id"],all_jobs_exit_barrier=barrier_ref,model_reports=reports,
        baseline=protocol["baseline_evaluation"],parent=protocol["parent_evaluation"],
        HighLR=protocol["high_lr_evaluation"],comparisons=comparisons,
        primary_estimands=primary_estimands(comparisons["development"]),
        failure_mechanisms=binding.entry(Path(root) / "mechanism_analysis/paired_invalid/record.json"),
        failure_mechanism_id=failure["id"],low_lr_training_dynamics=binding.entry(dynamics_path),
        static_supervision_gate=protocol["static_supervision_gate"],
        existing_analysis=protocol["existing_analysis"],
        new_evaluation_sessions=1886,new_outer_updates=0,optimizer_updates=298,task_exposures=1488,
        endpoint_selected_in_advance=1490,parent_step=1192,learning_rate=1e-5,
        feedback_sessions=0,class_passes=0,VJP=0,replay_responses=0,dev1192_evaluated=True,
        individual_C_N_or_internal_root_cause_identified=False,learning_rate_optimality_identified=False,
        across_seed_stability_proved=False,development_evidence_only=True,automatic_followup=False,
        automatic_Full_resume=False,intermediate_accuracy_used_for_selection=False,
        baseline_rescored=False,parent_calibration_rescored=False,high_lr_rescored=False))
