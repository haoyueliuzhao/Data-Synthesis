"""New architecture condition. Public generation bundle and private evaluator are separate."""

import subprocess
from pathlib import Path

from .online.common import LIMITS, SYSTEM, record

BASELINE = "a84ba9b46ac35e1d4322b253ac757fa366515b27"
PACKAGE = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_autonomous_formula"
)
OUTPUT = "trusted_data_synthesis/artifacts/qa_vnext_autonomous_formula/six_tasks_2rep_20260909"
DOCUMENT = "trusted_data_synthesis/docs/finance_qa_vnext_autonomous_formula.md"
TEST = "trusted_data_synthesis/tests/test_qa_vnext_autonomous_formula.py"
WORKER_PYTHON = "/usr/bin/python3"
TASKS = ("C2", "E1", "E3", "M3", "J1", "J2")
LABELS = tuple(f"{key}_{rep:02d}" for rep in (1, 2) for key in TASKS)


def condition():
    return record(
        "architecture_condition",
        tasks=list(TASKS),
        task_weights={t: "1/6" for t in TASKS},
        labels=list(LABELS),
        information="complete original table/pre_text/post_text, uniform all-number indexing",
        model="deepseek-v4-pro",
        temperature=0.7,
        top_p=1.0,
        thinking="disabled",
        response_format="json_object",
        native_tools=False,
        system_prompt=SYSTEM,
        limits=LIMITS,
        maximum_model_requests=384,
        maximum_reserved_tokens=41287680,
        input_admission="whole actual HTTP body bytes<=98304, including complete history; "
        "+1024 overhead allowance; reservation is not measured provider usage",
        lifecycle="optional message or explicit tool call; "
        "first unambiguous JSON final ends immediately",
        no_formula_gate=True,
        no_accept_state=True,
        no_online_target_feedback=True,
        source_declarations_optional_for_numeric_execution=True,
        execution="standalone -I -S stdlib process, Linux Landlock public-only file allowlist",
        private_evaluation="loaded only by the separate parent after all workers have terminated",
        benchmark_scope="six previously interpreted development tasks, not unseen or blind data",
        comparison_scope="whole architecture bundle; no single-change causal comparison "
        "with old success rates",
        answer_policy="published numeric value, direction and explicit or question-implied units; "
        "rational exactness or rounding interval at reported precision, "
        "never looser than half of 0.01 units",
        trace_policy="separate pre-execution relationship, source-variable correspondence, "
        "scale/sign, independent actual arithmetic and publication. Missing provenance or "
        "unsupported alternatives are undetermined, not automatic numeric-answer errors. "
        "Manual semantic review must quote original pre-tool text/requests",
        no_after_final_formula_credit=True,
        rubric_frozen_before_generation=True,
        semantic_review_unblinded=True,
        no_new_quotient=True,
        no_token_export=True,
        student=False,
        gpu=False,
        vtdo=False,
        resampling=False,
    )


def require(value, code):
    if not value:
        raise ValueError(code)


def history_guard(root):
    paths = [
        "trusted_data_synthesis",
        ":(exclude)" + PACKAGE,
        ":(exclude)trusted_data_synthesis/artifacts/qa_vnext_autonomous_formula",
        ":(exclude)" + DOCUMENT,
        ":(exclude)" + TEST,
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
    return {"baseline": BASELINE, "historical_files_unchanged": True}


def registrations(public_documents):
    rows = []
    for ordinal, label in enumerate(LABELS, 1):
        key, rep = label.split("_")
        rows.append(
            record(
                "registration",
                label=label,
                ordinal=ordinal,
                task_key=key,
                replicate=int(rep),
                task_id=public_documents[key]["task_id"],
                public_document_id=public_documents[key]["id"],
                condition_id=condition()["id"],
                response_budget=32,
                tool_budget=32,
                fresh_independent_session=True,
            )
        )
    return rows


def read_json(path):
    import json

    return json.loads(Path(path).read_bytes())
