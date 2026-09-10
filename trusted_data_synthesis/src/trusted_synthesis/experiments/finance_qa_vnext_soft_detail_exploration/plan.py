"""Frozen design for exactly 48 new conditional Teacher sessions."""

import json
import random
import subprocess
from pathlib import Path

from trusted_synthesis.experiments.finance_qa_vnext_thinking_comparison.online.common import (
    LIMITS,
    encode,
    sha,
)
from trusted_synthesis.experiments.finance_qa_vnext_trace_delivery.instructions import SYSTEMS

from .model_contract import ACCEPTED_RESPONSE_MODELS, REQUESTED_MODEL

BASELINE = "ed1826624585c0a4872b3c82a06706c282321ad9"
PACKAGE = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_so"
    "ft_detail_exploration"
)
OUTPUT = (
    "trusted_data_synthesis/artifacts/qa_vnext_soft_detail_exploration/three_tasks_NE_8rep_20260910"
)
DOCUMENT = "trusted_data_synthesis/docs/finance_qa_vnext_soft_detail_exploration.md"
TESTS = (
    "trusted_data_synthesis/tests/test_qa_vnext_soft_detail_quantity.py",
    "trusted_data_synthesis/tests/test_qa_vnext_soft_detail_exploration.py",
)
PARENT = (
    "trusted_data_synthesis/artifacts/qa_vnext_bidirectional_utility/three_tasks_"
    "24rep_flash_rerun_20260910"
)
PARENT_PACKAGE = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_bi"
    "directional_utility"
)
AUDIT_PATH = (
    "/home/zhuxinrui/.codex/attachments/e09ddc97-d2b3-42ec-88dc-663c7b1d38a9/pasted-text.txt"
)
AUDIT_SHA256 = "f64dad6eb01263178fb6fb9fa3e78d409f3a7293c4e280deca2d42a47f5d3e1a"
MODEL = REQUESTED_MODEL
TASKS = ("X1", "X2", "X3C")
ARMS = ("N", "E")
REPLICATES = 8
WORKERS = 24
WORKER_PYTHON = "/usr/bin/python3"
REVIEW_SHUFFLE_SEED = 21937
LABELS = tuple(
    f"{arm}_{task}_{rep:02d}" for rep in range(1, REPLICATES + 1) for task in TASKS for arm in ARMS
)
QUANTITY_SUFFIX = """Shared public quantity and delivery contract for this study:
The monetary targets in these tasks are U.S. dollar (USD) amounts; no currency conversion is
requested. Dollar-denominated source amounts are interpreted in that same currency unless the
source explicitly states otherwise; an explicit conflicting currency must never be silently
replaced. Source scales remain as stated, and all source material stays visible.
For clear delivery, prefer a final object containing a finite numeric value, a textual unit, an
answer, and the actual supporting result_id. The preferred unit spelling for a result expressed
in millions of U.S. dollars is USD_million. This spelling is a formatting preference, not a
financial-validity requirement. Quantity interpretation and formatting are evaluated separately.
The separate canonical-format flag checks only that final.value is a supported scalar and
final.unit is exactly USD_million; it does not certify correctness or source linkage.
Ordinary compositions of currency and scale words, such as "$ in millions", are interpretable.
"million" or "millions" alone states scale only: currency can be completed solely when the public
target and relevant source uniquely agree and no contrary currency is stated. Never infer a
missing scale from the question or use a correct-looking number to override a unit conflict.
The finite numeric interpretation accepts decimal or fractional text up to 256 characters,
including scientific notation with an exponent between -18 and 18.
Unsupported values stay unresolved.
An explicit amount and unit in the actual Final text can also deliver a quantity, even if the
preferred object fields are absent. No value or unit will be copied from a preceding message,
tool result, or private reference to complete an uninterpretable Final. Conflicting Final fields
or unresolved currency/scale keep their own failure or uncertainty status.
The first Final still terminates immediately; these evaluation rules do not introduce online
correctness feedback, retries, or a required extra calculation."""
SOFT_SUFFIX = """For this solution, give priority to examining sufficient evidence based on period
components or movements. Determine the items, signs, sources, and expression yourself from the
complete document. If you adopt such evidence, actually execute the calculation supporting your
final answer. If sufficient evidence cannot be established, say so honestly and do not invent it."""
SYSTEMS_NEW = {
    "N": SYSTEMS["T"] + "\n\n" + QUANTITY_SUFFIX,
    "E": SYSTEMS["T"] + "\n\n" + QUANTITY_SUFFIX + "\n\n" + SOFT_SUFFIX,
}


def require(value, code):
    if not value:
        raise ValueError(code)


