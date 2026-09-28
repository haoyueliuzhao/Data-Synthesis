"""Experiment 1–3 execution design/readiness, never a training implementation.

Admission examines supplied claims in existing inventory/resolution/encoding
formats. It does not open or verify claimed files, so it can NEVER authorize a
real launch. No model, API, GPU, optimizer, scoring or artifact writes occur here.
"""

from __future__ import annotations

import copy
import random
import re
from collections import Counter
from fractions import Fraction

from .contracts import digest
from .v6_distribution import ARMS, OUTER_STEPS

SEEDS = (11, 29, 47)
TASKS, BATCH_SIZE, EPOCHS, FINAL_STEP = 1000, 5, 10, 2000
INVENTORY_PRODUCER = "v6_decomposed_review.inventory"
RESOLUTION_SCHEMAS = {"v6_decomposed_pair_resolution.v3", "v7_decomposed_pair_resolution.v1"}
ENCODING_SCHEMAS = {"v6_student_encoding.v1", "v7_student_encoding.v1"}


def _roster(task_ids):
    values = list(task_ids)
    if (
        len(values) != TASKS
        or len(set(values)) != TASKS
        or any(not isinstance(value, str) or not value for value in values)
    ):
        raise ValueError("exact original ordered 1000-task roster required")
    return values


