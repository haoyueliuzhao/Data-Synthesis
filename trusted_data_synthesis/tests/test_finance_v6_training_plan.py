"""CPU design/claim controls, never training or synthetic training outcomes."""

import copy
from collections import Counter

import pytest

from trusted_synthesis.finance_research.contracts import digest
from trusted_synthesis.finance_research.v6_training_plan import (
    assess_400_800_sharing,
    assess_material_admission,
    build_execution_plan,
    build_task_schedule,
)


def roster():
    return [f"synthetic-task-{index}" for index in range(1000)]


def test_exact_five_arm_schedule_and_dose_not_a_result():
    plan = build_execution_plan(roster(), source_binding={"original_source": "synthetic control"})
    assert len(plan["arms"]) == 15 and plan["seeds"] == [11, 29, 47]
    assert plan["arm_names"] == ["Static", "Manual+", "Manual-", "C-only", "Full"]
    for seed in plan["seeds"]:
        rows = [row for row in plan["arms"] if row["seed"] == seed]
        assert len({row["schedule_sha256"] for row in rows}) == 1
        assert all(row["shared_prefix"]["end"] == 400 and row["final_step"] == 2000 for row in rows)
        assert all(
            row["outer_steps"] == [400, 800, 1200, 1600]
            for row in rows
            if row["arm"] in {"C-only", "Full"}
        )
        assert all(
            row["outer_steps"] == []
            for row in rows
            if row["arm"].startswith("Manual") or row["arm"] == "Static"
        )
    assert plan["training"]["effective_model_history_steps"] == 30000
    assert plan["budgets"]["core_physical_SFT_steps_conservative"] == 25200
    assert plan["budgets"]["core_physical_SFT_steps_if_identity_verified"] == 24000
    assert len(plan["feedback"]["logical_batches"]) * 700 == 16800
    assert plan["budgets"]["feedback_sessions_if_point400_and800_sharing_verified"] == 12600
    assert sum(row["tasks"] for row in plan["evaluation"]["dev_coordinates"]) == 883 * 16 == 14128
    assert plan["mechanism"]["C_direction"]["sessions"] == 120 * 3 * 3 * 3 == 3240
    assert plan["mechanism"]["C_direction"]["total_extra_training_steps"] == 600
    assert plan["mechanism"]["N_same_point"]["sessions"] == 120 * 2 * 3 * 3 == 2160
    assert plan["budgets"]["all_local_sessions_conservative"] == 36328
    assert plan["budgets"]["max_generate_calls_conservative"] == 36328 * 32
    assert not plan["interventions"]["manual_is_reverse_direction_control"]
    assert plan["mechanism"]["C_direction"]["reverse_is_not_Manual_minus"]
    assert not plan["training_started"] and not plan["real_experiment123_results"]
    assert (
        not plan["execution_admitted"]
        and not plan["material_readiness"]["claims_structurally_admitted"]
    )
    assert plan["later_independent"]["separate_registration"]


def test_schedule_has_exact_1000_coverage_each_epoch_and_deterministic_hash():
    tasks = roster()
    a = build_task_schedule(tasks, 11)
    assert a == build_task_schedule(tasks, 11)
    assert a["schedule_sha256"] != build_task_schedule(tasks, 29)["schedule_sha256"]
    assert [row["step"] for row in a["batches"]] == list(range(1, 2001))
    assert all(len(row["task_ids"]) == len(set(row["task_ids"])) == 5 for row in a["batches"])
    for epoch in range(1, 11):
        assert Counter(
            t for row in a["batches"] if row["epoch"] == epoch for t in row["task_ids"]
        ) == dict.fromkeys(tasks, 1)
    assert a["batches"][399]["epoch"] == 2 and a["batches"][400]["epoch"] == 3
    with pytest.raises(ValueError):
        build_task_schedule(tasks[:165], 11)


def material_claim(*, new=False):
    """Existing record shapes; fictional data is explicitly only a claim-validator fixture."""
    tasks, resolutions, encodings, summary = roster(), {}, {}, []
    for task in tasks:
        sid = task + "/0"
        manifest = dict(episode_sha256=digest(sid), mask_agreement=True, not_a_TokenReceipt=True)
        slots = {
            task + f"/{index}": dict(q_native=False, v_trace="invalid", mapper="not_applicable")
            for index in range(8)
        }
        slots[sid] = dict(
            q_native=True,
            v_trace="valid",
            mapper="mapped",
            state_id="z0",
            chi=0,
            mask_status="agreed",
            encoding_manifest=manifest,
        )
        resolution = dict(
            schema="v7_decomposed_pair_resolution.v1"
            if new
            else "v6_decomposed_pair_resolution.v3",
            task_id=task,
            slots=slots,
            task_mapping="complete",
            valid_slots_retained=[sid],
            all_eight_candidates_retained=True,
            no_dropping_hard_to_map_valid_packages=True,
        )
        resolutions[task] = dict(record=resolution, file_sha256=digest(resolution))
        encoding = dict(
            schema="v7_student_encoding.v1" if new else "v6_student_encoding.v1",
            task_id=task,
            episode_sha256=digest(sid),
            resolved_mask_sha256=digest(manifest),
            encoding_admitted=True,
            context_limit=24576,
            context_truncated=False,
            api_original_sampling_tokens_claimed=False,
            not_a_TokenReceipt=True,
            L_P=8,
            total_supervised_tokens=8,
            max_sequence_tokens=100,
            tokenizer_digest="1" * 64,
            chat_template_digest="2" * 64,
        )
        encodings[sid] = dict(record=encoding, file_sha256=digest(encoding))
        summary.append(
            dict(
                task_id=task,
                joint_valid=1,
                n_x=1,
                states={"z0": 1},
                mapping_complete=True,
                masks_complete=True,
            )
        )
    inventory = dict(
        protocol_id="synthetic-inventory",
        original_tasks=1000,
        original_slots=8000,
        slot_review_denominator=16000,
        alignment_denominator=2000,
        completed_calls=18000,
        tasks=summary,
        counts={"joint_valid": 1000},
        all_originals_retained=True,
        material_admission_only=True,
        Student_encoding_complete=False,
    )
    return dict(
        inventory_producer="v6_decomposed_review.inventory",
        inventory=dict(record=inventory, file_sha256=digest(inventory)),
        resolutions=resolutions,
        encodings=encodings,
    )


