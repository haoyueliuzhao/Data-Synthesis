"""Pre-call budget, open generation condition, review and finite behavior policies."""

import json
import subprocess
from pathlib import Path

from trusted_synthesis.experiments.finance_qa_vnext_thinking_comparison.online.common import (
    LIMITS,
    encode,
    sha,
)
from trusted_synthesis.experiments.finance_qa_vnext_trace_delivery.instructions import SYSTEMS

BASELINE = "c549e1aff48d73e9aff563648eaf309931d37f3c"
PACKAGE = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "finance_qa_vnext_open_support_exploration"
)
OUTPUT = (
    "trusted_data_synthesis/artifacts/qa_vnext_open_support_exploration/"
    "three_structures_4rep_20260909"
)
DOCUMENT = "trusted_data_synthesis/docs/finance_qa_vnext_open_support_exploration.md"
TESTS = (
    "trusted_data_synthesis/tests/test_qa_vnext_open_support_exploration.py",
    "trusted_data_synthesis/tests/test_qa_vnext_open_support_projection.py",
)
MODEL = "deepseek-v4-flash"
SYSTEM = SYSTEMS["T"]
TASKS = ("G1", "G2", "F1", "F2", "L1", "L2")
STRUCTURES = {
    "G1": "disclosed_total_and_component_reconstruction",
    "G2": "disclosed_total_and_component_reconstruction",
    "F1": "disclosed_metric_and_definition_reconstruction",
    "F2": "disclosed_metric_and_definition_reconstruction",
    "L1": "balance_difference_and_period_movements",
    "L2": "balance_difference_and_period_movements",
}
ANCHORS = {"G1": "N1", "F1": "N4", "L1": "N5"}
LABELS = tuple(f"T_{task}_{rep:02d}" for rep in range(1, 5) for task in TASKS)
WORKER_PYTHON = "/usr/bin/python3"
AUDIT_PATH = (
    "/home/zhuxinrui/.codex/attachments/48bdf682-f8bb-4ce2-a712-0277322d3bda/pasted-text.txt"
)
AUDIT_SHA256 = "84080974ac58c68e06513262532fcd9a962493324e4892acf7e4cb82ecbd0c27"


def record(kind, **fields):
    body = {"schema_version": "open_support_exploration.v1." + kind, **fields}
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
        ":(exclude)trusted_data_synthesis/artifacts/qa_vnext_open_support_exploration",
        ":(exclude)" + DOCUMENT,
        *[":(exclude)" + name for name in TESTS],
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
    return {"baseline": BASELINE, "all_historical_files_unchanged": True}


def condition():
    return record(
        "fixed_open_support_condition",
        model=MODEL,
        system=SYSTEM,
        system_sha256=sha(SYSTEM.encode()),
        parent_T_instruction_unchanged=True,
        thinking="enabled",
        reasoning_effort="high",
        temperature_top_p="omitted; no new decoding intervention",
        tasks=list(TASKS),
        structures=STRUCTURES,
        anchors=ANCHORS,
        labels=list(LABELS),
        new_task_population=True,
        task_marginal={task: "1/6" for task in TASKS},
        replicates_per_task=4,
        independent_new_sessions=24,
        old_trajectories_in_new_frequency_denominator=False,
        limits=LIMITS,
        maximum_model_requests=768,
        maximum_reserved_token_allowance=768 * 115712,
        concurrent_workers=24,
        fixed_allocation_no_adaptive_prompt_or_resampling=True,
        all_registrations_before_any_provider_call=True,
        no_retries_no_fallback_no_budget_increase=True,
        original_worker_calculator_projection_isolate_bytes=True,
        complete_original_question_and_source_visible=True,
        private_route_options_never_in_model_input=True,
        force_reconstruction=False,
        hide_disclosure=False,
        independent_empty_histories_no_shared_notes_or_answers=True,
        first_Final_terminal_even_if_incorrect_or_no_calculation=True,
        success_does_not_require_multiple_classes=True,
        private_reasoning_storage=False,
        Student=False,
        GPU=False,
        training=False,
        VTDO=False,
    )


