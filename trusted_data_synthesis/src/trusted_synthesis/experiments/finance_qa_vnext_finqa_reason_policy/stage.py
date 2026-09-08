"""Preregister and execute eight fresh E1 C/P sessions, with fixed R feedback."""

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
from trusted_synthesis.experiments.finance_qa_vnext_finqa_final_recovery.runtime import (
    REVIEW_TEXT,
    TARGET_ERROR,
    FinalRecoveryRuntime,
    verify_feedback,
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
    P_PROTOCOL_VERSION,
    P_REASON_RULE,
    VERSION,
    ReasonPolicyRuntime,
    verify_reason_policy,
)

PARENT = "dbf0afb97dfacac8ceab86139844ecc4079db1e3"
OLD_OUTPUT = "trusted_data_synthesis/artifacts/qa_vnext_finqa_final_recovery/e1_ef_br_2rep_20260908"
OUTPUT = "trusted_data_synthesis/artifacts/qa_vnext_finqa_reason_policy/e1_ef_cp_2rep_20260908"
DESIGN = "trusted_data_synthesis/docs/finance_qa_vnext_finqa_e1_reason_policy.md"
TEST = "trusted_data_synthesis/tests/test_qa_vnext_finqa_e1_reason_policy.py"
AUDIT_SHA256 = "daee008f6a978e4100d5a97380d5b396a77743999ab2ccb1b6e1747a37067c06"
LABELS = (
    "E1_E_C_01",
    "E1_E_P_01",
    "E1_F_C_01",
    "E1_F_P_01",
    "E1_F_P_02",
    "E1_F_C_02",
    "E1_E_P_02",
    "E1_E_C_02",
)


class Config(TransportConfig):
    maximum_pilot_attempts: Literal[256] = 256


def configuration():
    return Config(system_prompt=SYSTEM)