def record(kind, **fields):
    body = {"schema_version": "soft_detail_exploration.v1." + kind, **fields}
    return {**body, "id": kind + ":" + sha(encode(body))}


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
        "history.any_prior_code_data_score_or_panel_changed",
    )
    require(
        not subprocess.check_output(["git", "status", "--porcelain", "--", *paths], cwd=root),
        "history.uncommitted_outside_new_study",
    )
    return {
        "baseline": BASELINE,
        "all_files_outside_new_study_unchanged": True,
        "old_72_Flash_sessions_not_resumed_or_regraded": True,
        "old_development_confirmation_and_control_panels_unchanged": True,
    }


def public_quantity_context():
    return {
        "dimension": "money",
        "target_currency": "USD",
        "public_target_currencies": ["USD"],
        "relevant_source_currencies": ["USD"],
        "target_scale": "1000000",
        "preferred_unit": "USD_million",
        "source": "shared public quantity contract plus unchanged dollar-denominated source",
        "no_currency_or_scale_inferred_from_private_reference": True,
    }


def condition(arm):
    require(arm in ARMS, "condition.registered_arm")
    return record(
        "fixed_exploration_condition",
        arm=arm,
        model=MODEL,
        accepted_response_models=list(ACCEPTED_RESPONSE_MODELS),
        system=SYSTEMS_NEW[arm],
        system_sha256=sha(SYSTEMS_NEW[arm].encode()),
        source_tasks=list(TASKS),
        replicates_per_task=REPLICATES,
        thinking="enabled",
        reasoning_effort="high",
        temperature_top_p="omitted",
        limits=LIMITS,
        current_Flash_contract_reused_without_calibration=True,
        shared_quantity_context=public_quantity_context(),
        soft_detail_instruction=SOFT_SUFFIX if arm == "E" else None,
        guided_exploration=arm == "E",
        no_task_formula_source_id_or_answer_in_suffix=True,
        same_complete_sources_and_first_Final_stop=True,
        no_route_forcing_no_endpoint_hiding_no_second_calculation_requirement=True,
        provider_random_states_paired_or_seed_controlled=False,
    )


def policy():
    return record(
        "bounded_exploration_policy",
        sessions=48,
        per_task_per_condition=8,
        maximum_generation_requests=1536,
        response_and_tool_limit=32,
        concurrent_workers=WORKERS,
        waves=2,
        submissions_per_wave=24,
        submission_order="replicate ascending; each task N then E; two complete balanced waves",
        provider_start_or_finish_order_not_claimed_identical_to_submission_order=True,
        stop="all 48 registrations completed or terminally unavailable; never resample or train",
        quantity_policy="public_quantity_interpretation.v1",
        quantity_and_format_separate=True,
        canonical_unit_format_is_not_hard_trace_gate=True,
        positive_targets=(
            "all original legal public messages, successful tools and first Final "
            "in a joint-valid whole session; failed requests only remain in "
            "history"
        ),
        execution_R_yield="confirmed actual source-symbolic R execution / 8",
        valid_pure_R_yield="joint-valid complete registered pure R signature / 8",
        mention_execution_source_Final_and_full_behavior_separate=True,
        failed_unknown_unfinished_sessions_remain_in_all_registered_denominators=True,
        missing_mapping_preserves_original_financial_validity=True,
        within_condition_classes_only=True,
        exploratory_instruction_is_not_actual_Assignment=True,
        training_selections=[],
        training_runs=0,
        student_sessions=0,
        auxiliary_NLL=0,
        tokenizer_or_Student_weight_loading=False,
        token_consumability="NOT_MEASURED",
        readiness=(
            "report counts of valid original pure D/R sessions within each "
            "condition only; do not instantiate training kappa or mix N/E "
            "prefixes"
        ),
        full_actual_conditional_prefixes_preserved=True,
        reviewer=(
            "executing assistant; labels, condition, costs and model identifiers "
            "hidden in review packets where feasible; not independent or "
            "guaranteed fully blinded"
        ),
        old_scores_not_reopened=True,
        no_effect_or_Contribution_inferred=True,
    )


def registrations(public):
    shuffled = list(LABELS)
    random.Random(REVIEW_SHUFFLE_SEED).shuffle(shuffled)
    review_ids = {label: f"review_{i:03d}" for i, label in enumerate(shuffled, 1)}
    return [
        record(
            "exploration_registration",
            label=label,
            ordinal=i,
            wave=(i - 1) // 24 + 1,
            arm=arm,
            task_key=key,
            replicate=int(rep),
            review_id=review_ids[label],
            requested_model=MODEL,
            condition_id=condition(arm)["id"],
            system_sha256=sha(SYSTEMS_NEW[arm].encode()),
            task_id=public[key]["task_id"],
            public_document_id=public[key]["id"],
            response_budget=32,
            tool_budget=32,
            fresh_independent_session=True,
        )
        for i, label in enumerate(LABELS, 1)
        for arm, key, rep in [label.split("_")]
    ]
