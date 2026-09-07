"""Freeze census/panel; exactly one fresh E/F session per original FinQA question."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Literal

from trusted_synthesis.domains.finance.qa_vnext.protocol import record, require
from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore
from trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.audit import (
    manifest,
    no_plan,
)
from trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.stage import SYSTEM
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.plan import (
    seal_directory,
    source_snapshot,
    verify_source_snapshot,
)
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.runner import _credential
from trusted_synthesis.experiments.finance_qa_vnext_model_execution.transport import (
    OnlineModelCallback,
    TransportConfig,
    render_http_request,
)

from .audit import read, verify_session
from .census import census
from .controls import witness
from .panel import EXCLUSIONS, SPECS, Panel
from .runtime import VERSION, Runtime

PARENT = "964e0811a5bb51997c0c58665dcd82949ea7410b"
OUTPUT = "trusted_data_synthesis/artifacts/qa_vnext_finqa_difficulty/original_12_ef_v1_20260908"
DESIGN = "trusted_data_synthesis/docs/finance_qa_vnext_finqa_difficulty_ef.md"
TEST = "trusted_data_synthesis/tests/test_qa_vnext_finqa_difficulty.py"
AUDIT_SHA256 = "555c7696e202a44c8286ccc99b651d69168cc57135a860cf71149357101524ff"
LABELS = tuple(f"{key}_{h}_01" for key in SPECS for h in ("E", "F"))


class Config(TransportConfig):
    maximum_pilot_attempts: Literal[768] = 768


def configuration():
    return Config(system_prompt=SYSTEM)


def history_guard(root):
    paths = [
        "trusted_data_synthesis/artifacts",
        ":(exclude)trusted_data_synthesis/artifacts/qa_vnext_finqa_difficulty",
        (
            "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnex"
            "t_harness_responsibility"
        ),
        (
            "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnex"
            "t_harness_transfer"
        ),
    ]
    require(
        not subprocess.check_output(["git", "diff", "--name-only", PARENT, "--", *paths], cwd=root),
        "stage.historical_changes",
    )
    require(
        not subprocess.check_output(["git", "status", "--porcelain", "--", *paths], cwd=root),
        "stage.historical_uncommitted_changes",
    )
    return {
        "parent_commit": PARENT,
        "previous_artifacts_and_H1_H2_unchanged": True,
        "historical_tests_rerun": False,
    }


def prepare(root):
    output = root / OUTPUT
    require(not output.exists(), "stage.preparation_exists")
    implementation = source_snapshot(root)
    panel, config = Panel(root), configuration()
    store = DurableStore(output / "preparation")
    rows, summary = census(root)
    store.json("census_rows.json", rows)
    store.json("census_summary.json", summary)
    store.json("bindings.json", panel.bindings())
    store.json("screening_exclusions.json", EXCLUSIONS)
    store.json("implementation.json", implementation)
    store.json("history_guard.json", history_guard(root))
    store.json("configuration.json", config.as_record())
    store.write("design_at_freeze.md", (root / DESIGN).read_bytes())
    check = subprocess.run(
        [
            str(root / "trusted_data_synthesis/.venv/bin/python"),
            "-m",
            "pytest",
            "-q",
            "--tb=short",
            TEST,
        ],
        cwd=root,
        capture_output=True,
        check=False,
    )
    store.write("tests_stdout.txt", check.stdout)
    store.write("tests_stderr.txt", check.stderr)
    store.json(
        "tests.json",
        {
            "exit_code": check.returncode,
            "test_sha256": hashlib.sha256((root / TEST).read_bytes()).hexdigest(),
            "provider_calls": 0,
            "historical_tests_rerun": False,
        },
    )
    require(check.returncode == 0, "stage.new_controls_failed")
    registrations = []
    for ordinal, label in enumerate(LABELS, 1):
        key, h, _ = label.split("_")
        registration = record(
            "finqa_registration",
            label=label,
            ordinal=ordinal,
            task_key=key,
            stratum=SPECS[key][0],
            condition=h,
            task_id=SPECS[key][1],
            fresh_session=True,
            maximum_actions=12,
            maximum_submissions=32,
            maximum_provider_attempts=32,
            information_condition_only_varies_within_pair=True,
        )
        registrations.append(registration)
        runtime = Runtime(panel, key, h, "static:" + label)
        initial = runtime.request()
        no_plan(initial)
        require(
            not any(
                k in initial["context"]
                for k in ("target", "program", "gold_inds", "answer", "selected")
            ),
            "stage.private_reference_leak",
        )
        static = witness(runtime)
        sizes = [
            render_http_request(
                e["request"], config, session_id="static:" + label, attempt_index=i
            )["body_byte_count"]
            for i, e in enumerate(static["events"])
        ]
        require(
            max(sizes) <= 98304 and static["actions"] <= 12 and static["submissions"] <= 32,
            "stage.static_budget",
        )
        store.json(f"static_witnesses/{label}.json", static)
        store.json(f"initial_requests/{label}.json", initial)
        store.json(
            f"static_capacity/{label}.json",
            {
                "actions": static["actions"],
                "submissions": static["submissions"],
                "maximum_witness_request_bytes": max(sizes),
                "not_a_worst_case_model_trajectory_bound": True,
            },
        )
    condition = record(
        "finqa_condition",
        version=VERSION,
        audit_sha256=AUDIT_SHA256,
        source_commit=implementation["source_commit"],
        model_configuration_id=config.as_record()["id"],
        labels=list(LABELS),
        registered_sessions=24,
        denominator_per_task_condition=1,
        denominator_per_condition=12,
        strata_per_condition={s: 3 for s in ("control", "evidence", "method", "joint")},
        waves=[list(LABELS[i : i + 8]) for i in range(0, 24, 8)],
        maximum_parallel_sessions=8,
        maximum_provider_attempts=768,
        maximum_reserved_tokens=768 * 107520,
        attempts_per_session=32,
        actions_per_session=12,
        submissions_per_session=32,
        original_question_unchanged=True,
        development_diagnostic_not_blindtest=True,
        source_selection=(
            "purposive inspected panel after full census; not random or frequency matched"
        ),
        tool_extension=(
            "v2 source-indexed scalar numeric derivations; financial target verification at Final"
        ),
        within_EF_same_protocol_tools_budget_output=True,
        comparison_to_old_H2_is_not_controlled=True,
        no_success_probability_estimation=True,
        no_pure_retrieval_causal_claim=True,
        source_annotation_errors_preserved=True,
        automatic_retries=0,
        fallbacks=0,
        replacements=0,
        resume=False,
        stop_next_wave_on_integrity_or_condition_failure=True,
        negative_outcomes_do_not_trigger_resampling=True,
        student_updates=0,
        vtdo_updates=0,
        new_tokenizer_export=False,
    )
    store.json("condition.json", condition)
    store.json("registrations.json", registrations)
    store.json(
        "coverage_comparison.json",
        {
            "statuses": [
                "actually_instantiated_and_verified",
                "tool_or_semantic_wiring_missing",
                "undetermined",
            ],
            "old_H2_verified_source_derived_tasks": ["U16", "J15", "H24", "H13"],
            "old_tasks_are_original_FinQA_benchmark_questions": False,
            "old_H2_general_entries_missing": [
                "quantity_times_unit_price",
                "arbitrary_scale_conversion",
                "multi_member_aggregation",
                "minimum_maximum",
                "greater",
                "exp",
            ],
            "old_H2_original_FinQA_population_status": "undetermined",
            "old_H2_population_execution_coverage_percentage": None,
            "new_v2_original_questions": [
                {
                    "key": key,
                    "qa_id": SPECS[key][1],
                    "status": "actually_instantiated_and_verified",
                    "authority": (
                        "E/F zero-Provider static lifecycle witnesses; NOT online model outcomes"
                    ),
                }
                for key in SPECS
            ],
            "unselected_original_questions_new_v2_status": "undetermined",
            "source_overlap": {
                "distinct_pages": 12,
                "distinct_reports": 11,
                "subject_codes": 9,
                "repeated_report": "ETR/2016",
                "known_historical_pages_at_least": ["UNP/2015/page_56.pdf", "UNP/2016/page_52.pdf"],
            },
        },
    )
    seal_directory(store, kind="finqa_preparation_manifest", condition_id=condition["id"])
    return condition


def run_one(panel, registration, output, config, api_key):
    child = DurableStore(output / registration["label"])
    child.json("registration.json", registration)
    callback = OnlineModelCallback(
        config,
        session_id=registration["id"],
        evidence_directory=child.root / "transport",
        api_key=api_key,
    )
    runtime = Runtime(
        panel,
        registration["task_key"],
        registration["condition"],
        registration["id"],
        callback,
        child.root / "runtime",
    )
    try:
        runtime.run()
    finally:
        callback.finalize()
    result = verify_session(panel, registration, child.root)
    child.json("audit.json", result)
    lines = [
        f"# {registration['label']}",
        "",
        f"状态：{result['status']}；完整有效：{result['complete_valid']}。",
        "",
        "逐轮内容来自原始模型提交，未重写；数值 Claim 不自动认证其财务角色。",
        "",
        "| 提交 | 类型 | 操作／拒绝 |",
        "| --- | --- | --- |",
    ]
    for e in runtime.events:
        s = e["model_submission"] or {}
        detail = e["error"] or json.dumps(s, ensure_ascii=False)
        lines.append(
            f"| {e['submission_count']} | {s.get('kind', 'invalid')} | "
            + detail.replace("|", " / ").replace(chr(10), " ")
            + " |"
        )
    child.write("review.md", "\n".join(lines).encode())
    seal_directory(
        child,
        kind="finqa_session_manifest",
        registration_id=registration["id"],
        audit_id=result["id"],
    )
    return result


def run(root):
    output = root / OUTPUT
    manifest(output / "preparation")
    prep = output / "preparation"
    condition = read(prep / "condition.json")
    registrations = read(prep / "registrations.json")
    require(
        condition["labels"] == list(LABELS) and [r["label"] for r in registrations] == list(LABELS),
        "stage.fixed_labels",
    )
    implementation = read(prep / "implementation.json")
    verify_source_snapshot(root, implementation)
    require(
        read(prep / "configuration.json") == configuration().as_record(),
        "stage.frozen_configuration",
    )
    require(read(prep / "history_guard.json") == history_guard(root), "stage.history_guard")
    store = DurableStore(output / "online")
    store.json(
        "launch.json", record("finqa_launch", condition_id=condition["id"], registered_sessions=24)
    )
    panel, config = Panel(root), configuration()
    require(panel.bindings() == read(prep / "bindings.json"), "stage.frozen_bindings")
    api_key = _credential(root / "trusted_data_synthesis/.env")
    results, stop = [], False
    for wave in condition["waves"]:
        verify_source_snapshot(root, implementation)
        with ThreadPoolExecutor(max_workers=8) as pool:
            pending = {
                pool.submit(run_one, panel, r, store.root / "sessions", config, api_key): r
                for r in registrations
                if r["label"] in wave
            }
            for future in as_completed(pending):
                registration = pending[future]
                try:
                    result = future.result()
                except Exception as exc:
                    result = record(
                        "finqa_session_failure",
                        label=registration["label"],
                        task_key=registration["task_key"],
                        condition=registration["condition"],
                        status="unknown_integrity_or_host_failure",
                        complete_valid=False,
                        denominator=1,
                        error_type=type(exc).__name__,
                        error=str(exc)[:500],
                    )
                    store.json("failures/" + registration["label"] + ".json", result)
                    stop = True
                if result.get("condition_flags"):
                    stop = True
                results.append(result)
                print(
                    registration["label"],
                    result["status"],
                    "submissions",
                    result.get("submissions"),
                    "attempts",
                    result.get("provider_attempts"),
                    flush=True,
                )
        if stop:
            break
    bylabel = {r["label"]: r for r in results}
    ordered = [
        bylabel.get(
            label,
            {
                "label": label,
                "task_key": label.split("_")[0],
                "condition": label.split("_")[1],
                "status": "not_started_integrity_stop",
                "complete_valid": False,
                "denominator": 1,
            },
        )
        for label in LABELS
    ]
    totals = {}
    for h in ("E", "F"):
        selected = [r for r in ordered if r["condition"] == h]
        total = {
            "denominator": 12,
            "complete_valid": sum(r["complete_valid"] for r in selected),
            "statuses": dict(Counter(r["status"] for r in selected)),
        }
        for field in (
            "actions",
            "submissions",
            "provider_attempts",
            "unused_attempts",
            "unused_actions",
        ):
            total[field] = (
                sum(r[field] for r in selected) if all(field in r for r in selected) else None
            )
        total["rejections"] = (
            sum(r.get("counts", {}).get("rejections", 0) for r in selected)
            if all("counts" in r for r in selected)
            else None
        )
        total["usage"] = {
            k: sum(r["usage"][k]["total"] for r in selected)
            if all(r.get("usage", {}).get(k, {}).get("total") is not None for r in selected)
            else None
            for k in sorted({k for r in selected for k in r.get("usage", {})})
        }
        total["strata"] = {
            s: {
                "denominator": 3,
                "complete_valid": sum(
                    r["complete_valid"] for r in selected if SPECS[r["task_key"]][0] == s
                ),
            }
            for s in ("control", "evidence", "method", "joint")
        }
        totals[h] = total
    summary = record(
        "finqa_diagnostic_summary",
        condition_id=condition["id"],
        sessions=ordered,
        by_condition=totals,
        registered_denominator=24,
        provider_attempt_cap=768,
        halted_for_integrity_or_condition=stop,
        source_usage="inspected development panel, not benchmark blind evaluation",
        evidence_and_method_error_attribution=(
            "see trajectory review; off-reference reads alone are not errors"
        ),
    )
    store.json("summary.json", summary)
    verify_source_snapshot(root, implementation)
    seal_directory(
        store, kind="finqa_online_manifest", condition_id=condition["id"], summary_id=summary["id"]
    )
    print(json.dumps(totals, ensure_ascii=False, indent=2), flush=True)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["prepare", "run"])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    result = (prepare if args.command == "prepare" else run)(args.root)
    print(result["id"])


if __name__ == "__main__":
    main()