def history_guard(root):
    paths = [
        "trusted_data_synthesis/artifacts",
        ":(exclude)trusted_data_synthesis/artifacts/qa_vnext_finqa_reason_policy",
        "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_finqa_difficulty",
        "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_finqa_reference_diagnostic",
        "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_harness_responsibility",
        "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_harness_transfer",
        "trusted_data_synthesis/tests/test_qa_vnext_finqa_difficulty.py",
        "trusted_data_synthesis/tests/test_qa_vnext_finqa_update_reference_revision.py",
        "trusted_data_synthesis/tests/test_qa_vnext_finqa_reference_diagnostic.py",
        "trusted_data_synthesis/docs/finance_qa_vnext_finqa_reference_diagnostic.md",
        "trusted_data_synthesis/scripts/finqa_v21_closeout.py",
        "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_finqa_final_recovery",
        "trusted_data_synthesis/docs/finance_qa_vnext_finqa_e1_final_recovery.md",
        "trusted_data_synthesis/tests/test_qa_vnext_finqa_e1_final_recovery.py",
        "trusted_data_synthesis/scripts/finqa_e1_recovery_posthoc.py",
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
        key, h, policy, replicate = label.split("_")
        rows.append(
            record(
                "e1_reason_policy_registration",
                label=label,
                ordinal=ordinal,
                task_key=key,
                task_id=SPECS[key][1],
                condition=h,
                feedback_condition="R",
                expression_condition=policy,
                replicate=int(replicate),
                runtime_version=P_PROTOCOL_VERSION
                if policy == "P"
                else "finqa_source_numeric_h2.v2.1",
                expression_contract_version=VERSION,
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
    require(old_config == new_config, "stage.same_model_and_population_cap")
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
            "only_new_reason_contract_and_layered_measurement_controls": True,
        },
    )
    require(check.returncode == 0, "stage.new_controls_failed")
    rows, checks = registrations(), []
    for registration in rows:
        h, policy, sid = (
            registration["condition"],
            registration["expression_condition"],
            registration["id"],
        )
        runtime = ReasonPolicyRuntime(panel, "E1", h, sid, expression_condition=policy)
        initial = runtime.request()
        previous_same_id = FinalRecoveryRuntime(
            panel, "E1", h, sid, feedback_condition="R"
        ).request()
        if policy == "C":
            require(initial == previous_same_id, "stage.C_same_as_previous_R")
        else:
            require(initial["context"] == previous_same_id["context"], "stage.P_same_context")
            action = json.loads(json.dumps(initial["response_schemas"]["action"]))
            action["properties"]["reason"]["maxLength"] = 480
            require(
                action == previous_same_id["response_schemas"]["action"],
                "stage.only_reason_schema_delta",
            )
            for kind in ("update", "final"):
                require(
                    initial["response_schemas"][kind] == previous_same_id["response_schemas"][kind],
                    "stage.unchanged_update_final_schema",
                )
            require(
                {k: v for k, v in initial["rules"].items() if k != "reason_limit"}
                == {k: v for k, v in previous_same_id["rules"].items() if k != "reason_limit"},
                "stage.other_rules_unchanged",
            )
        verify_reason_policy(initial, policy)
        require(
            not initial["state"]["claims"] and initial["state"]["pending_observation"] is None,
            "stage.fresh_empty_state",
        )
        old_request = read(old / f"preparation/initial_requests/E1_{h}_R_01.json")
        require(initial["context"] == old_request["context"], "stage.identical_E_F_context")
        no_plan(initial)
        verify_public_reference(initial)
        require(not verify_feedback(initial, "R"), "stage.no_initial_review")
        store.json(f"initial_requests/{registration['label']}.json", initial)
        checks.append(
            {
                "label": registration["label"],
                "context_equals_previous_R": True,
                "reason_contract_only_public_delta": True,
                "initial_http_body_bytes": render_http_request(
                    initial, config, session_id=sid, attempt_index=0
                )["body_byte_count"],
            }
        )
    condition = record(
        "e1_reason_policy_condition",
        version=VERSION,
        runtime_versions={"C": "finqa_source_numeric_h2.v2.1", "P": P_PROTOCOL_VERSION},
        audit_sha256=AUDIT_SHA256,
        source_commit=implementation["source_commit"],
        model_configuration_id=new_config["id"],
        labels=list(LABELS),
        registered_sessions=8,
        denominator_per_information_expression_cell=2,
        denominator_per_expression_condition=4,
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
        executable_runtime="ReasonPolicyRuntime",
        readonly_replay_runtime="ReasonPolicyRuntime",
        actual_parser="reason_policy.runtime.parse(raw, expression_condition)",
        no_global_parser_monkeypatch=True,
        original_transition_body_only_parser_seam_changed=True,
        action_reason_policy={
            "C": {"minLength": 1, "maxLength": 480},
            "P": {"minLength": 1, "no_local_maxLength": True, "public_rule": P_REASON_RULE},
        },
        fixed_R_text_and_trigger_clearing=True,
        contract_differs_from_first_request=True,
        not_same_error_state_recovery_intervention=True,
        task_oracle_read_to_construct_feedback=False,
        automatic_action_or_claim_repair=False,
        no_forced_action_or_prohibited_repeat_final=True,
        no_old_claim_deletion=True,
        measurement_definition=(
            "frozen metrics.action_layers and recovery_trace; raw JSON -> schema -> "
            "admission -> Observation -> acceptance -> actual consumption"
        ),
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
    seal_directory(
        store, kind="e1_reason_policy_preparation_manifest", condition_id=condition["id"]
    )
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
    runtime = ReasonPolicyRuntime(
        panel,
        registration["task_key"],
        registration["condition"],
        registration["id"],
        callback,
        child.root / "runtime",
        expression_condition=registration["expression_condition"],
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


def summarize_groups(ordered):
    require([r["label"] for r in ordered] == list(LABELS), "stage.group_population")
    return {
        "by_cell": {
            h + "_" + policy: aggregate(
                [r for r in ordered if r["condition"] == h and r["expression_condition"] == policy]
            )
            for h in ("E", "F")
            for policy in ("C", "P")
        },
        "by_policy": {
            policy: aggregate([r for r in ordered if r["expression_condition"] == policy])
            for policy in ("C", "P")
        },
    }


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
        record("e1_reason_policy_launch", condition_id=condition["id"], registered_sessions=8),
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
                    feedback_condition="R",
                    expression_condition=registration["expression_condition"],
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
        "e1_reason_policy_summary",
        condition_id=condition["id"],
        sessions=ordered,
        registered_denominator=8,
        total=total,
        **summarize_groups(ordered),
        integrity_or_condition_failure=any(
            r.get("condition_flags") or "recovery_trace" not in r for r in ordered
        ),
        no_retries_replacements_or_expansion=True,
    )
    store.json("summary.json", summary)
    verify_source_snapshot(root, frozen)
    seal_directory(
        store,
        kind="e1_reason_policy_online_manifest",
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
