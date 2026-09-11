"""Accepted new batch: fixed sampling, eligibility and conditional utility boundary."""

import random
from fractions import Fraction

from trusted_synthesis.experiments.finance_qa_vnext_soft_detail_exploration.plan import (
    SYSTEMS_NEW,
    condition,
)
from trusted_synthesis.experiments.finance_qa_vnext_target_binding.core import encode as encode
from trusted_synthesis.experiments.finance_qa_vnext_target_binding.core import (
    read_json as read_json,
)
from trusted_synthesis.experiments.finance_qa_vnext_target_binding.core import (
    reference as reference,
)
from trusted_synthesis.experiments.finance_qa_vnext_target_binding.core import (
    require,
    sha,
)
from trusted_synthesis.experiments.finance_qa_vnext_thinking_comparison.online.common import LIMITS

BASELINE = "5d81205b138a9842bbea8df8161edc0a0692c130"
PACKAGE = "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_dr_support"
OUTPUT = "trusted_data_synthesis/artifacts/qa_vnext_dr_support/E_X2_32rep_20260911"
DOCUMENT = "trusted_data_synthesis/docs/finance_qa_vnext_dr_support.md"
TEST = "trusted_data_synthesis/tests/test_qa_vnext_dr_support.py"
OLD = (
    "trusted_data_synthesis/artifacts/qa_vnext_soft_detail_exploration/three_tasks_NE_8rep_20260910"
)
OLD_UTILITY = (
    "trusted_data_synthesis/artifacts/qa_vnext_source_class_utility/N_X3C_3arm3seed_20260911"
)
BINDING = (
    "trusted_data_synthesis/artifacts/qa_vnext_target_binding/fixed_36targets_18cases_20260911"
)
AUDIT = "/home/zhuxinrui/.codex/attachments/a6ba7d9b-d425-45d1-88c6-848c1832c437/pasted-text.txt"
AUDIT_SHA = "f94b8e10ee9e16108a3ec91d4f0ed1086cf429f907d9dbc5e7f473ef215e61e4"
MODEL = "deepseek-flash"
SYSTEM = SYSTEMS_NEW["E"]
LABELS = tuple(f"E_X2_B2_{i:02d}" for i in range(1, 33))
OLD_LABELS = tuple(f"E_X2_{i:02d}" for i in range(1, 9))
WORKERS = 24
WORKER_PYTHON = "/usr/bin/python3"
CONDITIONS = ("pi0", "plus_R", "minus_R")
SEEDS = (11, 29, 47)
GROUPS = ("dual_sufficient", "detail_related", "other_finance")


def record(kind, **fields):
    body = {"schema_version": "bounded_E_X2_DR_support.v1." + kind, **fields}
    return {**body, "id": kind + ":" + sha(encode(body))}


def registrations(public):
    mixed = list(LABELS)
    random.Random(41387).shuffle(mixed)
    review_ids = {label: f"dr_review_{i:03d}" for i, label in enumerate(mixed, 1)}
    return [
        record(
            "DR_support_registration",
            label=label,
            ordinal=i,
            replicate=i,
            batch="new_32",
            wave=1 if i <= 24 else 2,
            arm="E",
            task_key="X2",
            task_id=public["task_id"],
            public_document_id=public["id"],
            requested_model=MODEL,
            generative_condition_id=condition("E")["id"],
            system_sha256=sha(SYSTEM.encode()),
            review_id=review_ids[label],
            response_budget=32,
            tool_budget=32,
            independent_empty_history=True,
        )
        for i, label in enumerate(LABELS, 1)
    ]


