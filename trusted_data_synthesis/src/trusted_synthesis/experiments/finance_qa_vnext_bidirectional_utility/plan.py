"""Pre-call commitments for one bounded, conditional utility experiment."""

import json
import subprocess
from pathlib import Path

from trusted_synthesis.experiments.finance_qa_vnext_open_support_exploration.plan import (
    policy as inherited_support_policy,
)
from trusted_synthesis.experiments.finance_qa_vnext_pq_student.plan import (
    evaluation_config as inherited_evaluation_config,
)
from trusted_synthesis.experiments.finance_qa_vnext_pq_student.plan import (
    training_config as inherited_training_config,
)
from trusted_synthesis.experiments.finance_qa_vnext_thinking_comparison.online.common import (
    LIMITS,
    encode,
    sha,
)
from trusted_synthesis.experiments.finance_qa_vnext_trace_delivery.instructions import SYSTEMS

from .model_contract import ACCEPTED_RESPONSE_MODELS, REQUESTED_MODEL

BASELINE = "5dde23c2a041a638060ee0af8dcaa3fa4f7330e5"
PACKAGE = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_bidirectional_ut"
    "ility"
)
OUTPUT = (
    "trusted_data_synthesis/artifacts/qa_vnext_bidirectional_utility/"
    "three_tasks_24rep_flash_rerun_20260910"
)
DOCUMENT = "trusted_data_synthesis/docs/finance_qa_vnext_bidirectional_utility_flash_rerun.md"
TESTS = (
    "trusted_data_synthesis/tests/test_qa_vnext_bidirectional_utility.py",
    "trusted_data_synthesis/tests/test_qa_vnext_bidirectional_flash_contract.py",
)
MODEL = REQUESTED_MODEL
MODEL_CATALOG_SHA256 = "a9c95c422d1a3d79b91240fbbf1a5f4b9ecaa29df5ced18b502360ea37b45c5b"
PRIOR_OUTPUT = (
    "trusted_data_synthesis/artifacts/qa_vnext_bidirectional_utility/three_tasks_24rep_20260910"
)
SYSTEM = SYSTEMS["T"]
TASKS = ("X1", "X2", "X3")
CONTROLS = ("G1", "G2", "F1")
TRAIN_TASKS = (*TASKS, *CONTROLS)
STRUCTURES = {
    "X1": "net_revenue_bridge_vertical_table",
    "X2": "product_warranty_reserve_prose_rollforward",
    "X3": "unrecognized_tax_benefits_multiyear_table",
}
REPLICATES = 24
LABELS = tuple(f"T_{task}_{rep:02d}" for rep in range(1, REPLICATES + 1) for task in TASKS)
SEEDS = (11, 29, 47)
CONDITIONS = ("P_new", "X1+", "X1-", "X2+", "X2-", "X3+", "X3-")
WORKER_PYTHON = "/usr/bin/python3"
AUDIT_PATH = (
    "/home/zhuxinrui/.codex/attachments/899f21c9-917c-4151-b259-a92f70f8deae/pasted-text.txt"
)
AUDIT_SHA256 = "3c5c9123ebab4378e6d8ea62dc96a698f80be8e2632afac3cda458d9f5bca61b"
PARENT = (
    "trusted_data_synthesis/artifacts/qa_vnext_open_support_exploration/three_structures_4rep_2"
    "0260909"
)
CONTROL_LABELS = (
    "T_G1_01",
    "T_G1_02",
    "T_G1_03",
    "T_G2_01",
    "T_G2_02",
    "T_G2_03",
    "T_F1_02",
    "T_F1_03",
    "T_F1_04",
)
CONTROL_INDEX_SHA256 = "7e8ccf83f765405c3b168de81fa125bf5c9c73660bac4f6fa5015e4620478f2d"


def record(kind, **fields):
    body = {"schema_version": "bidirectional_utility.flash_rerun.v1." + kind, **fields}
    return {**body, "id": kind + ":" + sha(encode(body))}


def require(value, code):
    if not value:
        raise ValueError(code)


def read_json(path):
    return json.loads(Path(path).read_bytes())


