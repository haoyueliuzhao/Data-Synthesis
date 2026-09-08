"""New architecture condition. Public generation bundle and private evaluator are separate."""

import subprocess
from pathlib import Path

from .online.common import LIMITS, SYSTEM, record

BASELINE = "858f8a4ecb86f49c59c2d37ae769b6a3d4d68362"
PACKAGE = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_thinking_comparison"
)
OUTPUT = (
    "trusted_data_synthesis/artifacts/qa_vnext_thinking_comparison/flash_pro_high_2rep_20260909"
)
DOCUMENT = "trusted_data_synthesis/docs/finance_qa_vnext_thinking_comparison.md"
TEST = "trusted_data_synthesis/tests/test_qa_vnext_thinking_comparison.py"
WORKER_PYTHON = "/usr/bin/python3"
TASKS = ("C2", "E1", "E3", "M3", "J1", "J2")
MODELS = {"F": "deepseek-v4-flash", "P": "deepseek-v4-pro"}
LABELS = tuple(
    f"{arm}_{key}_{rep:02d}"
    for rep in (1, 2)
    for key in TASKS
    for arm in (("F", "P") if rep == 1 else ("P", "F"))
)


def condition():
    return record(
        "comparison_condition",
        tasks=list(TASKS),
        labels=list(LABELS),
        models=MODELS,
        primary="F",
        reference="P",
        thinking="enabled",
        reasoning_effort="high",
        temperature_and_top_p="omitted_not_effective_in_thinking",
        task_weights_per_model={t: "1/6" for t in TASKS},
        system_prompt=SYSTEM,
        limits=LIMITS,
        maximum_model_requests=768,
        maximum_reserved_token_allowance=88866816,
        scheduling="two fixed replicate waves; 12 concurrent workers per wave; "
        "interleaved F/P by task",
        same_full_sources_tools_public_history_and_first_final_stop=True,
        financial_oracle_online=False,
        mandatory_accept=False,
        mandatory_formula=False,
        public_response_storage="in-memory allowlist projection BEFORE disk; content byte-exact",
        private_reasoning_storage=False,
        private_reasoning_hash=False,
        reasoning_in_history=False,
        native_tools=False,
        reasoning_usage="completion_tokens_details.reasoning_tokens; subset of completion; "
        "missing unknown",
        length_finish="generation_truncated_length; preserve public fragment "
        "but no tool parse or retry",
        numeric_policy="publication_tolerance.v2: rational exact; "
        "min(.005,max(half lexical quantum,1e-12))",
        multi_field_policy="value first; other answer values must agree at their own displayed "
        "precision; units/direction separately checked",
        review_policy="finite quote-grounded semantic review; model labels masked before reviews "
        "are sealed; reviewer is executing agent, not independent",
        no_retries=True,
        no_resampling=True,
        no_thinking_downgrade=True,
        no_model_fallback=True,
        no_student=True,
        no_vtdo=True,
        no_quotient=True,
        no_token_export=True,
        inference_scope="six known development tasks, two repetitions; "
        "not noninferiority or thinking-on/off causal effect",
    )


def require(value, code):
    if not value:
        raise ValueError(code)


def history_guard(root):
    paths = [
        "trusted_data_synthesis",
        ":(exclude)" + PACKAGE,
        ":(exclude)trusted_data_synthesis/artifacts/qa_vnext_thinking_comparison",
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
        arm, key, rep = label.split("_")
        rows.append(
            record(
                "registration",
                label=label,
                ordinal=ordinal,
                task_key=key,
                arm=arm,
                requested_model=MODELS[arm],
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
