"""Freeze and execute eight fresh E1/J2 fixed-E V0/V1 sessions."""

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
    verify_feedback,
)
from trusted_synthesis.experiments.finance_qa_vnext_finqa_reason_policy.runtime import (
    ReasonPolicyRuntime,
    verify_reason_policy,
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
from .runtime import VERSION, VIEW_KEY, ReadableBindingRuntime, verify_binding_view

PARENT = "d43b5eb803ee07558dee309eee018fb0046d5811"
OLD_OUTPUT = "trusted_data_synthesis/artifacts/qa_vnext_finqa_reason_policy/e1_ef_cp_2rep_20260908"
OLD_J2_INITIAL = (
    "trusted_data_synthesis/artifacts/qa_vnext_finqa_reference_diagnostic/"
    "original_12_ef_v21_20260908/preparation/initial_requests/J2_E_v21_01.json"
)
OUTPUT = "trusted_data_synthesis/artifacts/qa_vnext_finqa_binding_view/e1_j2_e_v0v1_2rep_20260908"
DESIGN = "trusted_data_synthesis/docs/finance_qa_vnext_finqa_readable_bindings.md"
TEST = "trusted_data_synthesis/tests/test_qa_vnext_finqa_readable_bindings.py"
AUDIT_SHA256 = "750b32660ad13629190146a86b22112e1e4906d850d753d1962dc9b97d338eea"
LABELS = (
    "E1_E_V0_01",
    "E1_E_V1_01",
    "J2_E_V0_01",
    "J2_E_V1_01",
    "J2_E_V1_02",
    "J2_E_V0_02",
    "E1_E_V1_02",
    "E1_E_V0_02",
)
INTENT_RUBRIC = {
    "population": (
        "every valid unambiguous JSON object with kind=action; malformed JSON is not promoted"
    ),
    "labels": ["MATCH", "MISMATCH", "UNDETERMINABLE"],
    "evidence": (
        "exact quotations from original reason/subgoal; compare explicit current-step "
        "objects, ordered inputs, values and source identities"
    ),
    "MATCH": (
        "sufficiently specific current-step intent agrees with the actual selected "
        "objects/order; this does not certify the financial method"
    ),
    "MISMATCH": (
        "a clear current-step assertion about operation, object, value, order or source "
        "period contradicts the original selected inputs/source records"
    ),
    "UNDETERMINABLE": (
        "vague intent, unresolved object reference, or competing plans without an "
        "identifiable current-step choice"
    ),
    "multistep_plans": "do not require every future step to be performed in the current Action",
    "cross_period_products": (
        "not automatically errors; explicitly stated source identities and full target "
        "dependencies determine interpretation"
    ),
    "review": (
        "posthoc human descriptive, not blinded; do not infer private reasoning or a "
        "unique causal source"
    ),
    "report": (
        "all raw shapes and actually executed subsets separately; unknown labels stay "
        "in full accounting"
    ),
}


class Config(TransportConfig):
    maximum_pilot_attempts: Literal[256] = 256


def configuration():
    return Config(system_prompt=SYSTEM)


def history_guard(root):
    paths = [
        "trusted_data_synthesis/src",
        ":(exclude)trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_finqa_binding_view",
        "trusted_data_synthesis/artifacts",
        ":(exclude)trusted_data_synthesis/artifacts/qa_vnext_finqa_binding_view",
        "trusted_data_synthesis/tests",
        ":(exclude)trusted_data_synthesis/tests/test_qa_vnext_finqa_readable_bindings.py",
        "trusted_data_synthesis/docs",
        ":(exclude)trusted_data_synthesis/docs/finance_qa_vnext_finqa_readable_bindings.md",
        "trusted_data_synthesis/scripts",
        "trusted_data_synthesis/benchmarks",
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
        key, information, view, replicate = label.split("_")
        rows.append(
            record(
                "binding_view_registration",
                label=label,
                ordinal=ordinal,
                task_key=key,
                task_id=SPECS[key][1],
                condition=information,
                view_condition=view,
                replicate=int(replicate),
                expression_condition="P",
                feedback_condition="R",
                runtime_version="finqa_source_numeric_h2.v2.2.reason_policy",
                presentation_version=VERSION,
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
    previous = {name: manifest(old / name)["id"] for name in ("preparation", "online", "closeout")}
    require(
        panel.bindings() == read(old / "preparation/bindings.json"),
        "stage.same_frozen_task_bindings",
    )
    require(
        config.as_record() == read(old / "preparation/configuration.json"),
        "stage.same_model_and_budgets",
    )
    store = DurableStore(output / "preparation")
    store.json("implementation.json", implementation)
    store.json("history_guard.json", history_guard(root))
    store.json("bindings.json", panel.bindings())
    store.json("configuration.json", config.as_record())
    store.json("intent_review_rubric.json", INTENT_RUBRIC)
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
            "only_new_display_two_task_wiring_and_measurement_controls": True,
        },
    )
    require(check.returncode == 0, "stage.new_controls_failed")
    rows, checks = registrations(), []
    for r in rows:
        key, sid, view = r["task_key"], r["id"], r["view_condition"]
        runtime = ReadableBindingRuntime(panel, key, "E", sid, view_condition=view)
        request = runtime.request()
        baseline = ReasonPolicyRuntime(panel, key, "E", sid, expression_condition="P").request()
        if view == "V0":
            require(request == baseline, "stage.V0_exact_P")
        else:
            require(
                {k: v for k, v in request.items() if k not in {"id", VIEW_KEY}}
                == {k: v for k, v in baseline.items() if k != "id"},
                "stage.only_additive_view",
            )
            require(request[VIEW_KEY]["results"] == [], "stage.no_initial_results")
        prior_initial = (
            read(old / "preparation/initial_requests/E1_E_P_01.json")
            if key == "E1"
            else read(root / OLD_J2_INITIAL)
        )
        require(request["context"] == prior_initial["context"], "stage.original_task_E_context")
        require(
            not request["state"]["claims"] and request["state"]["pending_observation"] is None,
            "stage.fresh_empty_state",
        )
        verify_public_reference(request)
        verify_reason_policy(request, "P")
        verify_binding_view(request, [], view)
        require(not verify_feedback(request, "R"), "stage.no_initial_target_review")
        no_plan(request)
        store.json(f"initial_requests/{r['label']}.json", request)
        checks.append(
            {
                "label": r["label"],
                "original_context_unchanged": True,
                "P_schema_tools_and_rules_unchanged": True,
                "initial_http_body_bytes": render_http_request(
                    request, config, session_id=sid, attempt_index=0
                )["body_byte_count"],
            }
        )
    condition = record(
        "binding_view_condition",
        version=VERSION,
        audit_sha256=AUDIT_SHA256,
        source_commit=implementation["source_commit"],
        model_configuration_id=config.as_record()["id"],
        labels=list(LABELS),
        registered_sessions=8,
        information_condition="E",
        tasks=["E1", "J2"],
        denominator_per_task_view=2,
        denominator_per_view=4,
        task_weights_per_view={"E1": 0.5, "J2": 0.5},
        fixed_expression_condition="P",
        fixed_feedback_condition="R",
        dispatch_order=list(LABELS),
        waves=[list(LABELS)],
        maximum_parallel_sessions=8,
        actual_http_start_order="concurrent; not claimed deterministic",
        maximum_provider_attempts=256,
        maximum_reserved_tokens=27525120,
        actions_per_session=12,
        submissions_per_session=32,
        attempts_per_session=32,
        view_definition={
            "V0": "unchanged P request",
            "V1": (
                "all accepted results with original IDs, values, original source fragments, "
                "actual ordered inputs and values, and explicit acceptance records"
            ),
            "construction_inputs": [
                "current public Context and Claims",
                "previously public admitted Observation/Update records",
            ],
            "ordering": (
                "original acceptance order; no numeric merge, sorting by value, financial "
                "rank, or failed-Final filtering"
            ),
            "task_oracle_or_model_reason_read": False,
            "source_or_derived_units_inferred": False,
            "actual_input_language_changed": False,
            "pure_cosmetic_or_equal_current_request_information_claim": False,
        },
        feedback_trigger={
            "current_feedback_equals": TARGET_ERROR,
            "text": REVIEW_TEXT,
            "persistence": "current error only; same clearing as previous R",
        },
        executable_runtime="ReadableBindingRuntime",
        readonly_replay_runtime="ReadableBindingRuntime",
        original_P_transition_and_parser_inherited=True,
        no_global_monkeypatch=True,
        no_forced_action_or_prohibited_repeat_final=True,
        no_claim_deletion_or_host_repair=True,
        method_diagnostics=(
            "separate frozen E1 scale and J2 annual-term/full-difference probes; "
            "not an admission route"
        ),
        intent_rubric=INTENT_RUBRIC,
        no_target_rejection_recovery_status="NOT_APPLICABLE; full denominator retained",
        old_outcomes_inherited=0,
        historical_controls_rerun=False,
        automatic_retries=0,
        fallbacks=0,
        replacements=0,
        resume=False,
        no_expansion_to_obtain_trigger_or_success=True,
        development_diagnostic_not_blindtest=True,
        no_pure_layout_element_causal_claim=True,
        no_general_financial_or_training_benefit_claim=True,
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
            "previous_CP_output": OLD_OUTPUT,
            "previous_manifest_ids": previous,
            "old_results_are_not_new_controls": True,
            "J2_is_existing_inspected_development_task": True,
            "historical_controls_reexecuted": False,
        },
    )
    seal_directory(store, kind="binding_view_preparation_manifest", condition_id=condition["id"])
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
    runtime = ReadableBindingRuntime(
        panel,
        registration["task_key"],
        registration["condition"],
        registration["id"],
        callback,
        child.root / "runtime",
        view_condition=registration["view_condition"],
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
        "by_task_view": {
            key + "_" + view: aggregate(
                [r for r in ordered if r["task_key"] == key and r["view_condition"] == view]
            )
            for key in ("E1", "J2")
            for view in ("V0", "V1")
        },
        "by_view": {
            view: aggregate([r for r in ordered if r["view_condition"] == view])
            for view in ("V0", "V1")
        },
    }


def run(root):
    output, config = root / OUTPUT, configuration()
    prep = output / "preparation"
    manifest(prep)
    condition, rows = read(prep / "condition.json"), read(prep / "registrations.json")
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
        record("binding_view_launch", condition_id=condition["id"], registered_sessions=8),
    )
    panel = Panel(root)
    require(panel.bindings() == read(prep / "bindings.json"), "stage.frozen_bindings")
    api_key = _credential(root / "trusted_data_synthesis/.env")
    results = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        pending = {
            pool.submit(run_one, panel, r, store.root / "sessions", config, api_key): r
            for r in rows
        }
        for future in as_completed(pending):
            registration = pending[future]
            try:
                result = future.result()
            except Exception as exc:
                result = record(
                    "binding_view_session_failure",
                    label=registration["label"],
                    task_key=registration["task_key"],
                    condition="E",
                    view_condition=registration["view_condition"],
                    expression_condition="P",
                    feedback_condition="R",
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
        "binding_view_summary",
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
        kind="binding_view_online_manifest",
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
