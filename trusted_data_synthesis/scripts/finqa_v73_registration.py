"""Freeze the bounded P/H/L single-response probe, without scientific calls."""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import subprocess

import finqa_v73_binding as b

FILES = tuple(f"finqa_v73_{name}.py" for name in (
    "binding", "registration", "inputs", "measurement", "runtime", "resources",
    "signals", "worker", "controller", "analysis", "entry"))
_IMPLEMENTATION = _PROTOCOL = None


def contract():
    return dict(schema="v73_same_context_single_response_contract.v1",
        models=["P", "H", "L"], condition_groups={"F": 48, "K": 48},
        candidate_counts={"F": 125, "K": 380}, histories=["P", "H", "L"],
        maximum_generation_calls=864, maximum_probability_sequences=288,
        generation_calls_per_unique_model_context=1, probability_sequences_per_model_task=1,
        model_shards=2, max_gpu_workers=6, per_gpu_workers=1,
        max_new_tokens=2048, greedy=True, temperature=0.0,
        source_prompt_token_exact=True, no_source_history_rewriting=True,
        deduplicate_before_science=True, missing_inputs_not_replaced=True,
        conditional_sample_not_population_accuracy=True, unknown_not_zero=True,
        primary_column="h_P", report_groups_separately=True,
        teacher_forcing_separate_from_free_generation=True,
        targets="actual saved parent response tokens including actual EOS",
        probability="raw full vocabulary logits float32 log_softmax; chunks of 64 positions",
        group_missing_value=None, new_optimizer_updates=0, new_LoRA_initializations=0,
        new_backward_calls=0, new_tools_executed=0, new_native_scores=0,
        new_feedback_sessions=0, new_class_passes=0, new_response_replays=0,
        new_VJP=0, external_API_calls=0, automatic_followup=False,
        new_episodes_or_new_EA_PA=False, output_categories_are_static_candidates_only=True,
        diagonal_is_reproduction_check_not_new_discovery=True,
        no_causal_fraction_of_history_or_unique_root_cause=True,
        no_significance_or_advancement_threshold=True)


def recovery_policy():
    return dict(schema="v73_actual_return_boundary_recovery.v1",
        complete_returns_reused=True, incomplete_new_model_call_is_UNKNOWN=True,
        UNKNOWN_state_source_numeric_or_implementation_failure_automatic_retry=False,
        confirmed_resource_failure_before_call_or_after_saved_return_only=True,
        retry_backoff_seconds=300, no_progress_retry_limit=3,
        controller_failure_automatic_restart=False,
        explicit_STOP_or_owner_signal_stops_recovery=True,
        arbitrary_stage_or_resource_wait_deadline=False,
        no_resampling_or_new_budget_on_retry=True)


def prepare_inputs(input_directory="inputs"):
    b.require(re.fullmatch(r"inputs(?:_revision_[0-9]{2})?", input_directory), "invalid independent input directory")
    input_path = b.PREPARATION_ROOT / input_directory / "record.json"
    b.require(not input_path.exists(), "input preparation already complete")
    inputs = importlib.import_module("finqa_v73_inputs")
    measurement = importlib.import_module("finqa_v73_measurement")
    loaded = inputs.load_sources()
    selection_path = b.PREPARATION_ROOT / "selection/record.json"
    if selection_path.exists():
        selection = b.checked(selection_path)
        b.require(selection["original_source_refs"] == loaded["source_refs"], "selected source bytes changed")
    else:
        selection = inputs.select_samples(loaded["scores"]["P"], loaded["scores"]["H"],
            loaded["scores"]["L"], loaded["invalid"])
        selection = b.publish(selection_path, dict(selection, original_source_refs=loaded["source_refs"]))
    # Selection is durable before any selected raw requests are materialized.
    tokenizer = inputs.load_tokenizer(loaded["registrations"])
    bundle = inputs.materialize_contexts(selection, loaded["registrations"], tokenizer,
        generation_roots=loaded["generation_roots"])
    for task_key, target in list(bundle["targets"].items()):
        try:
            target["grouping"] = measurement.annotate_parent_target(tokenizer,
                target["raw_generated_token_ids"], target["raw_text"], eos_ids=target["eos_token_ids"],
                actual_eos=target["actual_eos"], tools=target["tools"])
        except ValueError as error:
            bundle["unknown_targets"].append(dict(task_key=task_key, group=target["group"],
                status="UNKNOWN", source_model="P", phase="fixed_parent_token_grouping",
                reason=str(error), replacement=False))
            del bundle["targets"][task_key]
    bundle["dedup"]["planned_probability_sequences"] = 3 * len(bundle["targets"])
    b.publish(input_path, dict(bundle,
        selection=b.entry(selection_path),
        preparation_source_sha256={name: b.sha(b.REPO / "trusted_data_synthesis/scripts" / name)
            for name in ("finqa_v73_inputs.py", "finqa_v73_measurement.py")},
        original_source_refs=loaded["source_refs"],
        generation_registrations=loaded["registrations"],
        new_model_calls=0, CUDA_initialized=False, new_native_scores=0))
    return dict(status="INPUTS_PREPARED", selection=b.entry(selection_path),
        inputs=b.entry(input_path))


