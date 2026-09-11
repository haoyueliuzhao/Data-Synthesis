"""Prospective synthesis conditions, actual-method strata and a bounded support gate."""

import random

from trusted_synthesis.experiments.finance_qa_vnext_soft_detail_exploration.plan import (
    SYSTEMS_NEW,
)
from trusted_synthesis.experiments.finance_qa_vnext_target_binding.core import encode as encode
from trusted_synthesis.experiments.finance_qa_vnext_target_binding.core import (
    read_json as read_json,
)
from trusted_synthesis.experiments.finance_qa_vnext_target_binding.core import (
    reference as reference,
)
from trusted_synthesis.experiments.finance_qa_vnext_target_binding.core import require as require
from trusted_synthesis.experiments.finance_qa_vnext_target_binding.core import sha as sha
from trusted_synthesis.experiments.finance_qa_vnext_thinking_comparison.online.common import LIMITS

BASELINE = "9743e7e057ff484249713276c7848e6fc744e645"
PACKAGE = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "finance_qa_vnext_basis_conditioned_support"
)
OUTPUT = (
    "trusted_data_synthesis/artifacts/qa_vnext_basis_conditioned_support/X1_X2_basis_8rep_20260911"
)
DOCUMENT = "trusted_data_synthesis/docs/finance_qa_vnext_basis_conditioned_support.md"
TESTS = (
    "trusted_data_synthesis/tests/test_qa_vnext_basis_conditioned_support.py",
    "trusted_data_synthesis/tests/test_qa_vnext_basis_conditioned_projection.py",
    "trusted_data_synthesis/tests/test_qa_vnext_basis_conditioned_tokens.py",
    "trusted_data_synthesis/tests/test_qa_vnext_basis_conditioned_collection.py",
    "trusted_data_synthesis/tests/test_qa_vnext_basis_conditioned_methods.py",
    "trusted_data_synthesis/tests/test_qa_vnext_basis_conditioned_consumption.py",
    "trusted_data_synthesis/tests/test_qa_vnext_basis_conditioned_costs.py",
)
SOURCE = (
    "trusted_data_synthesis/artifacts/qa_vnext_soft_detail_exploration/three_tasks_NE_8rep_20260910"
)
PREVIOUS = "trusted_data_synthesis/artifacts/qa_vnext_dr_support/E_X2_32rep_20260911"
AUDIT = "/home/zhuxinrui/.codex/attachments/878c2e85-e7a5-4768-b716-f48cc9436635/pasted-text.txt"
AUDIT_SHA = "021f8d41be81af33bd2c0b9f398bb480c5d78761d30b09f5323458791f7ec25b"
MODEL = "deepseek-flash"
TASKS = ("X1", "X2")
GENERATION_CONDITIONS = ("endpoint", "movement")
METHODS = ("endpoint", "movement")
WORKERS = 24
WORKER_PYTHON = "/usr/bin/python3"
COMMON_SYSTEM = SYSTEMS_NEW["N"]
BASIS_INSTRUCTIONS = {
    "endpoint": (
        "Use the two comparison endpoints disclosed directly in the source as the main "
        "basis of your published answer. Identify the financial object, comparison periods, "
        "sources and expression yourself from the complete document, and actually execute "
        "the calculation supporting the requested change or difference. If you cannot "
        "establish a sufficient valid basis of this kind, say so honestly and finish "
        "without inventing one."
    ),
    "movement": (
        "Use the components or changes explaining the comparison as the main basis of "
        "your published answer, rather than directly subtracting the two disclosed "
        "comparison endpoints as the main answer calculation. Identify the items, signs, "
        "sources and expression yourself from the complete document, and actually execute "
        "the requested net change or difference calculation. If you cannot establish a "
        "sufficient valid basis of this kind, say so honestly and finish without inventing one."
    ),
}
SYSTEMS = {g: COMMON_SYSTEM + "\n\n" + BASIS_INSTRUCTIONS[g] for g in GENERATION_CONDITIONS}
LABELS = tuple(
    f"{g}_{task}_{rep:02d}" for rep in range(1, 9) for task in TASKS for g in GENERATION_CONDITIONS
)