@pytest.mark.parametrize("new", [False, True])
def test_actual_old_and_new_record_shapes_are_claims_only_never_real_launch_admission(new):
    claim = material_claim(new=new)
    ready = assess_material_admission(roster(), claim)
    assert ready["claims_structurally_admitted"] and ready["claim_validation_only"]
    assert ready["original_slot_count"] == 8000 and ready["joint_valid_packages_retained"] == 1000
    assert ready["mu"] == "1/1000" and all(
        r == {"z0": "1"} for r in ready["empirical_prior"].values()
    )
    assert ready["actual_launch_requires_artifactverification"]
    assert not ready["referenced_file_bytes_read_or_verified"] and not ready["execution_admitted"]
    # The immutable inventory precedes encoding. Do not demand editing its false
    # flag once separate actual encoding artifacts have subsequently been made.
    assert claim["inventory"]["record"]["Student_encoding_complete"] is False


@pytest.mark.parametrize(
    "bad",
    [
        "165scope",
        "missing_originals",
        "missing_slot",
        "unknown_inventory",
        "unknown_resolution",
        "unknown_encoding",
        "missing_encoding",
        "missing_hash",
        "partial_reviews",
        "unknown_mask",
        "mask_hash",
        "truncated",
        "missing_task_support",
    ],
)
def test_readiness_blocks_absent_changed_filtered_or_unbound_material(bad):
    claim, tasks = material_claim(), roster()
    task, sid = tasks[0], tasks[0] + "/0"
    if bad == "165scope":
        tasks = tasks[:165]
    elif bad == "missing_originals":
        claim["inventory"]["record"]["all_originals_retained"] = False
    elif bad == "missing_slot":
        claim["resolutions"][task]["record"]["slots"].pop(task + "/7")
    elif bad == "unknown_inventory":
        claim["inventory"]["record"]["schema"] = "unknown_future_inventory"
    elif bad == "unknown_resolution":
        claim["resolutions"][task]["record"]["schema"] = "unknown_future_resolution"
    elif bad == "unknown_encoding":
        claim["encodings"][sid]["record"]["schema"] = "unknown_future_encoding"
    elif bad == "missing_encoding":
        claim["encodings"].pop(sid)
    elif bad == "missing_hash":
        claim["encodings"][sid]["file_sha256"] = None
    elif bad == "partial_reviews":
        claim["inventory"]["record"]["completed_calls"] = 12
    elif bad == "unknown_mask":
        claim["resolutions"][task]["record"]["slots"][sid]["mask_status"] = "unknown"
    elif bad == "mask_hash":
        claim["encodings"][sid]["record"]["resolved_mask_sha256"] = "f" * 64
    elif bad == "truncated":
        claim["encodings"][sid]["record"]["context_truncated"] = True
    else:
        claim["resolutions"][task]["record"]["slots"][sid]["q_native"] = False
    result = assess_material_admission(tasks, claim)
    assert not result["claims_structurally_admitted"] and result["failures"]
    assert result["execution_admitted"] is False


def test_extra_joint_valid_package_cannot_be_filtered_even_when_every_task_has_support():
    claim, task = material_claim(), roster()[0]
    resolution = claim["resolutions"][task]["record"]
    resolution["slots"][task + "/1"] = copy.deepcopy(resolution["slots"][task + "/0"])
    result = assess_material_admission(roster(), claim)
    assert not result["claims_structurally_admitted"]
    assert any(
        row["reason"] == "joint_valid_original_package_was_omitted" for row in result["failures"]
    )


def test_conditional_sharing_needs_full_state_evidence_not_matching_reward_counts():
    common = dict(
        seed=11,
        step=400,
        schedule_cursor=400,
        feedback_sessions=700,
        feedback_sealed_before_scoring=True,
        reward_count=100,
    )
    left, right = {**common, "arm": "C-only"}, {**common, "arm": "Full"}
    required = assess_400_800_sharing(left, right)["missing_hashes"]
    assert required
    for key in required:
        left[key] = right[key] = digest(key)
    result = assess_400_800_sharing(left, right)
    assert result["claims_compatible_for_sharing"]
    assert not result["budget_saving_applied"] and not result["execution_admitted"]
    right["rng_state_sha256"] = "f" * 64
    assert not assess_400_800_sharing(left, right)["claims_compatible_for_sharing"]