def model_bindings(inputs):
    coordinates = {"P": (b.V71_ROOT, "step0894"), "H": (b.V71_ROOT, "step1192"),
                   "L": (b.V72_ROOT, "step1192")}
    output = {}
    for label, (root, point) in coordinates.items():
        directory = root / "points" / point / "train"
        completed, accepted = b.checked(directory / "completed/record.json"), b.checked(directory / "accepted/record.json")
        actual = b.read_ref(accepted["actual_exit"])
        b.require(actual["actual_waitpid_observed"] and actual["returncode"] == 0
            and completed["status"] == "COMPLETE", "source checkpoint not actually accepted")
        cp = completed["final_checkpoint"]
        b.require(cp["step"] == (1192 if label == "P" else 1490), "wrong fixed checkpoint")
        registration = inputs["generation_registrations"][label]
        b.require(registration["checkpoint"] == cp,
            "original generation identity is not bound to the selected saved checkpoint")
        output[label] = dict(checkpoint=cp, accepted=b.entry(directory / "accepted/record.json"),
            actual_exit=accepted["actual_exit"], assets=registration["assets"],
            model_identity=registration["model_identity"])
    return output


def jobs_for(inputs):
    jobs = {}
    for model in ("P", "H", "L"):
        for shard in range(2):
            key = f"{model}.shard{shard}"
            belongs = lambda value: int(b.digest(value), 16) % 2 == shard
            jobs[key] = dict(job_id=key, id=key, model=model, shard=shard,
                kind="generate", memory_phase="generate", stage="generate", seed=137,
                context_ids=[key for key in sorted(inputs["contexts"]) if belongs(key)],
                target_keys=[key for key in sorted(inputs["targets"]) if belongs(key)])
    b.require(sum(len(j["context_ids"]) for j in jobs.values()) <= 864
        and sum(len(j["target_keys"]) for j in jobs.values()) <= 288, "probe budget exceeded")
    return jobs