def policy():
    return record(
        "finite_new_support_policy",
        task_definition=(
            "original unmodified question; complete original source; fixed private target and "
            "verified sufficient relations before first generation"
        ),
        validity=(
            "unchanged publication_tolerance.v2 and finite public semantic review: applicable "
            "formula, corresponding actual inputs, units, actual calculation and consistent Final"
        ),
        source_attribution=(
            "explicit model source declaration versus reviewer-resolved role/period/unit "
            "association versus actual consumed values; no value-only source matching"
        ),
        review_author=(
            "executing research agents; source targets known; not blind or independent human "
            "financial certification"
        ),
        occurrence_ledger=(
            "authored after generation against exact raw public evidence, under pre-call "
            "source/interpretation rules; no class-count-driven rule changes"
        ),
        rational_normalizer=(
            "reuse frozen open-materialization +,-,*,/,sum,avg domain; unsupported/domain-erasing"
            " cancellation => UNDETERMINED"
        ),
        financial_identities="allowed for answer validity, never expanded in behavior signatures",
        behavior_signature=[
            "fixed_condition",
            "task_version",
            "source_document_id",
            "goal_scope",
            "answer_source_normal_form",
            "active_support",
            "substantive_revision_path",
            "evidenced_independent_cross_checks",
        ],
        nuisance=[
            "variable names",
            "whitespace",
            "JSON ordering",
            "equivalent same-source arithmetic",
            "zero-contribution algebra",
            "tool granularity after unfolding actual referenced results",
            "evidence-verified format-only recovery",
        ],
        real_result_references=(
            "must match actual prior successful result_id and exact consumed value; unfold source"
            " expression, not equal-valued guesses"
        ),
        support_reading=(
            "merely mentioning or reading alternative evidence is not actual use; retain original"
            " read records separately"
        ),
        cross_checks=(
            "retain a distinct source-grounded verification episode only when actually executed "
            "and explicitly linked by public evidence to checking the task result; an extra "
            "unrelated call alone is not a new class"
        ),
        revisions=(
            "retain ordered evidence-grounded changes in formula, source pairing, unit meaning or"
            " task interpretation, even if final normal forms agree"
        ),
        unmapped_semantics=(
            "retain original validity and full session; behavior UNDETERMINED for unsupported "
            "expressions, unresolved attribution, unreviewed messages/calls or unclear revisions"
        ),
        positive_targets=(
            "valid sessions: every original structurally legal message-only response, successful "
            "calculate/read_source/notebook request and actual Final; JSON/protocol errors and "
            "failed tool requests are retained in the full session and subsequent inputs but not "
            "positive targets"
        ),
        no_host_merge_rewrite_or_inserted_annotations=True,
        representation=(
            "exact same-turn request.messages and assistant.raw; reuse existing local "
            "tokenizer/32768/no-truncation/target-only-label policy only for these new candidates"
        ),
        full_package=(
            "all original public responses/events including errors; positive-target eligibility "
            "separate; no claim that excluded error turns receive positive loss"
        ),
        empirical_quality="valid_count/4 for each task; all registered expense retained",
        empirical_class_mass=(
            "class_count/all originally valid new sessions; unresolved mass retained; full "
            "distribution null if any valid trajectory remains unmapped"
        ),
        local_two_support_witness=(
            "any two confirmed DISTINCT valid trajectories of the same task suffice, even with "
            "other valid mappings unresolved; not a complete population distribution"
        ),
        no_valid_support="conditional distribution null, not proof of no possible valid behavior",
        class_probability_degrees_of_freedom=(
            "sum(observed class count - 1) only over supported tasks with complete mappings; not "
            "a cross-task class pool"
        ),
        training_weights=None,
        rare_or_longer_is_not_higher_contribution=True,
        old_64_controls_or_old_24_token_rows_repeated=False,
        stopping=(
            "24 registered bounded sessions plus offline evaluation, finite measurement and "
            "original new-package export; single-class outcomes accepted, never top up to two "
            "classes"
        ),
    )


def registrations(public):
    return [
        record(
            "new_support_registration",
            label=label,
            ordinal=index,
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
            original_source_anchor=ANCHORS.get(key),
            fresh_independent_session=True,
        )
        for index, label in enumerate(LABELS, 1)
        for _, key, rep in [label.split("_")]
    ]
