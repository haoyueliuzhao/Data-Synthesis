"""Public runtime contracts: views of source QA, never new or relabelled QA.

This module accepts PublicTask only. The DSL specification is shared verbatim
across conditions and tasks and never reads a reference program or answer.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .contracts import PublicTask, digest

PUBLIC_PROFILE_ID = "finqa_program_v1"
PUBLIC_PROFILE_V2_ID = "finqa_program_v2"
PUBLIC_PROFILE_V2 = PUBLIC_PROFILE_V2_ID
FINQA_PROFILE_IDS = frozenset({PUBLIC_PROFILE_ID, PUBLIC_PROFILE_V2_ID})
MISSING_PREDICTION_POLICY = "settled_model_terminal_missing_or_invalid_prediction_is_zero_v1"
FINQA_OPERATORS = (
    "add",
    "subtract",
    "multiply",
    "divide",
    "exp",
    "greater",
    "table_max",
    "table_min",
    "table_sum",
    "table_average",
)
MODEL_TERMINAL_REASONS = frozenset(
    {
        "final_answer",
        "max_steps",
        "context_exceeded",
        "no_tool_call",
        "multiple_tool_calls",
    }
)


def _profile_v1() -> dict[str, Any]:
    """Historical profile definition; its serialized bytes and digest stay unchanged."""
    return {
        "id": PUBLIC_PROFILE_ID,
        "dataset": "finqa",
        "version": 1,
        "required_final_fields": ["answer", "program"],
        "final_submission": (
            "Submit both answer and your predicted FinQA program through the harness-defined "
            "Final submission. "
            "A numeric answer without a program is not a valid prediction for native metrics. "
            "Final only submits the program; program evaluation is offline."
        ),
        "dsl": {
            "allowed_operators": list(FINQA_OPERATORS),
            "syntax": (
                "Use a nonempty sequence op(arg1, arg2), op(arg1, arg2), ... . "
                "Use exactly comma-space between operands and between steps, with no nested "
                "calls. The last step is the program result. Alternatively submit a token "
                "array with four tokens per step: operator plus '(', arg1, arg2, ')' and "
                "a final 'EOF' token. All array elements must be strings."
            ),
            "arithmetic_operands": (
                "Numeric literals (including decimals and percentages), const_<number>, "
                "const_m1 for negative one, or #k referring to the result of an earlier "
                "zero-based step. Forward/self references are invalid. Commas inside "
                "numeric literals are removed by the official numeric parser."
            ),
            "arithmetic_semantics": {
                "add": "arg1 + arg2",
                "subtract": "arg1 - arg2",
                "multiply": "arg1 * arg2",
                "divide": "arg1 / arg2",
                "exp": "arg1 raised to arg2",
                "greater": "'yes' if arg1 > arg2, else 'no'",
            },
            "table_operands": (
                "For table_max, table_min, table_sum and table_average, arg1 is the exact "
                "public first-column row label; arg2 is the placeholder none. The operation "
                "uses all subsequent numeric cells in that row, not a selected cell."
            ),
            "numeric_semantics": (
                "Official FinQA execution uses floating-point arithmetic and rounds the last "
                "numeric result to five decimal places. A percent literal is divided by 100. "
                "The Final answer should agree with the submitted program's result."
            ),
        },
        "missing_prediction_policy": MISSING_PREDICTION_POLICY,
        "model_terminal_reasons": sorted(MODEL_TERMINAL_REASONS),
        "scoring_policy": (
            "After known-settled normal model termination, no Final, no program, malformed "
            "or invalid program yields native execution=0 and program=0. Missing scorer "
            "dependencies, inconsistent references and unresolved infrastructure/call "
            "settlement remain unscorable/unknown, not model zeros. Official scorer bytes "
            "are unchanged. Program correctness does not certify the actual tool trajectory."
        ),
        "same_contract_for_all_conditions": True,
        "contains_task_specific_reference": False,
    }


def profile_definition(profile_id: str = PUBLIC_PROFILE_ID) -> dict[str, Any]:
    """Return a fresh common contract, without reading tasks or private references."""
    if profile_id not in FINQA_PROFILE_IDS:
        raise ValueError(f"unknown submission profile: {profile_id}")
    profile = _profile_v1()
    if profile_id == PUBLIC_PROFILE_ID:
        return profile
    profile.update(
        id=PUBLIC_PROFILE_V2_ID,
        version=2,
        previous_profile_id=PUBLIC_PROFILE_ID,
        one_fixed_public_instruction_revision=True,
        examples_are_synthetic_not_selected_from_benchmark_references=True,
        three_languages={
            "tool_result_references": (
                "Only when tools are enabled, each visible tool content contains a short "
                "result_handle such as r1, status and output. Reference a previous successful "
                "result with a whole string value such as prev:r1.output.content.1.1. "
                "Dot-separated numeric components index arrays. Put these whole references "
                "in calculate.variables values, or other reference-enabled value fields "
                "such as a Final answer. Never embed prev: in calculate.expression. "
                "Do not use internal call IDs, tool names, guessed handles, bracket syntax, "
                "future/failed results, or handles from another session."
            ),
            "calculate_expression": (
                "The calculate tool uses a separate bounded scalar arithmetic language: "
                "numeric literals, names declared in variables, parentheses, + - * / ** and "
                "unary +/-. It uses decimal precision 34; no function calls, indexing, "
                "attributes, table_sum(), subtract(), #k or embedded prev: expressions. "
                "For example expression a-b with variables supplying a and b. "
                "Numbers must be finite, magnitude <=1e100; no automatic comma, unit or "
                "percent conversion. Limits: 2048 expression characters, 128 AST nodes, "
                "64 named variables, exponent magnitude <=16."
            ),
            "final_finqa_program": (
                "The submitted program is a separate linear FinQA DSL, evaluated offline. "
                "Use subtract(120, 90), divide(#0, 90): first subtract, then divide the result "
                "of step 0 by 90. Use comma-space separators. Do not nest calls, use tool "
                "result handles, embed prev:, or copy a calculate infix expression as program. "
                "#0 refers to an earlier program step, never a tool result. Table operations "
                "use the exact complete public row label with no added quotation marks: "
                "table_max(Revenue, none) is valid for the synthetic Revenue row below; "
                "table_max('Revenue', none) looks for a different row whose label includes "
                "the quote characters and is invalid when that quoted row does not exist."
            ),
        },
        synthetic_example={
            "scope": (
                "Illustrative documentation only, not an executed tool history or a source "
                "for the current QA. These invented Revenue numbers do not replace the "
                "current task's original sources. Direct-DSL receives no live tool results."
            ),
            "source": {
                "source_id": "synthetic_revenue",
                "kind": "table",
                "locator": "synthetic-only/table",
                "content": [["metric", "current", "prior"], ["Revenue", "120", "90"]],
            },
            "read_source_arguments": {"source_id": "synthetic_revenue"},
            "illustrative_read_observation": {
                "result_handle": "r1",
                "status": "ok",
                "output": {
                    "source_id": "synthetic_revenue",
                    "kind": "table",
                    "locator": "synthetic-only/table",
                    "content": [["metric", "current", "prior"], ["Revenue", "120", "90"]],
                },
            },
            "calculate_arguments": {
                "expression": "(a-b)/b",
                "variables": {"a": "prev:r1.output.content.1.1", "b": "prev:r1.output.content.1.2"},
            },
            "illustrative_calculation_observation": {
                "result_handle": "r2",
                "status": "ok",
                "output": {
                    "result": "0.3333333333333333333333333333333333",
                    "expression": "(a-b)/b",
                    "variables": {"a": "120", "b": "90"},
                    "decimal_precision": 34,
                },
            },
            "final_semantic_fields": {
                "answer": "0.33333",
                "scale": "",
                "program": "subtract(120, 90), divide(#0, 90)",
            },
            "final_note": (
                "Submit through the active harness's Final transport. The example answer "
                "matches the last program result rounded to five decimals; the calculator "
                "retains its independent 34-digit decimal result."
            ),
        },
    )
    return profile


def public_run_view(task: PublicTask, profile_id: str = PUBLIC_PROFILE_ID) -> PublicTask:
    """Make a hash-bound public view without changing source text, QA ID or snapshot.

    Already-profiled views are rejected so a view can never silently become the
    claimed original. Callers must retain the source snapshot and run-view hash.
    """
    if not isinstance(task, PublicTask):
        raise TypeError("public_run_view accepts PublicTask, never TaskBundle/private reference")
    profile = profile_definition(profile_id)
    if task.dataset != profile["dataset"]:
        raise ValueError("submission profile does not match the original task dataset")
    if "submission_profile" in task.answer_contract:
        raise ValueError("runtime view must be derived from the original public task")
    contract = deepcopy(task.answer_contract)
    contract.update(
        {
            "program": "required predicted FinQA DSL program; see submission_profile",
            "profile_id": profile_id,
            "profile_sha256": digest(profile),
            "original_public_task_sha256": digest(task),
            "submission_profile": profile,
        }
    )
    return task.model_copy(update={"answer_contract": contract})