def freeze(source_commit, input_directory="inputs"):
    b.require(not (b.ROOT / "implementation").exists(), "V73 implementation already frozen")
    b.require(re.fullmatch(r"inputs(?:_revision_[0-9]{2})?", input_directory), "invalid independent input directory")
    input_path = b.PREPARATION_ROOT / input_directory / "record.json"
    bundle = b.checked(input_path)
    b.require(bundle["contexts"] and bundle["targets"], "all-UNKNOWN input reconstruction blocks scientific dispatch")
    commit = subprocess.check_output(["git", "rev-parse", source_commit + "^{commit}"], cwd=b.REPO, text=True).strip()
    raw_files = {}
    for filename in FILES:
        relative = "trusted_data_synthesis/scripts/" + filename
        raw = subprocess.check_output(["git", "show", commit + ":" + relative], cwd=b.REPO)
        b.require(hashlib.sha256(raw).hexdigest() == b.sha(b.REPO / relative), "uncommitted production file: " + filename)
        raw_files[filename] = raw
    for filename, expected in bundle["preparation_source_sha256"].items():
        b.require(hashlib.sha256(raw_files[filename]).hexdigest() == expected, "prepared input producer changed")
    inherited_ref = b.entry(b.V72_ROOT / "implementation/record.json")
    inherited = b.read_ref(inherited_ref)
    sources = dict(inherited["source_bindings"])
    sources.update({str(b.V72_ROOT / "implementation" / name): sha for name, sha in inherited["sha256"].items()})
    # The original package initializer contains only its provenance docstring.
    # The program tokenizer is pinned by the original vendor PROVENANCE, not
    # by the earlier worker-import subset. Register these exact existing bytes.
    vendor = Path(inherited["frozen_source_root"]) / "trusted_synthesis/finance_research/metric_vendor"
    vendor_init = vendor / "__init__.py"
    b.require(vendor_init.read_bytes() == b'"""Pinned, licensed upstream metric implementations; see PROVENANCE.json."""\n', "original vendor initializer changed")
    provenance_path = vendor / "PROVENANCE.json"
    provenance = json.loads(provenance_path.read_bytes())
    expected_tokens = "b64686fab3de2053da53c40f01a14fac7783cae101d64af722c1b59d54269df2"
    b.require(provenance["files"]["finqa_evaluate.py"]["local_sha256"] == expected_tokens
        and b.sha(vendor / "finqa_evaluate.py") == expected_tokens, "original pure program tokenizer changed")
    sources[str(vendor_init)] = b.sha(vendor_init)
    sources[str(vendor / "finqa_evaluate.py")] = expected_tokens
    destination = b.ROOT / "implementation"
    destination.mkdir(parents=True, exist_ok=False)
    for name, raw in raw_files.items():
        with (destination / name).open("xb") as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    manifest = b.publish(destination / "record.json", dict(schema="v73_frozen_probe_implementation.v1",
        source_commit=commit, sha256={name: hashlib.sha256(raw).hexdigest() for name, raw in raw_files.items()},
        source_bindings=sources, inherited_manifest=inherited_ref,
        explicit_vendor_provenance=b.file_ref(provenance_path),
        frozen_source_root=inherited["frozen_source_root"],
        original_scientific_sources_modified=False))
    resources = importlib.import_module("finqa_v73_resources")
    signals = importlib.import_module("finqa_v73_signals")
    measurement = importlib.import_module("finqa_v73_measurement")
    controller = importlib.import_module("finqa_v73_controller")
    old_protocol = b.checked(b.V72_ROOT / "protocol/record.json")
    protocol = b.publish(b.ROOT / "protocol/record.json", dict(schema="v73_same_context_probe_protocol.v1",
        output_root=str(b.ROOT), source_commit=commit,
        user_plan=b.file_ref(b.USER_PLAN), authorization="参照审计修订并开展后续实验",
        implementation=b.entry(destination / "record.json"),
        selection=b.entry(b.PREPARATION_ROOT / "selection/record.json"), inputs=b.entry(input_path),
        rejected_preparation=b.entry(b.PREPARATION_ROOT / "preparation_closeout/record.json"),
        prior_execution_failure=b.entry(b.PREPARATION_ROOT / "execution_revision_01/closeout/record.json"),
        prior_cold_entry_audit=b.entry(b.PREPARATION_ROOT / "execution_revision_01/cold_entry_failure_audit/record.json"),
        continuation_scope="same authorized probe budget after diagnosed pre-CUDA policy-registration correction; old failed controller is never restarted",
        scientific_contract=contract(), measurement_policy=measurement.policy(),
        model_bindings=model_bindings(bundle), jobs=jobs_for(bundle),
        gpu_uuids=resources.GPU_UUIDS, cpu_affinity=resources.CPU_AFFINITY,
        gpu_priority=list(b.GPU_PRIORITY), gpu_lease_root=old_protocol["gpu_lease_root"],
        allowed_gpu_indices=list(range(8)), max_gpu_workers=6, max_workers_per_gpu=1,
        resource_policy=resources.resource_policy(), gpu_isolation_policy=resources.isolation.gpu_isolation_policy(),
        resource_recovery_policy=resources.resource_recovery_policy(),
        final_analysis_resource_policy=controller.cpu_resource_policy(),
        signal_policy=signals.signals_policy(), signal_source_bindings=signals.external_source_bindings(),
        recovery_policy=recovery_policy(), no_wallclock_deadlines=True,
        source_V72_closeout=b.entry(b.V72_ROOT / "closeout/record.json")))
    b.publish(b.ROOT / "prepared/record.json", dict(schema="v73_prepared.v1", status="PREPARED",
        protocol=b.entry(b.ROOT / "protocol/record.json"), implementation_id=manifest["id"],
        scientific_calls=0, CUDA_initialized=False, supervisor_started=False))
    return dict(status="PREPARED", protocol_id=protocol["id"], implementation_id=manifest["id"])


def checked_implementation(root=b.ROOT):
    global _IMPLEMENTATION
    b.require(Path(root).resolve() == b.ROOT, "foreign probe root")
    if _IMPLEMENTATION is None:
        value = b.checked(b.ROOT / "implementation/record.json")
        b.require(set(value["sha256"]) == set(FILES), "implementation set changed")
        for name, sha in value["sha256"].items():
            b.require(b.sha(b.ROOT / "implementation" / name) == sha, "frozen source changed")
        _IMPLEMENTATION = value
    return _IMPLEMENTATION


def checked_protocol(root=b.ROOT):
    global _PROTOCOL
    if _PROTOCOL is None:
        manifest = checked_implementation(root)
        p = b.checked(b.ROOT / "protocol/record.json")
        b.require(p["scientific_contract"] == contract() and p["implementation"]["id"] == manifest["id"]
            and p["recovery_policy"] == recovery_policy(), "frozen probe contract changed")
        importlib.import_module("finqa_v73_resources").validate_registered_contract(p)
        _PROTOCOL = p
    return _PROTOCOL


def allowed_import_sources(root=b.ROOT):
    manifest = checked_implementation(root)
    return dict(manifest["source_bindings"], **{str(b.ROOT / "implementation" / name): sha for name, sha in manifest["sha256"].items()})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare-inputs", "freeze"))
    parser.add_argument("--source-commit")
    parser.add_argument("--input-directory", default="inputs")
    args = parser.parse_args()
    print(json.dumps(prepare_inputs(args.input_directory) if args.mode == "prepare-inputs" else freeze(args.source_commit, args.input_directory)))