def history_guard(root):
    paths = [
        "trusted_data_synthesis",
        ":(exclude)" + PACKAGE,
        ":(exclude)" + OUTPUT,
        ":(exclude)" + DOCUMENT,
        *[":(exclude)" + p for p in TESTS],
    ]
    require(
        not subprocess.check_output(
            ["git", "diff", "--name-only", BASELINE, "--", *paths], cwd=root
        ),
        "history.changed",
    )
    require(
        not subprocess.check_output(["git", "status", "--porcelain", "--", *paths], cwd=root),
        "history.uncommitted",
    )
    return {
        "baseline": BASELINE,
        "all_files_outside_authorized_rerun_scope_unchanged": True,
        "prior_batch_artifacts_and_financial_scores_unchanged": True,
        "current_experiment_code_has_authorized_model_contract_revision": True,
    }


def condition():
    return record(
        "fixed_open_support_condition",
        model=MODEL,
        accepted_response_models=list(ACCEPTED_RESPONSE_MODELS),
        user_confirmed_current_Flash_and_authorized_new_batch=True,
        model_catalog_snapshot_path=PACKAGE + "/model_catalog_snapshot.json",
        model_catalog_snapshot_sha256=MODEL_CATALOG_SHA256,
        independent_rerun_of=PRIOR_OUTPUT,
        previous_72_sessions_not_resumed_regraded_or_pooled=True,
        system=SYSTEM,
        system_sha256=sha(SYSTEM.encode()),
        thinking="enabled",
        reasoning_effort="high",
        temperature_top_p="omitted; unchanged parent T condition",
        tasks=list(TASKS),
        structures=STRUCTURES,
        labels=list(LABELS),
        replicates_per_task=REPLICATES,
        independent_new_sessions=72,
        limits=LIMITS,
        maximum_model_requests=2304,
        maximum_reserved_token_allowance=2304 * 115712,
        concurrent_workers=24,
        collection_task_allocation={key: "1/3" for key in TASKS},
        eventual_training_task_marginal={key: "1/6" for key in TRAIN_TASKS},
        parent_T_instruction_unchanged=True,
        complete_original_question_and_source_visible=True,
        original_worker_calculator_projection_isolate_bytes=False,
        worker_changes="current Flash request/response identity contract only",
        original_calculator_feedback_stop_projection_isolate_and_T_semantics=True,
        private_route_options_never_in_model_input=True,
        fixed_allocation_no_adaptive_prompt_or_resampling=True,
        all_registrations_before_any_provider_call=True,
        no_retries_no_fallback_no_budget_increase=True,
        force_reconstruction=False,
        hide_disclosure=False,
        independent_empty_histories_no_shared_notes_or_answers=True,
        first_Final_terminal_even_if_incorrect_or_no_calculation=True,
        private_reasoning_storage=False,
        no_old_trajectories_in_new_denominator=True,
    )


def policy():
    inherited = {
        k: v for k, v in inherited_support_policy().items() if k not in {"id", "schema_version"}
    }
    inherited.update(
        empirical_quality=(
            "valid_count/24 for each newly sampled task; all registered expense retained"
        ),
        stopping=(
            "exactly 72 fixed sessions; any one of six specified full behavior classes has "
            "fewer than four valid consumable packages => INPUT_INADEQUATE and no Student "
            "stages; no top-up, replacement, rewriting or copying"
        ),
        target_classes=(
            "private pre-call source-symbolic D and R signatures with empty substantive "
            "revision and independent-cross-check lists; full signature equality, not "
            "last-formula bucketing"
        ),
        support_selection=(
            "each task/class: eligible sessions ordered by original numeric replicate; first "
            "three train, fourth same-task diagnostic; later eligible sessions retained but not "
            "selected"
        ),
        independent_generations_not_distinct_classes_or_distinct_texts=True,
        duplicate_target_texts_retained_and_disclosed=True,
        diagnostic_duplicate_text_not_unseen_text_generalization=True,
        training_weights=(
            "fixed mu=1/6, kappa=1/3; P_new D/R=2/3,1/3; one-task plus=1/2,1/2; minus=5/6,1/6; "
            "control packages=1/18"
        ),
        old_controls=(
            "nine previously accepted G1/G2/F1 packages, no new sampling, qualification, pair "
            "review or tokenization"
        ),
        review_author=(
            "executing assistant, exact public evidence reviewed offline; not an independent "
            "financial expert"
        ),
        class_probability_degrees_of_freedom=(
            "descriptive finite observed support only; selected 3:3 counts are not natural "
            "class probabilities"
        ),
        no_contribution_or_student_utility_inferred_from_NLL=True,
    )
    return record("finite_new_support_policy", **inherited)


