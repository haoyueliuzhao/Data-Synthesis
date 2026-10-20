"""One prospective, independently frozen balanced feedback repetition.

Preparation reads completed parents and metadata, not model/gradient Tensors.
The original 96 execution files and all historical records remain unchanged.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess

import finqa_v63_binding as binding

ROOT, OLD_ROOT, REPO = binding.ROOT, binding.OLD_ROOT, binding.REPO
SCHEMA = "v63_prospective_balanced_feedback_repetition.v1"
IMPLEMENTATION_SCHEMA = "v63_independent_frozen_implementation.v1"
PREPARED_SCHEMA = "v63_metadata_preparation_complete.v1"
FILES = tuple("finqa_v63_" + name + ".py" for name in (
    "binding", "registration", "entry", "signals", "gpu_isolation", "runtime",
    "temperature", "draw_components", "training", "worker", "worker_audit",
    "statistics", "evaluation", "diagnostics", "queue_base", "controller"))
GPU_PRIORITY = [7, 2, 1, 6, 0, 4, 5, 3]
require, checked, publish = binding.require, binding.checked, binding.publish
_IMPLEMENTATION = None
_PROTOCOL = None


def modules():
    binding.install_scientific_paths()
    # The same canonical helper is loaded before the historical driver imports.
    importlib.import_module("finqa_v63_entry").install_registered_auxiliary()
    return {name: importlib.import_module("finqa_v63_" + name) for name in
            ("training", "runtime", "controller", "evaluation", "diagnostics",
             "temperature", "signals", "gpu_isolation")}


def scientific_contract():
    return dict(
        schema="v63_one_balanced_feedback_repetition_scientific_contract.v1",
        parent_seeds=list(binding.SEEDS), parent_arm="C-only",
        real_parent_step=596, real_parent_phase="step", parent_outer_done=[298],
        actual_training_starts_from_theta_bar=False,
        new_arms=list(binding.ARMS), feedback_temperatures=binding.TEMPERATURES,
        old_feedback_batch=0, new_feedback_batch=1,
        old_endpoint_conditions_read_only=9, new_endpoint_conditions=6,
        logical_endpoint_conditions=15, independent_training_parent_count=3,
        new_C1_is_actual_new_feedback_and_training=True,
        per_condition_feedback_tasks=350, feedback_draw_seeds=list(binding.DRAW_SEEDS),
        per_condition_feedback_denominator=700, zero_reward_episodes_in_denominator=True,
        batch_temperature_point_config_roster_identity_required=True,
        old_and_new_feedback_pooled=False, old_or_new_best_selection=False,
        probability="softmax(raw_logits/T), complete actual trajectory including EOS",
        derivative="log_softmax(raw_logits/T), normalization and 1/T retained",
        feedback_gradient_SFT_mask=False, trajectory_length_normalized=False,
        old_gJ_reused_or_rescaled=False, new_feedback_sessions=4200,
        training_update_interval=[597, 894], actual_updates_per_new_branch=298,
        new_optimizer_updates=1788, fixed_own_q=True, real_SFT_dropout=0.05,
        saved_snapshots=[745, 894], primary_endpoint=894, outer_at894=False,
        old_material_task_count=744, old_material_state_count=1360,
        old_material_package_count=2468, old_material_effective_rows=4974,
        new_class_forward_passes=0, original_complete_task_gradients_read_only=True,
        class_G_and_theta_bar_reconstructed_in_original_order_and_bitwise_checked=True,
        original_parent_rng_Adam_schedule_loss_mask_clip_materials_unchanged=True,
        contribution_exponent=0.8, novelty_exponent=0.0,
        original_RMS_floor_sigmoid_history_and_prior_anchors_unchanged=True,
        full_trajectory_logP_and_reward_parser_unchanged=True,
        formal_response_sum_order_unchanged=True, formal_replay_denominator=700,
        draw_diagnostic_denominator=350, draw_components=[101, 103],
        formal_and_two_draw_buffers_share_one_atomic_response_checkpoint=True,
        draw_mean_tolerances=dict(atol=1e-7, rtol=2e-4,
            source="V54_CPU_full_autograd_gradient_comparison"),
        diagnostic_extra_VJPs_per_condition=2,
        diagnostic_extra_centered_inner_product_passes_per_condition=2,
        diagnostic_extra_VJPs_total=12, diagnostic_extra_inner_product_passes_total=12,
        formal_q_from_formal_C_once=True, mean_of_normalized_draw_q_forbidden=True,
        diagnostic_costs_counted_in_actual_resources=True,
        new_evaluation_jobs=24, new_evaluation_sessions=7458,
        new_total_logical_sessions=11658, new_step745_evaluation=0,
        new_test_evaluation=0, new_Hold_training_or_generation=0,
        all_six_training_branches_and_actual_exits_before_evaluation=True,
        all_24_generations_and_actual_exits_before_any_scoring=True,
        evaluator_temperature_is_not_training_feedback_temperature=True,
        greedy_evaluation_seed=20260928, random_evaluation_seeds=[11, 29],
        random_evaluation_temperature=1.0,
        external_API_calls=0, api_model="deepseek-flash",
        provider="same_local_frozen_Student",
        new_primary="C05,b1 minus C1,b1 on dev883 greedy",
        key_secondary="C05,b1 minus old Hold", also_report="C1,b1 minus old Hold",
        primary_net_correct_at_least=27, key_secondary_net_correct_at_least=1,
        research_value_threshold_pp=1.0, significance_or_power_claim=False,
        old_advance_record_preserved=True, old_batch_not_in_new_primary=True,
        dev_cal_not_unseen_confirmation_sets=True, UNKNOWN_not_zero=True,
        every_parent_positive_required=False, every_auxiliary_positive_required=False,
        automatic_followup_authorized=False, default_temperature_baseline=1.0)


def original_evidence():
    paths = dict(protocol=OLD_ROOT / "protocol/record.json",
        implementation=OLD_ROOT / "implementation/record.json",
        closeout=OLD_ROOT / "signal_recovery_04/closeout/record.json",
        supervisor_closeout=OLD_ROOT / "signal_recovery_04/supervisor/closeout/record.json",
        controller_launch=OLD_ROOT / "signal_recovery_04/supervisor/attempts/attempt0001/launch/record.json",
        controller_exit=OLD_ROOT / "signal_recovery_04/supervisor/attempts/attempt0001/actual_exit/record.json",
        evaluation_registration=OLD_ROOT / "evaluations/registration/record.json")
    refs = {key: binding.entry(path) for key, path in paths.items()}
    old = {key: binding.read_ref(ref) for key, ref in refs.items()}
    require(old["protocol"]["id"] == binding.OLD_PROTOCOL_ID
            and old["implementation"]["id"] == binding.OLD_IMPLEMENTATION_ID
            and old["closeout"]["id"] == binding.OLD_CLOSEOUT_ID
            and old["closeout"]["status"] == "COMPLETE"
            and old["closeout"]["accepted_jobs"] == 68
            and old["closeout"]["active_workers"] == 0,
            "only the actually complete old temperature experiment can be inherited")
    require(old["supervisor_closeout"]["status"] == "COMPLETE",
            "the completed original controller must have an actual successful supervisor closeout")
    require(old["controller_exit"]["actual_waitpid_observed"] is True
            and old["controller_exit"]["returncode"] == 0
            and all(old["controller_exit"][key] == old["controller_launch"][key]
                    for key in ("pid", "birth")),
            "old COMPLETE must be backed by its actual controller waitpid exit zero")
    return refs, old


def _checkpoint_metadata(reference):
    directory = Path(reference["path"])
    require(binding.sha(directory / "record.json") == reference["record_sha256"],
            "original checkpoint metadata changed")
    require((directory / "state.pt").is_file(),
            "the actual original checkpoint Tensor is required, not only its JSON receipt")


def parent_metadata(seed):
    parent = checked(OLD_ROOT / f"parents/seed{seed}/record.json")
    require(parent["protocol_id"] == binding.OLD_PROTOCOL_ID and parent["seed"] == seed
            and parent["c1_reuse"]["eligible"] is True
            and parent["real_parent_is_virtual_point"] is False,
            "completed actual pre596 parent required")
    _checkpoint_metadata(parent["parent_checkpoint"])
    _checkpoint_metadata(parent["old_outer_checkpoint"])
    binding.read_ref(parent["task_plan"])
    old_branches = {}
    for arm in ("Hold", "C1", "C05"):
        path = OLD_ROOT / f"branches/seed{seed}/{arm}/completed/record.json"
        result = checked(path)
        require(result["status"] == "COMPLETE"
                and result["parent_state_digest"] == parent["parent_state_digest"]
                and set(result["snapshots"]) == {"745", "894"},
                "read-only historical branch does not match the shared parent")
        for reference in result["snapshots"].values():
            _checkpoint_metadata(reference)
        old_branches[arm] = binding.entry(path)
    return dict(original_parent=binding.entry(OLD_ROOT / f"parents/seed{seed}/record.json"),
                old_branches=old_branches, scientific_Tensors_loaded=False)


def freeze(root, commit):
    require(Path(root).resolve() == ROOT and not ROOT.exists(),
            "V63 requires its one fresh independent scientific directory")
    commit = subprocess.check_output(["git", "rev-parse", commit + "^{commit}"],
                                    cwd=REPO, text=True).strip()
    old = checked(OLD_ROOT / "implementation/record.json")
    require(old["id"] == binding.OLD_IMPLEMENTATION_ID and len(old["sha256"]) == 96,
            "the original mathematical execution bundle changed")
    sources = {}
    for name, expected in old["sha256"].items():
        raw = (OLD_ROOT / "implementation" / name).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == expected, "original frozen source changed")
        sources[name] = raw
    for name in FILES:
        relative = "trusted_data_synthesis/scripts/" + name
        raw = subprocess.check_output(["git", "show", commit + ":" + relative], cwd=REPO)
        require(hashlib.sha256(raw).hexdigest() == binding.sha(REPO / relative),
                "uncommitted V63 execution source: " + name)
        require(name not in sources, "new implementation must not overwrite any original file")
        sources[name] = raw
    destination = ROOT / "implementation"
    destination.mkdir(parents=True, exist_ok=False)
    for name, raw in sources.items():
        with (destination / name).open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    return publish(destination / "record.json", dict(schema=IMPLEMENTATION_SCHEMA,
        source_commit=commit, committed_files=list(FILES),
        sha256={name: hashlib.sha256(raw).hexdigest() for name, raw in sources.items()},
        original_implementation=binding.entry(OLD_ROOT / "implementation/record.json"),
        original_96_files_byte_identical=True,
        external_frozen_source_sha256=old["external_frozen_source_sha256"],
        frozen_source_root=old["frozen_source_root"], historical_files_modified=False))


def checked_implementation(root=ROOT):
    global _IMPLEMENTATION
    require(Path(root).resolve() == ROOT, "foreign V63 implementation root")
    if _IMPLEMENTATION is not None:
        return _IMPLEMENTATION
    value = checked(ROOT / "implementation/record.json")
    old = binding.read_ref(value["original_implementation"])
    require(value["schema"] == IMPLEMENTATION_SCHEMA
            and old["id"] == binding.OLD_IMPLEMENTATION_ID
            and value["committed_files"] == list(FILES)
            and set(value["sha256"]) == set(old["sha256"]) | set(FILES)
            and len(value["sha256"]) == 96 + len(FILES)
            and all(value["sha256"][name] == expected for name, expected in old["sha256"].items())
            and value["external_frozen_source_sha256"] == old["external_frozen_source_sha256"]
            and value["frozen_source_root"] == old["frozen_source_root"],
            "new independent bundle differs from its frozen mathematical lineage")
    for name, expected in value["sha256"].items():
        require(binding.sha(ROOT / "implementation" / name) == expected,
                "registered V63 source bytes changed: " + name)
    for path, expected in value["external_frozen_source_sha256"].items():
        require(binding.sha(path) == expected, "external scientific source bytes changed: " + path)
    _IMPLEMENTATION = value
    return value


def _policy_fields(loaded):
    return dict(scientific_contract=scientific_contract(),
        evaluation=loaded["evaluation"].evaluation_contract(),
        diagnostics_policy=loaded["diagnostics"].policy(),
        resource_policy=loaded["runtime"].resource_policy(),
        resource_recovery_policy=loaded["runtime"].resource_recovery_policy(),
        auto_recovery_policy=loaded["controller"].auto_recovery_policy(),
        gpu_isolation_policy=loaded["gpu_isolation"].gpu_isolation_policy(),
        signal_policy=loaded["signals"].signals_policy(),
        signal_source_bindings=loaded["signals"].external_source_bindings())


def checked_protocol(root=ROOT):
    global _PROTOCOL
    require(Path(root).resolve() == ROOT, "foreign prospective experiment root")
    if _PROTOCOL is not None:
        return _PROTOCOL
    value = checked(ROOT / "protocol/record.json")
    loaded = modules()
    require(value["schema"] == SCHEMA and value["output_root"] == str(ROOT)
            and value["implementation"]["id"] == checked_implementation()["id"]
            and all(value[key] == expected for key, expected in _policy_fields(loaded).items())
            and value["max_gpu_workers"] == 6 and value["max_workers_per_gpu"] == 1
            and value["allowed_gpu_indices"] == list(range(8))
            and value["gpu_uuids"] == loaded["runtime"].GPU_UUIDS
            and value["cpu_affinity"] == loaded["runtime"].CPU_AFFINITY
            and value["gpu_priority"] == GPU_PRIORITY
            and value["gpu_lease_root"] == str(loaded["controller"].base.GPU_LEASE_ROOT)
            and value["inherited_resource_wait_seconds"] == 0.0,
            "prospective scientific, resource, process or signal contract changed")
    require(binding.read_ref(value["original_completed_experiment"]["closeout"])["id"]
            == binding.OLD_CLOSEOUT_ID, "historical completed result changed")
    _PROTOCOL = value
    return value


def checked_prepared(root=ROOT):
    require(Path(root).resolve() == ROOT, "foreign prepared experiment root")
    value = checked(ROOT / "prepared/record.json")
    protocol = checked_protocol(root)
    require(value["schema"] == PREPARED_SCHEMA and value["protocol"]["id"] == protocol["id"]
            and set(value["parents"]) == {str(seed) for seed in binding.SEEDS}
            and value["actual_new_optimizer_budget"] == 1788
            and value["new_feedback_sessions"] == 4200
            and value["new_evaluation_sessions"] == 7458
            and value["new_class_task_count"] == 0
            and value["scientific_supervisor_started"] is False
            and value["CUDA_initialized"] is False,
            "preparation must bind all three actual parents and the exact new dose")
    return value


def prepare(source_commit):
    require(not ROOT.exists(), "a prepared or partially frozen V63 root cannot be overwritten")
    loaded = modules()
    refs, old = original_evidence()
    metadata = {str(seed): parent_metadata(seed) for seed in binding.SEEDS}
    # Check only existing process identities, never signal historical controls.
    for suffix in ("signal_recovery_04/supervisor/launch/record.json",
                   "signal_recovery_04/controllers/attempt0001/launch/record.json"):
        path = OLD_ROOT / suffix
        if path.is_file():
            launch = checked(path)
            require(loaded["runtime"].birth(launch["pid"]) != launch["birth"],
                    "historical control identity is still active")
    source_ref = old["protocol"]["evaluation_source_registration"]
    binding.read_ref(source_ref)
    old_plan = old["evaluation_registration"]
    summaries = {}
    for panel, *_ in loaded["evaluation"].PANEL_SPECS:
        path = OLD_ROOT / "evaluations/panels" / panel / "summary/record.json"
        summary = checked(path)
        require(summary["registration_id"] == old_plan["id"],
                "old comparison panel belongs to a different evaluation")
        summaries[panel] = binding.entry(path)
    # Six real 298-step trajectories retain all new committed checkpoints.
    minimum_disk = 160 * 1024 ** 3
    free_disk = shutil.disk_usage(ROOT.parent).free
    require(free_disk >= minimum_disk, "insufficient disk for registered new durable trajectories")
    policies = _policy_fields(loaded)
    user_audit = binding.file_ref(binding.USER_AUDIT)
    implementation = freeze(ROOT, source_commit)
    protocol = publish(ROOT / "protocol/record.json", dict(schema=SCHEMA,
        output_root=str(ROOT), source_commit=implementation["source_commit"],
        authorization="参照审计修订并开展后续实验",
        user_audit=user_audit,
        implementation=binding.entry(ROOT / "implementation/record.json"),
        original_completed_experiment=refs, original_parent_metadata=metadata,
        evaluation_source_registration=source_ref,
        old_evaluation_registration=refs["evaluation_registration"],
        old_evaluation_summaries=summaries,
        allowed_gpu_indices=list(range(8)), gpu_uuids=loaded["runtime"].GPU_UUIDS,
        cpu_affinity=loaded["runtime"].CPU_AFFINITY, gpu_priority=GPU_PRIORITY,
        gpu_lease_root=str(loaded["controller"].base.GPU_LEASE_ROOT),
        max_gpu_workers=6, max_workers_per_gpu=1,
        initialization_wait_and_draining_count_as_workers=True,
        no_wallclock_deadlines=True, inherited_resource_wait_seconds=0.0,
        historical_resource_wait_not_erased=True,
        waiting_statistics_are_for_new_independent_experiment=True,
        account_cron_installed_by_this_protocol=False,
        independent_machine_wide_observer_started=False,
        preparation_GPU7_holder_is_not_scientific_worker=True,
        previous_UNKNOWN_reexecution_permissions_carried_forward=False,
        **policies))
    for seed in binding.SEEDS:
        loaded["training"].prepare_parent(ROOT, seed, protocol["id"])
    subprocess.run([str(binding.PYTHON), str(ROOT / "implementation/finqa_v63_diagnostics.py"),
                    "prepare", "--root", str(ROOT)], cwd=REPO, check=True)
    return publish(ROOT / "prepared/record.json", dict(schema=PREPARED_SCHEMA,
        protocol=binding.entry(ROOT / "protocol/record.json"),
        parents={str(seed): binding.entry(ROOT / f"parents/seed{seed}/record.json")
                 for seed in binding.SEEDS},
        original_parent_metadata=metadata, original_validation_not_repeated=True,
        original_Tensor_checks_at_actual_consumption=True,
        actual_new_optimizer_budget=1788, new_feedback_sessions=4200,
        new_evaluation_sessions=7458, new_total_sessions=11658,
        new_class_task_count=0, read_only_historical_complete_class_tasks=2232,
        original_complete_cache_binding_checked_when_assembled=True,
        scientific_supervisor_started=False, CUDA_initialized=False,
        model_loaded=False, scientific_calls=0,
        disk_free_bytes=free_disk, disk_minimum_admission_bytes=minimum_disk,
        CPU_preparation_only=True, frozen_entry_check_imports_still_required=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-commit", required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.source_commit), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
