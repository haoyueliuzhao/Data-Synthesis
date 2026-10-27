"""Freeze one training-side demonstration intervention with the V72 control."""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess

import finqa_v75_binding as b

FILES = tuple(f"finqa_v75_{name}.py" for name in (
    "binding", "registration", "resources", "signals", "controller", "entry", "worker",
    "collection", "collection_runtime", "training", "materials", "evaluation", "analysis"))
_IMPLEMENTATION = _PROTOCOL = None


def scientific_contract():
    return dict(schema="v75_training_state_demonstration_contract.v1",
        parent="exact original P1192 theta/buffers/Adam/RNG/pi/prior/schedule",
        candidate="StateDemo1192", new_training_paths=1, reused_control="V72 LowLR1490",
        reused_control_EA=431, parent_EA=536, development_denominator=883,
        original_894_525_not_parent=True, original_learning_rate=1e-4, learning_rate=1e-5,
        change_LR_only_after_exact_parent_restore=True, new_optimizer_updates=298,
        steps=[1193,1490], task_exposures=1488, four_task_tail_batches=2,
        original_task_frequency_schedule_and_pi_preserved=True, original_outer_history=[298],
        max_selected_training_tasks=128, selected_before_generation=True,
        collection_phases=["L.initial","P.initial","P.post"], collection_shards_per_phase=2,
        initial_L_sessions=128, initial_P_sessions=128, maximum_post_P_sessions=128,
        post_state="exact input before L last returned model call; only b>=1 with actual tools",
        post_budget="32-b", initial_state_not_duplicate_post=True,
        maximum_collection_model_calls=12160, new_development_sessions=883,
        maximum_development_model_calls=28256, maximum_total_new_model_calls=40416,
        max_steps=32, max_new_tokens=2048, context_limit=24576,
        greedy=True, failure_replacement=False, force_tools_or_program_repair=False,
        teacher_success_not_assumed=True, only_complete_EA_correct_public_valid_teacher_suffix_supervised=True,
        student_prefix_user_and_tool_observations_target_masked=True,
        initial_slot_weight=0.25, post_slot_weight=0.25,
        old_loss_weight="1-0.25*I_initial-0.25*I_post",
        missing_slot_mass_returns_to_old_loss=True, missing_slot_mass_transferred_to_other_demo=False,
        demo_loss="sum teacher suffix token CE / full teacher suffix supervised token count",
        old_loss_normalization_unchanged=True, one_clip_and_Adam_per_batch=True,
        two_demo_slots_available_global_equal_task_mass_upper_bound=128/744*0.5,
        actual_batch_normalized_dose_registered_before_training=True, actual_consumption_recorded=True,
        source_overlap_reported_not_assumed_absent=True, PA_and_public_checks_separate=True,
        old_static_supervision_audit_reused_no_full_reexecution=True,
        new_material_and_new_consumer_only_static_checks=True,
        old_control_is_not_new_independent_replication=True, extra_forward_dropout_stream_not_claimed_identical=True,
        evaluation_from_initial_request=True, endpoint_only=True, calibration_sessions=0,
        deltas=["(S-431)/883","(S-536)/883"], full_denominator_I_W_R_UNKNOWN=True,
        initial_and_post_tool_no_call_denominator=883, old96_fixed_mechanism_slice_only=True,
        paired_uncertainty_uses_actual_source_clusters=True,
        new_outer_updates=0, new_Contribution=0, new_VJP=0, new_class_passes=0,
        new_feedback_gradient_sessions=0, new_response_gradient_replays=0,
        new_large_NLL_probe=0, external_API_calls=0, automatic_followup=False,
        automatic_Full_resume=False, hyperparameter_search=False,
        development_examples_or_derived_answers_in_training=False,
        combined_recipe_effect_only_not_VTDO_increment=True)


def recovery_policy():
    return dict(schema="v75_same_durable_state_recovery.v1",
        complete_model_tool_returns_and_optimizer_commits_reused=True,
        incomplete_new_model_tool_or_reconstruction_call_is_UNKNOWN=True,
        UNKNOWN_state_source_numeric_or_implementation_failure_automatic_retry=False,
        confirmed_resource_failure_at_actual_durable_boundary_only=True,
        retry_backoff_seconds=300,no_progress_retry_limit=3,
        controller_failure_automatic_restart=False, CPU_phase_automatic_retry=False,
        explicit_STOP_or_owner_signal_stops_recovery=True,
        arbitrary_stage_or_resource_wait_deadline=False,new_budget_on_retry=False)


def jobs_for(bundle):
    collection=importlib.import_module("finqa_v75_collection")
    evaluation=importlib.import_module("finqa_v75_evaluation")
    training=importlib.import_module("finqa_v75_training")
    jobs=collection.jobs(bundle)
    collection_ids=sorted(jobs)
    for row in jobs.values():
        row["dependencies"]=[f"L.initial.shard{s}" for s in range(2)] if row["phase"]=="P.post" else []
    train=training.job_spec()
    train["dependencies"]=collection_ids
    train["requires_materials_accepted"]=True
    jobs[train["job_id"]]=train
    for key,row in evaluation.planned_jobs().items():
        jobs[key]=dict(row,dependencies=[train["job_id"]])
    return jobs