def downstream_plan():
    training = {
        k: v for k, v in inherited_training_config().items() if k not in {"id", "schema_version"}
    }
    training.update(
        conditions=list(CONDITIONS),
        train_runs=21,
        packages_per_epoch=27,
        rows_per_epoch=None,
        supervised_tokens_per_epoch=None,
        sequence_tokens_per_epoch=None,
        supervised_tokens_per_run=None,
        sequence_tokens_per_run=None,
        accumulation=(
            "one full pass over all physical rows of the same 27 original packages before each "
            "update"
        ),
        row_order="same seed gives same permutation of all physical row IDs in every condition",
        actual_token_budget_frozen_only_after_materialization=True,
        no_retokenization_of_training_rows=True,
        no_teacher_sampling="training phase only; fixed 72 Teacher sessions precede the input gate",
        Q_is_hand_specified_diagnostic_not_optimized_contribution_or_novelty=False,
    )
    evaluation = {
        k: v for k, v in inherited_evaluation_config().items() if k not in {"id", "schema_version"}
    }
    for k in (
        "primary_transfer_tasks",
        "regression_tasks",
        "variants",
        "baseline_once_before_training",
        "same_panel_after_every_final_P_Q_checkpoint",
    ):
        evaluation.pop(k, None)
    evaluation.update(
        tasks=36,
        development_tasks=12,
        confirmation_tasks=24,
        source_isolation=(
            "company-disjoint training/development/confirmation; within-panel company/report "
            "dependence explicitly retained"
        ),
        total_sessions=396,
        development_sessions=252,
        maximum_confirmation_sessions=144,
        no_B0=True,
        decoder="unchanged parent greedy",
        numeric_policy=(
            "unchanged pq_student score_quantity/qualify rules and unit normalization; no new "
            "aliases or online source correction"
        ),
        panel_groups=["dual_sufficient", "detail_related", "other_finance"],
        development_group_sizes=[4, 4, 4],
        confirmation_group_sizes=[8, 8, 8],
        main_utility=(
            "one third of each group mean indicator of complete trace PASS; unknowns retained "
            "in denominator"
        ),
        semantic_review=(
            "condition/seed/NLL/model identifiers withheld and sessions mixed where feasible; "
            "same author, not independent expert certification"
        ),
        selector=(
            "maximum paired-seed mean dev utility gain over P_new; move only if strictly "
            "positive; baseline wins zero tie; remaining tie order X1+, X1-, X2+, X2-, X3+, X3-"
        ),
        finite_direction=(
            "mean_s[J_dev(x+,s)-J_dev(x-,s)]/(2*(1/6)); finite delta, not theoretical Contribution"
        ),
        confirmation=(
            "seal selected distribution and checkpoint identities before confirmation; only "
            "selected and P_new, 3 seeds each; no runner-up replacement"
        ),
        no_move_action="finish after development; no duplicate baseline confirmation sessions",
        same_task_diagnostic=(
            "six reserved fourth packages; optional text-fit measurement is not main utility; "
            "no original L1 greedy rerun"
        ),
        stop_on_training_implementation_failure_without_hidden_rerun=True,
        no_confirm_result_driven_policy_panel_or_step_change=True,
    )
    return record(
        "conditional_downstream_plan",
        input_gate_required=True,
        training=training,
        evaluation=evaluation,
    )


def registrations(public):
    return [
        record(
            "new_support_registration",
            label=label,
            ordinal=i,
            arm="T",
            task_key=key,
            structure=STRUCTURES[key],
            replicate=int(rep),
            requested_model=MODEL,
            system_sha256=sha(SYSTEM.encode()),
            task_id=public[key]["task_id"],
            public_document_id=public[key]["id"],
            condition_id=condition()["id"],
            response_budget=32,
            tool_budget=32,
            fresh_independent_session=True,
        )
        for i, label in enumerate(LABELS, 1)
        for _, key, rep in [label.split("_")]
    ]