def record(kind, **fields):
    body = {"schema_version": "basis_conditioned_support.v1." + kind, **fields}
    return {**body, "id": kind + ":" + sha(encode(body))}


def condition(g):
    require(g in GENERATION_CONDITIONS, "condition.registered_guidance")
    return record(
        "basis_synthesis_condition",
        requested_basis=g,
        system=SYSTEMS[g],
        system_sha256=sha(SYSTEMS[g].encode()),
        common_system_sha256=sha(COMMON_SYSTEM.encode()),
        guidance=BASIS_INSTRUCTIONS[g],
        model=MODEL,
        thinking="enabled",
        reasoning_effort="high",
        temperature_top_p="omitted",
        limits=LIMITS,
        tasks=list(TASKS),
        replicates_per_task=8,
        explicit_basis_conditioning_not_old_E_natural_sampling=True,
        requested_g_is_not_assigned_actual_method_m=True,
        new_condition_identity_not_old_N_or_E=True,
        no_task_formula_values_source_ID_or_answer_hint=True,
        no_endpoint_hiding_no_extra_check_required=True,
    )


def registrations(public):
    shuffled = list(LABELS)
    random.Random(57641).shuffle(shuffled)
    ids = {label: f"basis_review_{i:03d}" for i, label in enumerate(shuffled, 1)}
    rows = []
    for ordinal, label in enumerate(LABELS, 1):
        g, task, replicate = label.split("_")
        rows.append(
            record(
                "basis_registration",
                label=label,
                ordinal=ordinal,
                replicate=int(replicate),
                wave=1 if ordinal <= 24 else 2,
                arm=g,
                requested_basis=g,
                task_key=task,
                task_id=public[task]["task_id"],
                public_document_id=public[task]["id"],
                condition_id=condition(g)["id"],
                system_sha256=sha(SYSTEMS[g].encode()),
                review_id=ids[label],
                requested_model=MODEL,
                response_budget=32,
                tool_budget=32,
                new_independent_empty_history=True,
            )
        )
    return rows