def stage_prepared_inputs(inputs_path, stratification_path):
    """Reuse already completed read-only preparation without selecting again."""
    destination=b.ROOT/"inputs/record.json"
    b.require(not destination.exists(),"V75 inputs already staged")
    inputs=b.checked(inputs_path)
    producer=b.REPO/"trusted_data_synthesis/scripts/finqa_v75_collection.py"
    b.require(b.sha(producer)=="1fbdf6ba0df815b868e6f3caf9a32ab945e21e6f3cc3160755cd8e3fa619a79d",
              "actual input preparation producer changed")
    b.require(inputs["selected_task_count"]==128 and inputs["collection_call_cap"]==12160,
              "registered collection dose changed")
    b.publish(destination,dict(inputs,preparation_source_sha256={producer.name:b.sha(producer)}))
    stratification=json.loads(Path(stratification_path).read_bytes())
    producer_ref=stratification["producer"]
    b.require(b.sha(producer_ref["path"])==producer_ref["sha256"],"actual read-only analysis producer changed")
    b.publish(b.ROOT/"historical_V74_stratification/record.json",stratification)
    return dict(status="INPUTS_PREPARED",inputs=b.entry(destination))


def _reference_contract(bundle):
    old=b.checked(b.V72_ROOT/"protocol/record.json")
    closeout=b.checked(b.V72_ROOT/"closeout/record.json")
    summary=b.checked(b.V72_ROOT/"evaluations/final_summary/record.json")
    b.require(closeout["status"]==summary["status"]=="COMPLETE","V72 reusable control incomplete")
    refs=dict(B=summary["model_reports"]["step1490.dev_greedy"],
              P=summary["model_reports"]["step1192.dev_greedy"])
    for name,count in (("B",431),("P",536)):
        value=b.read_ref(refs[name])
        b.require(value["denominator"]==883 and value["metrics"]["execution_accuracy"]["correct"]==count
            and value["metrics"]["states"]["UNKNOWN"]==0,"reused endpoint/count differs")
    parent=old["initial_parent"]
    b.require(parent["checkpoint"]==bundle["model_bindings"]["P"]["checkpoint"]
        and parent["checkpoint"]["step"]==1192,"P collection and training parents differ")
    return old,parent,refs