def _sha(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def build_task_schedule(original_task_ids, seed):
    """Freeze concrete five-task batches; every arm of a seed consumes this same schedule."""
    tasks = _roster(original_task_ids)
    if type(seed) is not int or seed not in SEEDS:
        raise ValueError("paired seed must be 11, 29 or 47")
    rng, batches = random.Random(seed), []
    for epoch in range(1, EPOCHS + 1):
        permutation = list(tasks)
        rng.shuffle(permutation)
        for offset in range(0, TASKS, BATCH_SIZE):
            batches.append(
                dict(
                    step=len(batches) + 1,
                    epoch=epoch,
                    batch_index=offset // BATCH_SIZE,
                    task_ids=permutation[offset : offset + BATCH_SIZE],
                )
            )
    body = dict(
        schema="v6_five_arm_task_schedule.v1",
        seed=seed,
        original_task_ids_sha256=digest(tasks),
        epochs=EPOCHS,
        batch_size=BATCH_SIZE,
        updates=FINAL_STEP,
        shuffle="local Python Random(seed); shuffle fresh original order each epoch",
        same_schedule_for_all_arms=True,
        batches=batches,
    )
    return {**body, "schedule_sha256": digest(body)}


def assess_material_admission(original_task_ids, claim=None, *, source_binding=None):
    """Validate readiness claims without inventing a new required material format.

    claim wraps existing records as {record, file_sha256}: inventory, per-task
    resolutions, and per-original-slot encodings. The wrapper is only an input
    argument, NOT a new artifact schema the future collector must migrate to.
    All file SHA values are claims; launching must actually verify their bytes.
    """
    failures, tasks, all_slots, eligible, counts = [], [], set(), {}, Counter()
    priors = {}

    def reject(reason, **context):
        failures.append(dict(reason=reason, **context))

    try:
        tasks = _roster(original_task_ids)
    except (TypeError, ValueError):
        reject("not_original_1000_task_roster")
    if claim is None:
        reject("material_inventory_and_student_encodings_not_supplied")
    elif not isinstance(claim, dict):
        reject("unrecognized_material_claim")
    elif tasks:
        try:
            inventory_entry = claim["inventory"]
            inventory = inventory_entry["record"]
            # The actual decomposed inventory currently has no schema key.
            # An explicit producer distinguishes it from older 6+2/165-scope pools.
            if (
                claim.get("inventory_producer") != INVENTORY_PRODUCER
                or inventory.get("schema") is not None
            ):
                reject("unknown_inventory_schema_or_producer")
            if not _sha(inventory_entry.get("file_sha256")):
                reject("missing_claimed_inventory_file_sha256")
            if (
                inventory.get("original_tasks") != TASKS
                or inventory.get("original_slots") != 8000
                or inventory.get("all_originals_retained") is not True
            ):
                reject("original_1000_by_8_inventory_not_retained")
            if inventory.get("completed_calls") != inventory.get(
                "slot_review_denominator", -1
            ) + inventory.get("alignment_denominator", -1):
                reject("registered_review_matrix_incomplete")
            if source_binding and source_binding.get("inventory_protocol_id") is not None:
                if inventory.get("protocol_id") != source_binding["inventory_protocol_id"]:
                    reject("inventory_protocol_does_not_match_registered_source")
            rows = inventory["tasks"]
            if [row["task_id"] for row in rows] != tasks:
                reject("inventory_original_task_roster_changed")
            rows_by_task = {row["task_id"]: row for row in rows}
            resolutions = claim["resolutions"]
            if set(resolutions) != set(tasks):
                reject("missing_or_extra_original_task_resolutions")
            for task in tasks:
                if task not in resolutions or task not in rows_by_task:
                    reject("missing_task_support", task_id=task)
                    continue
                entry, row = resolutions[task], rows_by_task[task]
                resolution = entry["record"]
                if not _sha(entry.get("file_sha256")):
                    reject("missing_claimed_resolution_file_sha256", task_id=task)
                if resolution.get("schema") not in RESOLUTION_SCHEMAS:
                    reject("unknown_resolution_schema", task_id=task)
                    continue
                if resolution.get("task_id") != task:
                    reject("resolution_task_identity_mismatch", task_id=task)
                slots = resolution["slots"]
                if (
                    len(slots) != 8
                    or all_slots & set(slots)
                    or resolution.get("all_eight_candidates_retained") is not True
                    or resolution.get("no_dropping_hard_to_map_valid_packages") is not True
                ):
                    reject("original_slots_missing_duplicated_or_filtered", task_id=task)
                all_slots.update(slots)
                valid = {
                    sid: slot
                    for sid, slot in slots.items()
                    if slot.get("q_native") is True and slot.get("v_trace") == "valid"
                }
                if set(resolution.get("valid_slots_retained", [])) != set(valid) or len(
                    resolution.get("valid_slots_retained", [])
                ) != len(valid):
                    reject("joint_valid_original_package_was_omitted", task_id=task)
                if not valid:
                    reject("missing_task_support", task_id=task)
                if (
                    resolution.get("task_mapping") != "complete"
                    or row.get("mapping_complete") is not True
                ):
                    reject("whole_task_mapping_incomplete", task_id=task)
                state_counts, chi = Counter(), {}
                for sid, slot in valid.items():
                    if (
                        slot.get("mapper") != "mapped"
                        or not slot.get("state_id")
                        or type(slot.get("chi")) is not int
                        or slot["chi"] not in (0, 1)
                    ):
                        reject("joint_valid_package_state_or_chi_unknown", slot_id=sid)
                    state = slot.get("state_id")
                    if state in chi and chi[state] != slot.get("chi"):
                        reject("within_state_chi_conflict", task_id=task)
                    chi[state] = slot.get("chi")
                    state_counts[state] += 1
                    manifest = slot.get("encoding_manifest")
                    if (
                        slot.get("mask_status") != "agreed"
                        or not isinstance(manifest, dict)
                        or manifest.get("mask_agreement") is not True
                        or manifest.get("not_a_TokenReceipt") is not True
                    ):
                        reject("joint_valid_package_mask_not_agreed", slot_id=sid)
                    eligible[sid] = (task, manifest)
                if (
                    row.get("joint_valid") != len(valid)
                    or row.get("n_x") != len(valid)
                    or row.get("states") != dict(state_counts)
                    or row.get("masks_complete") is not True
                ):
                    reject(
                        "inventory_support_does_not_match_all_joint_valid_originals", task_id=task
                    )
                if valid and None not in state_counts:
                    priors[task] = {
                        state: str(Fraction(n, len(valid))) for state, n in state_counts.items()
                    }
            if len(all_slots) != 8000:
                reject("not_all_8000_original_slots_assessed")
            if inventory.get("counts", {}).get("joint_valid") != len(eligible):
                reject("inventory_joint_valid_count_mismatch")
            if inventory.get("material_admission_only") is not True:
                reject("inventory_material_admission_not_established")
            encodings = claim["encodings"]
            if set(encodings) != set(eligible):
                reject("encoding_set_is_not_exactly_all_joint_valid_original_packages")
            codec = set()
            for sid, (task, manifest) in eligible.items():
                if sid not in encodings:
                    continue
                entry, record = encodings[sid], encodings[sid]["record"]
                if record.get("schema") not in ENCODING_SCHEMAS:
                    reject("unknown_student_encoding_schema", slot_id=sid)
                if not _sha(entry.get("file_sha256")):
                    reject("missing_claimed_encoding_file_sha256", slot_id=sid)
                if (
                    record.get("task_id") != task
                    or not isinstance(manifest, dict)
                    or record.get("episode_sha256") != manifest.get("episode_sha256")
                    or record.get("resolved_mask_sha256") != digest(manifest)
                ):
                    reject("encoding_episode_or_review_mask_binding_mismatch", slot_id=sid)
                if (
                    record.get("encoding_admitted") is not True
                    or record.get("context_limit") != 24576
                    or record.get("context_truncated") is not False
                    or record.get("api_original_sampling_tokens_claimed") is not False
                    or record.get("not_a_TokenReceipt") is not True
                    or type(record.get("L_P")) is not int
                    or record["L_P"] <= 0
                    or record.get("total_supervised_tokens") != record["L_P"]
                    or type(record.get("max_sequence_tokens")) is not int
                    or not 0 < record["max_sequence_tokens"] <= 24576
                ):
                    reject(
                        "student_encoding_not_complete_untruncated_positive_package", slot_id=sid
                    )
                if not all(
                    _sha(record.get(key)) for key in ("tokenizer_digest", "chat_template_digest")
                ):
                    reject("student_tokenizer_identity_absent", slot_id=sid)
                codec.add((record.get("tokenizer_digest"), record.get("chat_template_digest")))
                counts["supervised_tokens"] += (
                    record.get("L_P", 0) if type(record.get("L_P")) is int else 0
                )
            if len(codec) != 1:
                reject("student_tokenizer_identity_not_common")
        except (KeyError, TypeError, ValueError, AttributeError) as error:
            reject(
                "incomplete_or_unrecognized_existing_artifact_claim",
                error_type=type(error).__name__,
            )
    return dict(
        status="CLAIMS_STRUCTURALLY_READY" if not failures else "BLOCKED_MATERIAL_CLAIMS",
        claims_structurally_admitted=not failures,
        claim_validation_only=True,
        execution_admitted=False,
        actual_launch_requires_artifactverification=True,
        referenced_file_bytes_read_or_verified=False,
        no_model_or_training_outcome=True,
        original_task_count=len(tasks),
        original_slot_count=len(all_slots),
        joint_valid_packages_retained=len(eligible),
        mu="1/1000",
        empirical_prior=priors,
        claimed_total_supervised_tokens=counts["supervised_tokens"] if eligible else None,
        failures=failures,
        claim_sha256=digest(claim) if isinstance(claim, dict) else None,
    )


def assess_400_800_sharing(left, right):
    """Compatible claimed state is necessary, not verified permission to share work."""
    hashes = (
        "checkpoint_sha256",
        "parameters_sha256",
        "adam_state_sha256",
        "rng_state_sha256",
        "schedule_sha256",
        "inventory_sha256",
        "encoding_manifest_sha256",
        "mask_manifest_sha256",
        "prior_sha256",
        "pi_next_sha256",
        "optimizer_config_sha256",
        "G_sha256",
        "gJ_sha256",
        "C_sha256",
        "feedback_generation_seal_sha256",
    )
    missing = [key for key in hashes if not _sha(left.get(key)) or not _sha(right.get(key))]
    unequal = [key for key in hashes if left.get(key) != right.get(key)]
    coordinates = (
        set((left.get("arm"), right.get("arm"))) == {"C-only", "Full"}
        and left.get("seed") == right.get("seed") in SEEDS
        and left.get("step") == right.get("step") == 400
        and left.get("schedule_cursor") == right.get("schedule_cursor") == 400
        and left.get("feedback_sessions") == right.get("feedback_sessions") == 700
        and left.get("feedback_sealed_before_scoring") is True
        and right.get("feedback_sealed_before_scoring") is True
    )
    return dict(
        claims_compatible_for_sharing=coordinates and not missing and not unequal,
        claim_validation_only=True,
        actual_launch_requires_artifactverification=True,
        execution_admitted=False,
        budget_saving_applied=False,
        missing_hashes=missing,
        unequal_hashes=unequal,
        equal_reward_counts_are_not_identity_evidence=True,
    )


def build_execution_plan(original_task_ids, *, source_binding, material_claim=None):
    """Machine-readable preregistration design, with no claim that training occurred."""
    tasks = _roster(original_task_ids)
    schedules = {}
    for seed in SEEDS:
        schedule = build_task_schedule(tasks, seed)
        schedules[str(seed)] = {key: value for key, value in schedule.items() if key != "batches"}
    arms = []
    for seed in SEEDS:
        for arm in ARMS:
            arms.append(
                dict(
                    seed=seed,
                    arm=arm,
                    schedule_sha256=schedules[str(seed)]["schedule_sha256"],
                    shared_prefix=dict(
                        start=0, end=400, distribution="r", optimizer_rng_snapshot_required=True
                    ),
                    final_step=2000,
                    only_final_evaluation_checkpoint=2000,
                    outer_steps=list(OUTER_STEPS) if arm in {"C-only", "Full"} else [],
                    after_prefix=(
                        "r"
                        if arm == "Static"
                        else "fixed r*2**(+chi) normalized"
                        if arm == "Manual+"
                        else "fixed r*2**(-chi) normalized"
                        if arm == "Manual-"
                        else "automatic C only"
                        if arm == "C-only"
                        else "automatic C and N"
                    ),
                )
            )
    feedback = [
        dict(
            seed=seed,
            arm=arm,
            step=step,
            tasks=350,
            repeats=2,
            sessions=700,
            score_only_after_all_700_generation_sealed=True,
        )
        for seed in SEEDS
        for arm in ("C-only", "Full")
        for step in OUTER_STEPS
    ]
    dev = [
        dict(seed=row["seed"], arm=row["arm"], step=2000, decoder="greedy", tasks=883)
        for row in arms
    ]
    dev.append(dict(seed=None, arm="Base", step=0, decoder="greedy", tasks=883))
    body = dict(
        schema="finqa_v6_experiment123_execution_design.v1",
        status="DESIGN_AND_CPU_READINESS_ONLY",
        source_binding=copy.deepcopy(source_binding),
        original_task_ids=tasks,
        original_task_ids_sha256=digest(tasks),
        seeds=list(SEEDS),
        arm_names=list(ARMS),
        arms=arms,
        task_schedules=schedules,
        source_population=dict(
            sft=1000,
            feedback=350,
            calibration=120,
            dev=883,
            test=1147,
            mu="1/1000",
            all_joint_valid_original_packages_retained=True,
            shrink_to_supported_subset=False,
            filtering_by_C_NLL_length_style=False,
            independent_batches_must_not_be_spliced=True,
            single_state_tasks_stay_in_G=True,
        ),
        training=dict(
            epochs=10,
            tasks_per_update=5,
            updates_per_epoch=200,
            updates_per_final_model=2000,
            final_models=15,
            effective_model_history_steps=30000,
            original_base="Qwen2.5-7B-Instruct, not a previously trained Static checkpoint",
            lora=dict(target_modules=["q_proj", "v_proj"], rank=8, alpha=16, dropout=0.05),
            dtype=dict(base="bfloat16 frozen", lora="float32", adam="float32"),
            optimizer=dict(
                name="AdamW",
                lr=1e-4,
                betas=[0.9, 0.999],
                eps=1e-8,
                weight_decay=0,
                scheduler="constant",
                warmup_steps=0,
                clip_norm=1,
            ),
            update_order="sum all weighted rows of five complete tasks; clip once; update once",
            package_loss="sum accepted R/U/A/F/registered EOS NLL divided by whole-package L_P",
            coefficient="pi(x,z)/(5*n_xz*L_P)",
            additional_batch_division=False,
            tool_observations_are_targets=False,
            identical_masks_for_all_five_arms=True,
            withdrawn_errors_retained_as_context_not_positive_targets=True,
            context_limit=24576,
            truncation=False,
        ),
        interventions=dict(
            manual_plus="normalize(r*2**chi)",
            manual_minus="normalize(r*2**(-chi))",
            manual_uses_C=False,
            manual_is_reverse_direction_control=False,
            chi="evidenced consequential verification or semantic revision; not tool count",
            automatic_outer_steps=list(OUTER_STEPS),
            C_only_novelty_exponent=0,
            Full_novelty_exponent=0.2,
            prior_never_reset=True,
            all_zero_fixed_denominator_feedback=(
                "retain current pi exactly; no N-only motion or top-up"
            ),
        ),
        feedback=dict(
            logical_batches=feedback,
            sessions_per_batch=700,
            fixed_denominator=700,
            full_generation_seal_before_scoring=True,
            dropout_for_G_and_proxy=False,
            train_dropout_retained=True,
            utility="FinQA native execution at the same frozen public harness",
            raw_feedback_logP=(
                "all actually sampled R/U/actions/Final/EOS, including error/recovery"
            ),
            feedback_receipt=(
                "actual local TokenReceipt; offline API Student encoding is not accepted"
            ),
            never_apply_SFT_mask_to_feedback=True,
            dev_enters_gJ=False,
        ),
        sharing=dict(
            common_0_400_per_seed=True,
            common_prefix_artifact_verification_required=True,
            C_only_Full_400_800=(
                "conditional on actual identical theta/Adam/RNG/schedule/material/pi_next evidence"
            ),
            point800_N_comparison=(
                "same verified theta/Adam/pi/G/gJ/C and training RNG; otherwise not identified"
            ),
            later_steps1200_1600="compute G/feedback/C at each arm's own real point",
            reward_count_equality_permits_merging=False,
            savings_assumed=False,
        ),
        mechanism=dict(
            C_direction=dict(
                start_step=400,
                end_step=600,
                directions=["Static r", "q_plus", "2*r-q_plus"],
                reverse_is_not_Manual_minus=True,
                new_training_steps_per_seed=200,
                total_extra_training_steps=600,
                tasks=120,
                seeds=3,
                directions_count=3,
                stochastic_repeats=2,
                greedy_repeats=1,
                sessions=3240,
                main_Static_and_q_plus_checkpoints_reused_only_when_identical=True,
            ),
            N_same_point=dict(
                start_step=800,
                end_step=1000,
                conditions=["C-only", "Full"],
                same_point_identity_required=True,
                extra_training_branches=0,
                tasks=120,
                seeds=3,
                stochastic_repeats=2,
                greedy_repeats=1,
                sessions=2160,
                if_N_does_not_change_distribution="report not activated; do not manufacture effect",
            ),
            intermediate_checkpoints_for_selection=False,
            cross_repeat_diagnostics_use_existing_700=True,
            positive_gain_required_to_continue_other_registered_arms=False,
        ),
        evaluation=dict(
            dev_coordinates=dev,
            total_dev_sessions=14128,
            primary="mean_seed J(Full)-mean_seed J(Static)",
            secondary="Full-C-only",
            manual_comparisons=["Manual+-Static", "Manual--Static"],
            Static_minus_Base="learning diagnostic, not VTDO effect",
            blind_test_in_this_batch=False,
            later_test=dict(
                tasks=1147,
                arms=["Static", "Full"],
                seeds=3,
                sessions=6882,
                separate_registration=True,
                adaptive_candidate_replacement=False,
            ),
        ),
        budgets=dict(
            core_physical_SFT_steps_conservative=25200,
            core_physical_SFT_steps_if_identity_verified=24000,
            mechanism_reverse_extra_steps=600,
            feedback_sessions_conservative=16800,
            feedback_sessions_if_point400_and800_sharing_verified=12600,
            dev_sessions=14128,
            mechanism_sessions=5400,
            all_local_sessions_conservative=36328,
            all_local_sessions_if_sharing_verified=32128,
            max_generate_calls_conservative=1162496,
            max_generate_calls_if_sharing_verified=1028096,
            actual_material_tokens=None,
            actual_peak_GPU_memory=None,
            GPU_hours=None,
            Probe_API_and_semantic_review_budget="separate original bounded ledger, not reset here",
        ),
        later_independent=dict(
            Experiment5=["Full", "Hierarchical 0.3/0.5/0.2", "Tool-only", "Final-only"],
            frozen_pi="r",
            separate_registration=True,
            automatically_launched=False,
            core_ablations="separate protocols; no full-factorial expansion",
        ),
        material_readiness=assess_material_admission(
            tasks, material_claim, source_binding=source_binding
        ),
        api_model_if_any_future_API="deepseek-flash",
        model_fallback=False,
        execution_admitted=False,
        training_started=False,
        real_experiment123_results=False,
    )
    return {**body, "plan_id": "v6_experiment123_design:" + digest(body)}
