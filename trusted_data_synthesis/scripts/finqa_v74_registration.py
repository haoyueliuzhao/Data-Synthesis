"""Freeze the bounded two-direction V74 hybrid continuation experiment."""
from __future__ import annotations
import argparse
import hashlib
import importlib
import os
from pathlib import Path
import subprocess
import finqa_v74_binding as b

FILES = tuple(f"finqa_v74_{name}.py" for name in (
    "binding", "registration", "inputs", "runtime", "resources", "signals",
    "worker", "controller", "evaluation", "entry"))
_IMPLEMENTATION = _PROTOCOL = None


def contract(maximum_new_model_calls):
    b.require(type(maximum_new_model_calls) is int and 0 <= maximum_new_model_calls <= 961,
              "residual model budget exceeds the authorized upper bound")
    return dict(schema="v74_cross_history_continuation_contract.v1",
        task_count=96, condition_groups={"F":48,"K":48}, condition_count=192,
        directions=["L_from_P", "P_from_L"], first_responses_reused=192,
        first_submit_candidates=147, first_nonterminal_candidates=31, first_no_call=14,
        maximum_new_model_calls=maximum_new_model_calls,
        conservative_new_model_call_bound=961, residual_budget_formula="max(0,32-b_i-1)",
        max_total_source_plus_successor_calls=32, max_new_tokens=2048, context_limit=24576,
        greedy=True, only_new_inference_model="P", max_gpu_workers=1,
        exact_original_first_response=True, restore_isolated_native_tool_state=True,
        verify_each_reconstructed_event=True, reconstruction_cost_separate=True,
        source_turn_receipt_identities_preserved=True, explicit_mixed_lineage=True,
        no_future_parent_answer_or_private_reference_in_model_input=True,
        no_history_truncation_or_second_chance_for_no_call=True,
        native_submit_records_program_without_extra_run=True,
        native_scores_only_after_all_192_terminal_and_actual_worker_exit=True,
        native_scores=192, old_native_scores_read_only=True,
        conditional_sample_not_population_accuracy=True, unknown_not_zero=True,
        report_groups_and_directions_separately=True,
        new_first_responses=0, new_probability_sequences=0, new_optimizer_updates=0,
        new_LoRA_initializations=0, new_backward_calls=0, new_feedback_sessions=0,
        new_class_passes=0, new_response_replays=0, new_VJP=0, external_API_calls=0,
        automatic_followup=False, no_training_gate=True, development_examples_not_training_data=True)


def recovery_policy():
    return dict(schema="v74_actual_return_boundary_recovery.v1",
        complete_model_and_tool_returns_reused=True, incomplete_new_call_is_UNKNOWN=True,
        UNKNOWN_state_source_numeric_or_implementation_failure_automatic_retry=False,
        confirmed_resource_failure_before_call_or_after_saved_return_only=True,
        retry_backoff_seconds=300, no_progress_retry_limit=3,
        controller_failure_automatic_restart=False,
        explicit_STOP_or_owner_signal_stops_recovery=True,
        arbitrary_stage_or_resource_wait_deadline=False,
        no_resampling_or_new_budget_on_retry=True)


def prepare_inputs():
    b.require(not (b.ROOT / "inputs/record.json").exists(), "V74 inputs already prepared")
    inputs = importlib.import_module("finqa_v74_inputs")
    bundle = inputs.prepare_inputs()
    return b.publish(b.ROOT / "inputs/record.json", dict(bundle,
        preparation_source_sha256={"finqa_v74_inputs.py":b.sha(b.REPO / "trusted_data_synthesis/scripts/finqa_v74_inputs.py")}))