def policy():
    return record(
        "basis_support_policy",
        accepted_by_current_user_continue_request=True,
        previous_batch_closed_terminal="INPUT_INADEQUATE",
        old_sampling_or_scores_reopened=False,
        tasks=list(TASKS),
        requested_conditions=list(GENERATION_CONDITIONS),
        actual_method_strata=list(METHODS),
        new_Teacher_sessions=32,
        per_task_per_requested_condition=8,
        maximum_generation_requests=1024,
        response_tool_caps=[32, 32],
        workers=WORKERS,
        waves=[24, 8],
        dispatch="replicate ascending, then X1/X2, then endpoint/movement request",
        no_assessment_or_adaptation_between_waves=True,
        same_complete_sources_tools_and_first_Final_stop=True,
        exactly_one_fixed_guidance_text_per_condition=True,
        no_task_specific_formula_amount_source_ID_or_target_answer=True,
        no_endpoint_hiding_retry_fallback_reprompt_replacement_or_topup=True,
        model_catalog_or_calibration_requests=0,
        requested_labels_never_used_as_actual_method=True,
        method_definition=(
            "Actual Final main support: disclosed comparison endpoints versus "
            "components explaining the requested change/difference. An extra "
            "endpoint-reconstruction check is not a movement main answer."
        ),
        multiple_or_ambiguous_main_bases="retain MIXED/UNDETERMINED; do not force a quota",
        method_is_not_a_new_equivalence_relation=True,
        complete_class_keeps_condition_task_sources_revisions_and_checks=True,
        numeric_equal_values_do_not_choose_sources_or_methods=True,
        finite_cross_quantity_extension=(
            "X2 disclosed/rebuilt ending warranty reserve linked to net change"
        ),
        cross_quantity_identity_is_offline_not_extra_model_execution=True,
        shared_sources_not_statistically_independent=True,
        known_B2_07_only_used_for_new_projection_preparation_not_new_target_material=True,
        no_rejudgment_of_old_40_or_36_18_252=True,
        quantity_policy="public_quantity_interpretation.v1.1",
        Final_multi_amount_extraction_not_extended=True,
        target_source_claim_policy="public_task_target_binding.v2",
        raw_eligibility="complete financial/delivery validity AND full mapping AND unique actual m",
        raw_support_gate=(
            "at least four NEW original packages in EACH of X1/X2 × actual endpoint/movement"
        ),
        within_method_requested_g_may_be_mixed_and_is_retained=True,
        selection_order="replicate ascending, ties requested endpoint before requested movement",
        selection_tie_break_is_new_preregistered_implementation_choice=True,
        first_three_future_train_fourth_heldout=True,
        if_any_raw_stratum_below_four="close with empty selection; no tokenizer or more sampling",
        token_check="only the fixed first four per actual task/method, 16 original packages once",
        token_check_includes_four_holdouts=True,
        no_replacement_after_selected_token_failure=True,
        no_cropping_rewriting_prefix_neutralization_or_target_repair=True,
        supervised_representation=(
            "exact original request.messages and original positive public responses"
        ),
        old_35D_1R_and_old_X1_examples_not_new_target_data=True,
        training_weights_or_27_package_training_population_instantiated=False,
        training_allowed_even_if_consumability_passes=False,
        Student_generations_training_B0_same_question_greedy_and_NLL=0,
        fixed_kernel_interpretation=(
            "K(g,tau|x,m) retains requested guidance, fine class composition and original "
            "text/representation. Later alpha moves method mass while q(g,z|x,m) and "
            "M(tau|x,g,z) stay fixed. Not a prompt-isolated abstract method effect."
        ),
        future_utility_proposal={
            "status": "NOT_AUTOMATICALLY_EXECUTED_BY_THIS_SUPPORT_STAGE",
            "training_packages": 27,
            "old_G1_G2_F1_controls": 9,
            "fixed_N_X3C_D_A": 6,
            "new_X1_endpoint_movement": 6,
            "new_X2_endpoint_movement": 6,
            "conditions": ["pi0", "X1_plus", "X1_minus", "X2_plus", "X2_minus"],
            "task_marginals": "1/6",
            "one_target_task_moves_per_candidate": True,
            "method_mass_baseline": ["1/2", "1/2"],
            "method_mass_plus": ["1/3", "2/3"],
            "method_mass_minus": ["2/3", "1/3"],
            "global_mass_move": "1/36",
            "same_checkpoint_LoRA_three_seeds_ten_passes": True,
            "maximum_training_runs": 15,
            "maximum_development_sessions": 180,
            "maximum_new_confirmation_sessions": 144,
            "actual_target_tokens_must_be_frozen_from_new_material": True,
            "known_development_D10_requires_clarified_new_version": True,
            "new_confirmation_must_not_reuse_old_24_questions_or_paraphrases": True,
            "eval_SYSTEM_has_no_basis_synthesis_instruction": True,
            "strict_positive_mean_paired_gain_and_prefrozen_tie_order": True,
            "no_runner_up_after_failed_confirmation": True,
        },
        reviewer=(
            "executing assistant team; packet metadata masked, not independent or guaranteed blind"
        ),
    )