def freeze(source_commit):
    b.require(not (b.ROOT/"implementation").exists(),"V75 already frozen")
    bundle=b.checked(b.ROOT/"inputs/record.json")
    old,parent,reused=_reference_contract(bundle)
    commit=subprocess.check_output(["git","rev-parse",source_commit+"^{commit}"],cwd=b.REPO,text=True).strip()
    raw_files={}
    for filename in FILES:
        relative="trusted_data_synthesis/scripts/"+filename
        raw=subprocess.check_output(["git","show",commit+":"+relative],cwd=b.REPO)
        b.require(hashlib.sha256(raw).hexdigest()==b.sha(b.REPO/relative),"uncommitted production file: "+filename)
        raw_files[filename]=raw
    for filename,sha in bundle["preparation_source_sha256"].items():
        b.require(hashlib.sha256(raw_files[filename]).hexdigest()==sha,"selection producer changed")
    analysis=b.checked(b.ROOT/"historical_V74_stratification/record.json")
    b.require(hashlib.sha256(raw_files["finqa_v75_analysis.py"]).hexdigest()==analysis["producer"]["sha256"],
              "historical analysis producer changed")
    inherited_ref=b.entry(b.V74_ROOT/"implementation/record.json")
    inherited=b.read_ref(inherited_ref)
    b.require(inherited["id"]==b.V74_IMPLEMENTATION_ID,"V74 frozen lineage changed")
    sources=dict(inherited["source_bindings"])
    sources.update({str(b.V74_ROOT/"implementation"/name):sha for name,sha in inherited["sha256"].items()})
    free_disk=shutil.disk_usage(b.ROOT.parent).free
    b.require(free_disk>=32*1024**3,"insufficient disk for bounded collection and candidate checkpoints")
    destination=b.ROOT/"implementation";destination.mkdir(parents=True,exist_ok=False)
    for name,raw in raw_files.items():
        with (destination/name).open("xb") as stream:
            stream.write(raw);stream.flush();os.fsync(stream.fileno())
    manifest=b.publish(destination/"record.json",dict(schema="v75_frozen_implementation.v1",source_commit=commit,
        sha256={name:hashlib.sha256(raw).hexdigest() for name,raw in raw_files.items()},
        source_bindings=sources,inherited_manifest=inherited_ref,frozen_source_root=inherited["frozen_source_root"],
        original_scientific_sources_modified=False))
    resources=importlib.import_module("finqa_v75_resources")
    signals=importlib.import_module("finqa_v75_signals")
    control=importlib.import_module("finqa_v75_controller")
    evaluation=importlib.import_module("finqa_v75_evaluation")
    training=importlib.import_module("finqa_v75_training")
    protocol=b.publish(b.ROOT/"protocol/record.json",dict(schema="v75_training_state_demonstration_protocol.v1",
        output_root=str(b.ROOT),source_commit=commit,user_plan=b.file_ref(b.USER_PLAN),
        authorization="参照审计修订并开展后续实验",implementation=b.entry(destination/"record.json"),
        inputs=b.entry(b.ROOT/"inputs/record.json"),scientific_contract=scientific_contract(),
        model_bindings=bundle["model_bindings"],initial_parent=parent,jobs=jobs_for(bundle),
        training_contract=training.training_contract(),baseline_compatibility=training.baseline_compatibility_policy(),
        evaluation=evaluation.evaluation_contract(),reused_evaluation=reused,
        evaluation_source_registration=old["evaluation_source_registration"],
        old_evaluation_registration=old["old_evaluation_registration"],
        mechanism_selection=bundle["V73_V74_mechanism_selection"],
        historical_V74_stratification=b.entry(b.ROOT/"historical_V74_stratification/record.json"),
        reused_old_static_audit=old["static_supervision_gate"],old_full_static_audit_reexecuted=False,
        source_V72_closeout=b.entry(b.V72_ROOT/"closeout/record.json"),
        source_V74_closeout=b.entry(b.V74_ROOT/"closeout/record.json"),
        gpu_uuids=resources.GPU_UUIDS,cpu_affinity=resources.CPU_AFFINITY,gpu_priority=list(b.GPU_PRIORITY),
        gpu_lease_root=old["gpu_lease_root"],allowed_gpu_indices=list(range(8)),max_gpu_workers=6,max_workers_per_gpu=1,
        resource_policy=resources.resource_policy(),resource_recovery_policy=resources.resource_recovery_policy(),
        gpu_isolation_policy=resources.isolation.gpu_isolation_policy(),
        final_analysis_resource_policy=control.cpu_resource_policy("final_analysis"),
        materials_resource_policy=control.cpu_resource_policy("materials_preparation"),
        signal_policy=signals.signals_policy(),signal_source_bindings=signals.external_source_bindings(),
        recovery_policy=recovery_policy(),no_wallclock_deadlines=True,inherited_resource_wait_seconds=0.0))
    b.publish(b.ROOT/"prepared/record.json",dict(status="PREPARED",protocol=b.entry(b.ROOT/"protocol/record.json"),
        implementation_id=manifest["id"],new_model_calls=0,CUDA_initialized=False,supervisor_started=False,
        selected_tasks=128,training_paths=1,optimizer_updates_planned=298,development_sessions_planned=883,
        material_support_not_yet_observed=True,disk_free_bytes=free_disk))
    return dict(status="PREPARED",protocol_id=protocol["id"],implementation_id=manifest["id"])


def checked_implementation(root=b.ROOT):
    global _IMPLEMENTATION
    b.require(Path(root).resolve()==b.ROOT,"foreign V75 root")
    if _IMPLEMENTATION is None:
        value=b.checked(b.ROOT/"implementation/record.json")
        b.require(set(value["sha256"])==set(FILES),"implementation set changed")
        for name,sha in value["sha256"].items():
            b.require(b.sha(b.ROOT/"implementation"/name)==sha,"frozen source changed")
        _IMPLEMENTATION=value
    return _IMPLEMENTATION


def checked_protocol(root=b.ROOT):
    global _PROTOCOL
    if _PROTOCOL is None:
        manifest=checked_implementation(root);p=b.checked(b.ROOT/"protocol/record.json")
        b.require(p["scientific_contract"]==scientific_contract() and p["implementation"]["id"]==manifest["id"]
            and p["recovery_policy"]==recovery_policy(),"frozen V75 contract changed")
        training=importlib.import_module("finqa_v75_training")
        b.require(p["training_contract"]==training.training_contract()
            and p["baseline_compatibility"]==training.baseline_compatibility_policy(),"new/old consumer contract changed")
        importlib.import_module("finqa_v75_resources").validate_registered_contract(p)
        _PROTOCOL=p
    return _PROTOCOL


def allowed_import_sources(root=b.ROOT):
    value=checked_implementation(root)
    return dict(value["source_bindings"],**{str(b.ROOT/"implementation"/name):sha for name,sha in value["sha256"].items()})


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode",choices=("stage-inputs","freeze"))
    parser.add_argument("--source-commit",default="HEAD")
    parser.add_argument("--inputs",type=Path)
    parser.add_argument("--stratification",type=Path)
    args=parser.parse_args()
    result=(stage_prepared_inputs(args.inputs,args.stratification) if args.mode=="stage-inputs" else freeze(args.source_commit))
    print(json.dumps(result,ensure_ascii=False))
