"""Pre-call condition, exact population and immutable history boundary."""

import subprocess
from pathlib import Path

from trusted_synthesis.experiments.finance_qa_vnext_thinking_comparison.online.common import (
    LIMITS,
    record,
    sha,
)

from .instructions import SYSTEMS, TRACE_SUFFIX

BASELINE = "1282a57e255211ddf86ffc9bbfa016b23c573798"
PACKAGE = "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_trace_delivery"
OUTPUT = "trusted_data_synthesis/artifacts/qa_vnext_trace_delivery/flash_high_at_2rep_20260909"
DOCUMENT = "trusted_data_synthesis/docs/finance_qa_vnext_trace_delivery.md"
TEST = "trusted_data_synthesis/tests/test_qa_vnext_trace_delivery.py"
WORKER_PYTHON = "/usr/bin/python3"
MODEL = "deepseek-v4-flash"
CONDITIONS = {"A": "original_autonomous", "T": "public_trace_deliverable"}
TASKS = ("N1", "N2", "N3", "N4", "N5", "N6")
LABELS = tuple(
    f"{arm}_{key}_{rep:02d}"
    for rep in (1, 2)
    for key in TASKS
    for arm in (("A", "T") if rep == 1 else ("T", "A"))
)
AUDIT_PATH = (
    "/home/zhuxinrui/.codex/attachments/0ef3cc5f-6aeb-4f36-b8e2-2296fae8c47a/pasted-text.txt"
)
AUDIT_SHA256 = "65e04d26111844527256f1821eac93ba253cc5d750bf61b23fa2450c583b2325"


def condition():
    return record(
        "trace_delivery_condition",
        model=MODEL,
        conditions=CONDITIONS,
        tasks=list(TASKS),
        labels=list(LABELS),
        task_weights_per_condition={key: "1/6" for key in TASKS},
        thinking="enabled",
        reasoning_effort="high",
        temperature_and_top_p="omitted_not_effective_in_thinking",
        limits=LIMITS,
        maximum_model_requests=768,
        maximum_reserved_token_allowance=88866816,
        system_prompts=SYSTEMS,
        system_sha256={arm: sha(text.encode()) for arm, text in SYSTEMS.items()},
        trace_instruction_suffix=TRACE_SUFFIX,
        intervention="only the fixed cross-task public-deliverable instruction appended to SYSTEM",
        original_worker_calculator_isolate_projection_bytes=True,
        condition_A_common_original_bytes=True,
        condition_T_common_only_static_system_append=True,
        public_source_document_same_for_A_and_T=True,
        independent_history_and_no_shared_answers=True,
        scheduling="two fixed replicate waves; 12 independent concurrent workers per wave; "
        "A/T by task in wave 1 and T/A by task in wave 2; no adaptive allocation",
        first_final_terminal_even_without_calculation=True,
        missing_sources_and_financially_wrong_arithmetic_still_executable=True,
        no_online_instruction_acceptance_gate=True,
        no_task_specific_formula_or_selected_sources=True,
        no_host_planning_or_calculation_on_behalf_of_model=True,
        public_storage="in-memory allowlist projection before disk; public content byte-exact",
        reasoning_telemetry_only=True,
        private_reasoning_text_or_hash_stored=False,
        numeric_policy="unchanged publication_tolerance.v2; main value priority; exact fractions; "
        "min(.005,max(half lexical quantum,1e-12)); "
        "secondary same-reference display check unchanged",
        diagnostic_only_internal_field_consistency_not_new_scoring=True,
        review_policy="condition-label-masked finite public-evidence review before label decoding; "
        "executing agent, not an independent human expert; style may reveal condition",
        no_retries=True,
        no_resampling=True,
        no_thinking_downgrade=True,
        no_model_fallback=True,
        no_pro_reference_in_new_population=True,
        no_student=True,
        no_vtdo=True,
        no_quotient=True,
        no_token_export=True,
        no_old_side_table_or_old_session_rerun=True,
        inference_scope="six new-to-current-harness task instances, two repeats per cell; "
        "transfer diagnostic, not proof of training-set novelty, statistical superiority, "
        "or improved intrinsic reasoning ability",
    )


def require(value, code):
    if not value:
        raise ValueError(code)


def history_guard(root):
    paths = [
        "trusted_data_synthesis",
        ":(exclude)" + PACKAGE,
        ":(exclude)trusted_data_synthesis/artifacts/qa_vnext_trace_delivery",
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
    return [
        record(
            "trace_delivery_registration",
            label=label,
            ordinal=ordinal,
            task_key=key,
            arm=arm,
            instruction_condition=CONDITIONS[arm],
            requested_model=MODEL,
            system_sha256=sha(SYSTEMS[arm].encode()),
            replicate=int(rep),
            task_id=public_documents[key]["task_id"],
            public_document_id=public_documents[key]["id"],
            condition_id=condition()["id"],
            response_budget=32,
            tool_budget=32,
            fresh_independent_session=True,
        )
        for ordinal, label in enumerate(LABELS, 1)
        for arm, key, rep in [label.split("_")]
    ]


def read_json(path):
    import json

    return json.loads(Path(path).read_bytes())