def target_ledgers(public, private):
    anchors = {
        "X1": (
            "p0",
            "p3",
            "p4",
            "t0c1",
            "t1c0",
            "t1c1",
            "t2c0",
            "t2c1",
            "t3c0",
            "t3c1",
            "t4c0",
            "t4c1",
        ),
        "X2": ("q9", "q10", "q11", "q12", "q13", "q14"),
    }
    descriptions = {
        "X1": {
            "object": (
                "Entergy Mississippi company-defined net revenue (gross margin), "
                "not net income or a stock reserve"
            ),
            "comparison": "2003 annual net revenue minus 2002 annual net revenue",
            "explanation": (
                "Public p3/p4 explicitly define net revenue and the 2003-to-2002 comparison; "
                "the table supplies two annual comparison endpoints and the base-rate/other "
                "variance bridge. This is not a stock-reserve rollforward."
            ),
        },
        "X2": {
            "object": "PPG product-warranty reserve, not asset-retirement obligations or pensions",
            "comparison": "December 31, 2006 reserve minus December 31, 2005 reserve",
            "explanation": (
                "Public q11 explicitly ties reserve balances to the two year ends; q9 and "
                "q12-q14 describe 2006 charges, cash outlays and assumed warranty obligations."
            ),
        },
    }
    return {
        key: record(
            "basis_public_target_ledger",
            task_key=key,
            task_id=public[key]["task_id"],
            public_document_id=public[key]["id"],
            question=public[key]["question"],
            alignment="ALIGNED",
            **descriptions[key],
            sign="later minus earlier; an increase is positive",
            unit="USD_million under unchanged common public money contract",
            public_source_anchors={sid: public[key]["segments"][sid] for sid in anchors[key]},
            registered_goal_scope=private[key]["goal_scope"],
            unchanged_public_question_and_complete_source=True,
            prior_reference_exact_value=private[key]["reference_exact_value"],
            no_old_model_output_used_to_choose_target=True,
        )
        for key in TASKS
    }


def fixed_selection(rows):
    require(
        len(rows) == 32 and {r["label"] for r in rows} == set(LABELS), "selection.exact_new_batch"
    )
    for row in rows:
        require(
            row.get("arm") in GENERATION_CONDITIONS
            and row.get("task_key") in TASKS
            and type(row.get("replicate")) is int
            and 1 <= row["replicate"] <= 8
            and row["label"] == f"{row['arm']}_{row['task_key']}_{row['replicate']:02d}"
            and row.get("condition_id") == condition(row["arm"])["id"],
            "selection.registered_identity_not_review_sort_key",
        )
        require(
            type(row.get("formula_driven_trace_verified")) is bool, "selection.boolean_validity"
        )
        if row.get("full_mapping_status") == "MAPPED":
            require(
                row.get("class_id")
                and row.get("projection_id")
                and row.get("method_record_id")
                and row["formula_driven_trace_verified"],
                "selection.actual_full_projection_and_class_required",
            )
    eligible = {key: {method: [] for method in METHODS} for key in TASKS}
    for row in sorted(
        rows,
        key=lambda r: (
            r["replicate"],
            GENERATION_CONDITIONS.index(r["arm"]),
            TASKS.index(r["task_key"]),
        ),
    ):
        method = row.get("method_stratum")
        if (
            row["formula_driven_trace_verified"]
            and row["full_mapping_status"] == "MAPPED"
            and method in METHODS
        ):
            eligible[row["task_key"]][method].append(row["label"])
    ready = all(len(labels) >= 4 for groups in eligible.values() for labels in groups.values())
    chosen = (
        [
            {
                "task_key": key,
                "actual_method": method,
                "label": label,
                "position": i + 1,
                "role": "future_train" if i < 3 else "heldout",
            }
            for key in TASKS
            for method in METHODS
            for i, label in enumerate(eligible[key][method][:4])
        ]
        if ready
        else []
    )
    return record(
        "basis_fixed_support_selection",
        status="RAW_METHOD_SUPPORT_ESTABLISHED" if ready else "INPUT_INADEQUATE",
        eligible=eligible,
        selected=chosen,
        selection_order=(
            "replicate ascending; tie requested endpoint then movement; within actual task/method"
        ),
        includes_historical_target_packages=False,
        selected_token_consumability="NOT_MEASURED",
        replace_selected_package_after_token_failure=False,
        training_allowed=False,
        next_step="freeze_16_package_representation_check"
        if ready
        else "stop_no_topup_no_tokenizer_no_training",
    )