def freeze(source_commit):
    b.require(not (b.ROOT / "implementation").exists(), "V74 already frozen")
    bundle = b.checked(b.ROOT / "inputs/record.json")
    conditions = bundle["conditions"]
    b.require(len(conditions) == 192, "fixed condition count differs")
    commit = subprocess.check_output(["git","rev-parse",source_commit+"^{commit}"],cwd=b.REPO,text=True).strip()
    raw_files = {}
    for filename in FILES:
        relative = "trusted_data_synthesis/scripts/" + filename
        raw = subprocess.check_output(["git","show",commit+":"+relative],cwd=b.REPO)
        b.require(hashlib.sha256(raw).hexdigest() == b.sha(b.REPO / relative), "uncommitted production file: "+filename)
        raw_files[filename] = raw
    for filename, expected in bundle["preparation_source_sha256"].items():
        b.require(hashlib.sha256(raw_files[filename]).hexdigest() == expected, "input producer bytes changed")
    inherited_ref = b.entry(b.V73_ROOT / "implementation/record.json")
    inherited = b.read_ref(inherited_ref)
    b.require(inherited["id"] == b.V73_IMPLEMENTATION_ID, "wrong V73 implementation")
    sources = dict(inherited["source_bindings"])
    sources.update({str(b.V73_ROOT / "implementation" / name):sha for name,sha in inherited["sha256"].items()})
    destination = b.ROOT / "implementation"
    destination.mkdir(parents=True,exist_ok=False)
    for name,raw in raw_files.items():
        with (destination/name).open("xb") as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    manifest = b.publish(destination / "record.json",dict(schema="v74_frozen_implementation.v1",
        source_commit=commit,sha256={name:hashlib.sha256(raw).hexdigest() for name,raw in raw_files.items()},
        source_bindings=sources,inherited_manifest=inherited_ref,
        frozen_source_root=inherited["frozen_source_root"],original_scientific_sources_modified=False))
    resources = importlib.import_module("finqa_v74_resources")
    signals = importlib.import_module("finqa_v74_signals")
    controller = importlib.import_module("finqa_v74_controller")
    old = b.checked(b.V73_ROOT / "protocol/record.json")
    closeout = b.checked(b.V73_ROOT / "closeout/record.json")
    b.require(closeout["status"] == "COMPLETE", "V73 not complete")
    maximum = sum(c["remaining_model_calls"] for c in conditions)
    job = dict(job_id="P.continuation", id="P.continuation",model="P",kind="generate",
        stage="generate",memory_phase="generate",seed=137,condition_ids=[c["condition_id"] for c in conditions])
    p = b.publish(b.ROOT / "protocol/record.json",dict(schema="v74_hybrid_continuation_protocol.v1",
        output_root=str(b.ROOT),source_commit=commit,user_plan=b.file_ref(b.USER_PLAN),
        authorization="参照审计修订并开展后续实验",implementation=b.entry(destination / "record.json"),
        inputs=b.entry(b.ROOT / "inputs/record.json"),scientific_contract=contract(maximum),
        source_V73_closeout=b.entry(b.V73_ROOT / "closeout/record.json"),source_V73_protocol=b.entry(b.V73_ROOT / "protocol/record.json"),
        model_bindings={k:old["model_bindings"][k] for k in ("P","L")},jobs={job["job_id"]:job},
        gpu_uuids=resources.GPU_UUIDS,cpu_affinity=resources.CPU_AFFINITY,
        gpu_priority=list(b.GPU_PRIORITY),gpu_lease_root=old["gpu_lease_root"],
        allowed_gpu_indices=list(range(8)),max_gpu_workers=1,max_workers_per_gpu=1,
        resource_policy=resources.resource_policy(),gpu_isolation_policy=resources.isolation.gpu_isolation_policy(),
        resource_recovery_policy=resources.resource_recovery_policy(),
        final_analysis_resource_policy=controller.cpu_resource_policy(),
        signal_policy=signals.signals_policy(),signal_source_bindings=signals.external_source_bindings(),
        recovery_policy=recovery_policy(),no_wallclock_deadlines=True))
    b.publish(b.ROOT / "prepared/record.json",dict(schema="v74_prepared.v1",status="PREPARED",
        protocol=b.entry(b.ROOT / "protocol/record.json"),implementation_id=manifest["id"],
        scientific_calls=0,CUDA_initialized=False,supervisor_started=False))
    return dict(status="PREPARED",protocol_id=p["id"],implementation_id=manifest["id"])


def checked_implementation(root=b.ROOT):
    global _IMPLEMENTATION
    b.require(Path(root).resolve() == b.ROOT, "foreign V74 root")
    if _IMPLEMENTATION is None:
        value = b.checked(b.ROOT / "implementation/record.json")
        b.require(set(value["sha256"]) == set(FILES), "implementation set changed")
        for name,sha in value["sha256"].items():
            b.require(b.sha(b.ROOT / "implementation" / name) == sha, "frozen source changed")
        _IMPLEMENTATION = value
    return _IMPLEMENTATION


def checked_protocol(root=b.ROOT):
    global _PROTOCOL
    if _PROTOCOL is None:
        manifest = checked_implementation(root)
        p = b.checked(b.ROOT / "protocol/record.json")
        maximum = p["scientific_contract"]["maximum_new_model_calls"]
        b.require(p["scientific_contract"] == contract(maximum) and p["implementation"]["id"] == manifest["id"]
            and p["recovery_policy"] == recovery_policy(), "frozen contract changed")
        importlib.import_module("finqa_v74_resources").validate_registered_contract(p)
        _PROTOCOL = p
    return _PROTOCOL


def allowed_import_sources(root=b.ROOT):
    manifest=checked_implementation(root)
    return dict(manifest["source_bindings"],**{str(b.ROOT / "implementation" / n):s for n,s in manifest["sha256"].items()})


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode",choices=("prepare-inputs","freeze"))
    parser.add_argument("--source-commit",default="HEAD")
    args=parser.parse_args()
    result=prepare_inputs() if args.mode=="prepare-inputs" else freeze(args.source_commit)
    print({k:result.get(k) for k in ("status","id","protocol_id","implementation_id")})
