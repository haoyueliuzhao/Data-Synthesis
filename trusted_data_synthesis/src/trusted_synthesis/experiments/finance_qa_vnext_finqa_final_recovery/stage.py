"""Preregister, freeze and execute exactly eight fresh E1 B/R sessions."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Literal

from trusted_synthesis.domains.finance.qa_vnext.protocol import record, require
from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore
from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.panel import SPECS, Panel
from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.reference_revision import (
    VERSION,
    ReferenceExplicitRuntime,
)
from trusted_synthesis.experiments.finance_qa_vnext_finqa_reference_diagnostic.metrics import (
    verify_public_reference,
)
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
from .metrics import aggregate
from .runtime import (
    PRESENTATION_VERSION,
    REVIEW_TEXT,
    TARGET_ERROR,
    FinalRecoveryRuntime,
    verify_feedback,
)

PARENT = "e10686e42f5ba6ee6019388232b434f60c4f44ae"
OLD_OUTPUT = (
    "trusted_data_synthesis/artifacts/qa_vnext_finqa_reference_diagnostic/"
    "original_12_ef_v21_20260908"
)
OUTPUT = "trusted_data_synthesis/artifacts/qa_vnext_finqa_final_recovery/e1_ef_br_2rep_20260908"
DESIGN = "trusted_data_synthesis/docs/finance_qa_vnext_finqa_e1_final_recovery.md"
TEST = "trusted_data_synthesis/tests/test_qa_vnext_finqa_e1_final_recovery.py"
AUDIT_SHA256 = "e097dff61478af07cd4ebde83767afd1d99ffd404a8c06230fc9445a5b21a9fe"
LABELS = (
    "E1_E_B_01",
    "E1_E_R_01",
    "E1_F_B_01",
    "E1_F_R_01",
    "E1_F_R_02",
    "E1_F_B_02",
    "E1_E_R_02",
    "E1_E_B_02",
)


class Config(TransportConfig):
    maximum_pilot_attempts: Literal[256] = 256


def configuration():
    return Config(system_prompt=SYSTEM)


def history_guard(root):
    paths = [
        "trusted_data_synthesis/artifacts",
        ":(exclude)trusted_data_synthesis/artifacts/qa_vnext_finqa_final_recovery",
        "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_finqa_difficulty",
        "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_finqa_reference_diagnostic",
        "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_harness_responsibility",
        "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_harness_transfer",
        "trusted_data_synthesis/tests/test_qa_vnext_finqa_difficulty.py",
        "trusted_data_synthesis/tests/test_qa_vnext_finqa_update_reference_revision.py",
        "trusted_data_synthesis/tests/test_qa_vnext_finqa_reference_diagnostic.py",
        "trusted_data_synthesis/docs/finance_qa_vnext_finqa_reference_diagnostic.md",
        "trusted_data_synthesis/scripts/finqa_v21_closeout.py",
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
        "historical_files_unchanged": True,
        "historical_controls_rerun": False,
    }


def registrations():
    rows = []
    for ordinal, label in enumerate(LABELS, 1):
        key, h, feedback, replicate = label.split("_")
        rows.append(
            record(
                "e1_recovery_registration",
                label=label,
                ordinal=ordinal,
                task_key=key,
                task_id=SPECS[key][1],
                condition=h,
                feedback_condition=feedback,
                replicate=int(replicate),
                runtime_version=VERSION,
                presentation_version=PRESENTATION_VERSION,
                fresh_session=True,
                maximum_actions=12,
                maximum_submissions=32,
                maximum_provider_attempts=32,
            )
        )
    return rows


def prepare(root):
    output = root / OUTPUT
    require(not output.exists(), "stage.preparation_exists")
    implementation = source_snapshot(root)
    panel, config = Panel(root), configuration()
    old = root / OLD_OUTPUT
    previous_preparation, previous_closeout = (
        manifest(old / "preparation"),
        manifest(old / "closeout"),
    )
    require(panel.bindings() == read(old / "preparation/bindings.json"), "stage.same_bindings")
    old_config, new_config = read(old / "preparation/configuration.json"), config.as_record()
    ignored = {"id", "maximum_pilot_attempts", "maximum_pilot_reserved_tokens"}
    require(
        {k: v for k, v in old_config.items() if k not in ignored}
        == {k: v for k, v in new_config.items() if k not in ignored},
        "stage.same_model_except_population_cap",
    )
    store = DurableStore(output / "preparation")
    store.json("implementation.json", implementation)
    store.json("history_guard.json", history_guard(root))
    store.json("bindings.json", panel.bindings())
    store.json("configuration.json", new_config)
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
            "only_new_feedback_and_measurement_controls": True,
        },
    )
    require(check.returncode == 0, "stage.new_controls_failed")
    rows, checks = registrations(), []
    for registration in rows:
        h, feedback, sid = (
            registration["condition"],
            registration["feedback_condition"],
            registration["id"],
        )
        runtime = FinalRecoveryRuntime(panel, "E1", h, sid, feedback_condition=feedback)
        initial = runtime.request()
        require(
            initial == ReferenceExplicitRuntime(panel, "E1", h, sid).request(),
            "stage.identical_pretrigger_v21",
        )
        require(
            not initial["state"]["claims"] and initial["state"]["pending_observation"] is None,
            "stage.fresh_empty_state",
        )
        old_request = read(old / f"preparation/initial_requests/E1_{h}_v21_01.json")
        require(initial["context"] == old_request["context"], "stage.identical_E_F_context")
        no_plan(initial)
        verify_public_reference(initial)
        require(not verify_feedback(initial, feedback), "stage.no_initial_review")
        store.json(f"initial_requests/{registration['label']}.json", initial)
        checks.append(
            {
                "label": registration["label"],
                "context_equals_v21": True,
                "initial_request_equals_v21_for_same_session_id": True,
                "initial_http_body_bytes": render_http_request(
                    initial, config, session_id=sid, attempt_index=0
                )["body_byte_count"],
            }
        )
    condition = record(
        "e1_recovery_condition",
        version=PRESENTATION_VERSION,
        underlying_runtime_version=VERSION,
        audit_sha256=AUDIT_SHA256,
        source_commit=implementation["source_commit"],
        model_configuration_id=new_config["id"],
        labels=list(LABELS),
        registered_sessions=8,
        denominator_per_information_feedback_cell=2,
        denominator_per_feedback=4,
        maximum_parallel_sessions=8,
        dispatch_order=list(LABELS),
        actual_http_start_order="concurrent; not claimed deterministic",
        waves=[list(LABELS)],
        maximum_provider_attempts=256,
        maximum_reserved_tokens=27525120,
        actions_per_session=12,
        submissions_per_session=32,
        attempts_per_session=32,
        feedback_trigger={
            "condition": "R",
            "current_feedback_equals": TARGET_ERROR,
            "text": REVIEW_TEXT,
            "persistence": (
                "only the request(s) whose current feedback is target_not_established; "
                "cleared by other feedback/success"
            ),
        },
        executable_runtime="FinalRecoveryRuntime",
        readonly_replay_runtime="FinalRecoveryRuntime",
        changes_only_public_request_presentation=True,
        original_v21_transition_inherited=True,
        task_oracle_read_to_construct_feedback=False,
        automatic_action_or_claim_repair=False,
        no_forced_action_or_prohibited_repeat_final=True,
        no_old_claim_deletion=True,
        measurement_definition="frozen metrics.recovery_trace source and design_at_freeze.md",
        no_target_rejection_recovery_status="NOT_APPLICABLE; full-success denominator retained",
        old_outcomes_inherited=0,
        historical_controls_rerun=False,
        automatic_retries=0,
        fallbacks=0,
        replacements=0,
        resume=False,
        no_expansion_to_obtain_trigger_or_success=True,
        development_diagnostic_not_blindtest=True,
        no_stable_success_probability_or_general_financial_effect_claim=True,
        student_updates=0,
        vtdo_updates=0,
        new_tokenizer_export=False,
    )
    store.json("condition.json", condition)
    store.json("registrations.json", rows)
    store.json("public_equivalence_checks.json", checks)
    store.json(
        "prior_evidence.json",
        {
            "old_output": OLD_OUTPUT,
            "preparation_manifest_id": previous_preparation["id"],
            "closeout_manifest_id": previous_closeout["id"],
            "old_results_are_not_new_controls": True,
            "no_prior_panel_or_static_witnesses_reexecuted": True,
        },
    )
    seal_directory(store, kind="e1_recovery_preparation_manifest", condition_id=condition["id"])
    return condition


def run_one(panel, registration, output, config, api_key, *, sender=None):
    child = DurableStore(output / registration["label"])
    child.json("registration.json", registration)
    callback = OnlineModelCallback(
        config,
        session_id=registration["id"],
        evidence_directory=child.root / "transport",
        api_key=api_key,
        sender=sender,
    )
    runtime = FinalRecoveryRuntime(
        panel,
        registration["task_key"],
        registration["condition"],
        registration["id"],
        callback,
        child.root / "runtime",
        feedback_condition=registration["feedback_condition"],
    )
    try:
        runtime.run()
    finally:
        callback.finalize()
    result = verify_session(panel, registration, child.root, model_required=sender is None)
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
    output, config = root / OUTPUT, configuration()
    prep = output / "preparation"
    manifest(prep)
    condition = read(prep / "condition.json")
    rows = read(prep / "registrations.json")
    require(
        condition["labels"] == list(LABELS) and rows == registrations(), "stage.fixed_population"
    )
    frozen = read(prep / "implementation.json")
    verify_source_snapshot(root, frozen)
    require(read(prep / "configuration.json") == config.as_record(), "stage.frozen_configuration")
    require(read(prep / "history_guard.json") == history_guard(root), "stage.history_guard")
    store = DurableStore(output / "online")
    store.json(
        "launch.json",
        record("e1_recovery_launch", condition_id=condition["id"], registered_sessions=8),
    )
    panel = Panel(root)
    require(panel.bindings() == read(prep / "bindings.json"), "stage.frozen_bindings")
    api_key = _credential(root / "trusted_data_synthesis/.env")
    results = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        pending = {
            pool.submit(run_one, panel, row, store.root / "sessions", config, api_key): row
            for row in rows
        }
        for future in as_completed(pending):
            registration = pending[future]
            try:
                result = future.result()
            except Exception as exc:
                result = record(
                    "e1_session_failure",
                    label=registration["label"],
                    task_key="E1",
                    condition=registration["condition"],
                    feedback_condition=registration["feedback_condition"],
                    replicate=registration["replicate"],
                    denominator=1,
                    complete_valid=False,
                    status="unknown_integrity_or_host_failure",
                    error_type=type(exc).__name__,
                )
                store.json("failures/" + registration["label"] + ".json", result)
            results[registration["label"]] = result
            print(
                registration["label"],
                result["status"],
                "submissions",
                result.get("submissions"),
                "attempts",
                result.get("provider_attempts"),
                flush=True,
            )
    ordered = [results[label] for label in LABELS]
    total = aggregate(ordered)
    require(
        total["provider_attempts"] is None or total["provider_attempts"] <= 256,
        "stage.global_attempt_cap",
    )
    summary = record(
        "e1_recovery_summary",
        condition_id=condition["id"],
        sessions=ordered,
        registered_denominator=8,
        total=total,
        by_cell={
            h + "_" + b: aggregate(
                [r for r in ordered if r["condition"] == h and r["feedback_condition"] == b]
            )
            for h in ("E", "F")
            for b in ("B", "R")
        },
        by_feedback={
            b: aggregate([r for r in ordered if r["feedback_condition"] == b]) for b in ("B", "R")
        },
        integrity_or_condition_failure=any(
            r.get("condition_flags") or "recovery_trace" not in r for r in ordered
        ),
        no_retries_replacements_or_expansion=True,
    )
    store.json("summary.json", summary)
    verify_source_snapshot(root, frozen)
    seal_directory(
        store,
        kind="e1_recovery_online_manifest",
        condition_id=condition["id"],
        summary_id=summary["id"],
    )
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["prepare", "run"])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    result = (prepare if args.command == "prepare" else run)(args.root)
    print(result["id"], flush=True)


if __name__ == "__main__":
    main()