def sampling_policy():
    return record(
        "accepted_DR_support_policy",
        accepted_by_new_continue_request_after_completed_zero_model_workflow=True,
        old_workflow_commit=BASELINE,
        new_sessions=32,
        maximum_generation_requests=1024,
        maximum_requests_per_session=32,
        maximum_tools_per_session=32,
        limits=LIMITS,
        workers=WORKERS,
        wave_sizes=[24, 8],
        dispatch="replicate ascending; finish first 24 before last 8; no review between waves",
        all_32_terminal_before_semantic_review=True,
        fixed_old_E_condition_reference=condition("E")["id"],
        old_condition_replicate_count_is_historical_metadata_not_new_budget=True,
        preserve_public_system_source_tools_and_first_Final_stop=True,
        preserve_requested_model_thinking_high_and_omitted_temperature_top_p=True,
        exact_public_source_task="PPG/2006/page_42.pdf-4",
        model_catalog_or_calibration_requests=0,
        network_retries_fallbacks_replacement_sessions_or_topups=0,
        no_adaptation_after_D_or_between_waves=True,
        no_evaluator_feedback_formula_source_ID_hint_or_hidden_endpoints=True,
        stop_regardless_of_support_count=True,
        historical_8_and_new_32_denominators_separate=True,
        same_provider_weights_dates_or_natural_sampling_law_claimed=False,
        same_condition_class_identity_is_a_defined_finite_quotient_not_a_distribution_claim=True,
        quantity_rule="public_quantity_interpretation.v1.1",
        public_target_rule="public_task_target_binding.v2",
        complete_validity=(
            "actual first Final; interpreted requested quantity; selected successful calculation; "
            "pre/same-call relationship, input and unit evidence; execution/publication and "
            "explicit Final result linkage; five public semantic fields; public target completion "
            "and current source-claim certification. Unknown is not PASS."
        ),
        formula_local_relation_and_public_task_completion_separate=True,
        source_roles=[
            "DIRECT_SOURCE_VALUE",
            "DERIVED_FROM_SOURCES",
            "GENERAL_REFERENCE",
            "UNRESOLVED",
        ],
        current_unconsumed_claims_not_erased_and_flat_adjacency_not_an_assertion=True,
        withdrawn_claim_requires_actual_correction_or_unambiguous_replacement=True,
        numeric_ID_only_gate=False,
        full_pure_D_R_class=(
            "reuse exact E/X2 source-symbolic full signatures: task, public document, goal, "
            "active sources, actual Final support, substantive revision path and independent "
            "checks; no relabeling other valid classes as pure R; no equal-value source search"
        ),
        raw_eligibility_review_population="only historical E/X2 eight and new E/X2 thirty-two",
        historical_scores_and_class_records_unchanged=True,
        selection_order="old batch first then new batch; original replicate ascending",
        minimum_per_class=4,
        first_three_per_class_train_fourth_heldout=True,
        token_check_only_if_both_raw_counts_at_least_four=True,
        token_check_first_four_each_once_including_heldout=True,
        no_replacement_after_selected_token_failure=True,
        heldout_training_greedy_and_NLL=0,
        repeat_text_is_not_an_additional_quotient_class=True,
        this_stage_Student_training_or_evaluation=0,
        tokenizer_in_this_collection_and_semantic_closeout=0,
        later_materialization_and_training_require_separate_frozen_artifacts=True,
        conditional_limits={
            "training_runs": 9,
            "development_sessions": 108,
            "confirmation_sessions": 144,
        },
        conditional_training={
            "packages": 24,
            "old_G1_G2_F1": 9,
            "old_N_X1": 3,
            "fixed_old_N_X3C_D_A": 6,
            "new_E_X2_D_R": 6,
            "task_marginals": "1/6",
            "conditions": list(CONDITIONS),
            "seeds": list(SEEDS),
            "full_passes": 10,
            "same_checkpoint_LoRA_optimizer_and_paired_training_order": True,
            "supervised_tokens_per_run": "10 * sum(actual selected target token lengths)",
            "old_fixed_arrays_reused_without_retokenization": True,
            "old_pi0_not_a_causal_comparator": True,
        },
        conditional_evaluation={
            "known_development": "old 12; D10 must be an explicitly clarified new task version",
            "new_confirmation": (
                "24 genuinely new tasks, three groups of eight, not old-question paraphrases"
            ),
            "freeze_source_selection_rule_before_candidate_outputs": True,
            "exclude_old_train_dev_confirmation_source_companies_from_new_confirmation": True,
            "freeze_resolved_public_target_ledger_before_any_Student_generation": True,
            "selection": "strictly positive mean paired gain; ties pi0, plus_R, minus_R",
            "confirm_only_selected_candidate_and_baseline": True,
            "stop_if_no_development_move_or_failed_confirmation": True,
            "no_runner_up_or_new_seed_after_confirm": True,
            "B0_same_question_greedy_auxiliary_NLL": 0,
        },
        reviewer="executing assistant; shuffled packet IDs, not independent or guaranteed blind",
    )


def target_ledger(public, private):
    require(public["task_id"] == "PPG/2006/page_42.pdf-4", "target.exact_X2")
    require(
        public["question"]
        == (
            "what was the change in millions in the reserve for product warranties "
            "from 2005 to 2006?"
        ),
        "target.unchanged_public_question",
    )
    anchors = {key: public["segments"][key] for key in ("q9", "q10", "q11", "q12", "q13", "q14")}
    require("31 , 2006 and 2005" in anchors["q11"]["text"], "target.explicit_year_ends")
    return record(
        "DR_public_target_ledger",
        task_id=public["task_id"],
        public_document_id=public["id"],
        public_question=public["question"],
        alignment="ALIGNED",
        object=(
            "PPG reserve for product warranties, not asset-retirement obligations "
            "or pension balances"
        ),
        interval="December 31, 2006 minus December 31, 2005",
        quantity="net change in the reserve balance",
        sign="later minus earlier; increase is positive",
        unit="millions of U.S. dollars under unchanged public E currency contract",
        source_anchors=anchors,
        registered_goal_scope=private["goal_scope"],
        source_bindings=private["source_bindings"],
        prior_reference_exact_value=private["reference_exact_value"],
        reference_arithmetic_or_other_tasks_recomputed=False,
        reason=(
            "q11 explicitly ties the reserve balances to the two named year ends; q9 and "
            "q12-q14 identify 2006 warranty charges, cash outlays and assumed obligations. "
            "Both sufficient relations concern this balance change. The model must actually "
            "complete this original public target, not merely another local relation."
        ),
        frozen_before_any_new_batch_response=True,
    )


def select_support(rows):
    require(len({r["label"] for r in rows}) == len(rows), "selection.unique_labels")
    eligible = {"D": [], "R": []}
    order = {label: (0, i) for i, label in enumerate(OLD_LABELS, 1)}
    order.update({label: (1, i) for i, label in enumerate(LABELS, 1)})
    require(set(r["label"] for r in rows) <= set(order), "selection.only_registered_candidates")
    for row in sorted(rows, key=lambda r: order[r["label"]]):
        if row["formula_driven_trace_verified"] and row.get("behavior") in {"PURE_D", "PURE_R"}:
            eligible[row["behavior"][-1]].append(row["label"])
    ready = all(len(labels) >= 4 for labels in eligible.values())
    return record(
        "DR_fixed_support_selection",
        status="RAW_SUPPORT_ESTABLISHED" if ready else "INPUT_INADEQUATE",
        eligible=eligible,
        train={r: labels[:3] for r, labels in eligible.items()} if ready else {},
        heldout={r: labels[3] for r, labels in eligible.items()} if ready else {},
        token_check={r: labels[:4] for r, labels in eligible.items()} if ready else {},
        consumability="NOT_MEASURED",
        training_allowed=False,
        next_step="freeze_and_validate_eight_selected_token_packages"
        if ready
        else "stop_no_topup_no_tokenizer_no_training",
    )


def package_mass(arm, task, route):
    require(arm in CONDITIONS, "mass.registered_arm")
    require(task in {"G1", "G2", "F1", "X1", "X2", "X3C"}, "mass.registered_task")
    if task == "X2":
        require(route in {"D", "R"}, "mass.pure_D_R_only")
        r = {"pi0": Fraction(1, 2), "plus_R": Fraction(2, 3), "minus_R": Fraction(1, 3)}[arm]
        return (r if route == "R" else 1 - r) / 18
    if task == "X3C":
        require(route in {"D", "A"}, "mass.fixed_D_A_control")
        return Fraction(1, 36)
    return Fraction(1, 18)
