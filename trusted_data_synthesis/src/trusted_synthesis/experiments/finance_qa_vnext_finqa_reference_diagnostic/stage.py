"""Fresh v2.1 fixed-panel diagnostic; explicit execution and replay wiring."""

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
from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.panel import SPECS, Panel
from trusted_synthesis.experiments.finance_qa_vnext_finqa_difficulty.reference_revision import (
    VERSION,
    ReferenceExplicitRuntime,
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
from .metrics import aggregate_observations, verify_public_reference

PARENT = "04026165aedab7b68590393817026cafaa31069c"
OLD_OUTPUT = "trusted_data_synthesis/artifacts/qa_vnext_finqa_difficulty/original_12_ef_v1_20260908"
OUTPUT = (
    "trusted_data_synthesis/artifacts/qa_vnext_finqa_reference_diagnostic/"
    "original_12_ef_v21_20260908"
)
DESIGN = "trusted_data_synthesis/docs/finance_qa_vnext_finqa_reference_diagnostic.md"
TEST = "trusted_data_synthesis/tests/test_qa_vnext_finqa_reference_diagnostic.py"
AUDIT_SHA256 = "f96b9cb41be695c8892d10580aaa023bd5d08d79d5300844d5dc84086d909d7b"
LABELS = tuple(f"{key}_{h}_v21_01" for key in SPECS for h in ("E", "F"))


class Config(TransportConfig):
    maximum_pilot_attempts: Literal[768] = 768


def configuration():
    return Config(system_prompt=SYSTEM)


def history_guard(root):
    paths = [
        "trusted_data_synthesis/artifacts",
        ":(exclude)trusted_data_synthesis/artifacts/qa_vnext_finqa_reference_diagnostic",
        "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_finqa_difficulty",
        "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_harness_responsibility",
        "trusted_data_synthesis/src/trusted_synthesis/experiments/finance_qa_vnext_harness_transfer",
        "trusted_data_synthesis/tests/test_qa_vnext_finqa_difficulty.py",
        "trusted_data_synthesis/tests/test_qa_vnext_finqa_update_reference_revision.py",
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
        "previous_stages_unchanged": True,
        "census_and_historical_controls_rerun": False,
    }


def prepare(root):
    output = root / OUTPUT
    require(not output.exists(), "stage.preparation_exists")
    implementation = source_snapshot(root)
    panel, config = Panel(root), configuration()
    old = root / OLD_OUTPUT
    old_preparation = manifest(old / "preparation")
    old_closeout = manifest(old / "closeout")
    require(panel.bindings() == read(old / "preparation/bindings.json"), "stage.same_bindings")
    require(config.as_record() == read(old / "preparation/configuration.json"), "stage.same_model")
    revision = read(old / "closeout/reference_revision.json")
    require(
        revision["version"] == VERSION
        and revision["provider_calls"] == 0
        and len(revision["offline_capacities"]) == 24
        and all(r["complete"] for r in revision["offline_capacities"]),
        "stage.prior_v21_static_evidence",
    )
    store = DurableStore(output / "preparation")
    store.json("implementation.json", implementation)
    store.json("history_guard.json", history_guard(root))
    store.json("bindings.json", panel.bindings())
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
            "only_new_wiring_and_measurement_controls": True,
        },
    )
    require(check.returncode == 0, "stage.new_wiring_controls_failed")
    registrations, public_checks = [], []
    old_ids = {r["id"] for r in read(old / "preparation/registrations.json")}
    for ordinal, label in enumerate(LABELS, 1):
        key, h, *_ = label.split("_")
        registration = record(
            "finqa_v21_registration",
            label=label,
            ordinal=ordinal,
            task_key=key,
            stratum=SPECS[key][0],
            condition=h,
            task_id=SPECS[key][1],
            runtime_version=VERSION,
            fresh_session=True,
            maximum_actions=12,
            maximum_submissions=32,
            maximum_provider_attempts=32,
            information_condition_only_varies_within_pair=True,
        )
        require(registration["id"] not in old_ids, "stage.fresh_identity")
        registrations.append(registration)
        runtime = ReferenceExplicitRuntime(panel, key, h, registration["id"])
        initial = runtime.request()
        no_plan(initial)
        verify_public_reference(initial)
        previous = read(old / f"preparation/initial_requests/{key}_{h}_01.json")
        require(initial["context"] == previous["context"], "stage.identical_public_context")
        for kind in ("action", "final"):
            require(
                initial["response_schemas"][kind] == previous["response_schemas"][kind],
                "stage.identical_nonupdate_schema",
            )
        store.json(f"initial_requests/{label}.json", initial)
        public_checks.append(
            {
                "label": label,
                "context_id": initial["context"]["id"],
                "context_equals_original": True,
                "nonupdate_schemas_equal_original": True,
                "initial_http_body_bytes": render_http_request(
                    initial,
                    config,
                    session_id=registration["id"],
                    attempt_index=0,
                )["body_byte_count"],
            }
        )
    condition = record(
        "finqa_v21_condition",
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
        old_complete_results_inherited=0,
        only_primary_runtime_change="existing v2.1 exact public Update reference contract",
        executable_runtime="ReferenceExplicitRuntime",
        readonly_replay_runtime="ReferenceExplicitRuntime",
        static_v21_witnesses_reused_not_reexecuted=True,
        development_diagnostic_not_blindtest=True,
        E_F_are_information_condition_packages_not_pure_retrieval=True,
        no_contemporaneous_v2_control=True,
        no_exact_causal_effect_claim=True,
        no_stable_success_probability_or_generalization_claim=True,
        no_reference_only_live_calibration=True,
        observation_measurement={
            "first_decision": "first subsequent actual model submission while pending",
            "legal": "admitted exact-ID Update with either accept or reject",
            "absent_decision": "null; retained in total Observation and session denominators",
            "rate_denominator": "observations with first subsequent actual model submission",
            "reference_runs": "consecutive actual submission indices with observation_binding",
            "events_not_independent_tasks": True,
        },
        financial_measurement={
            "focus": ["E1", "M3", "J1", "J2"],
            "opportunity_definition": "frozen metrics.financial_trace source",
            "no_inspectable_operation": "NOT_REACHED, not ability error",
            "intermediate_arithmetic_not_automatically_final_answer": True,
            "review": "posthoc evidence-linked descriptive; inputs, error, recovery, termination",
            "off_reference_source_ids": "review clue only",
        },
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
    store.json("public_equivalence_checks.json", public_checks)
    store.json(
        "prior_evidence.json",
        {
            "old_output": OLD_OUTPUT,
            "preparation_manifest_id": old_preparation["id"],
            "closeout_manifest_id": old_closeout["id"],
            "v21_static_capacities": revision["offline_capacities"],
            "full_census_recomputed": False,
            "historical_67_controls_rerun": False,
            "old_online_E_complete": 2,
            "old_online_F_complete": 7,
            "old_denominator_per_condition": 12,
            "old_outcomes_not_new_samples": True,
        },
    )
    seal_directory(store, kind="finqa_v21_preparation_manifest", condition_id=condition["id"])
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
    runtime = ReferenceExplicitRuntime(
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
        total["observation_diagnostics"] = (
            aggregate_observations(
                [event for r in selected for event in r["observation_diagnostics"]["events"]]
            )
            if all("observation_diagnostics" in r for r in selected)
            else None
        )
        total["explicit_accepts"] = (
            sum(r["observation_diagnostics"]["summary"]["resolved_accept"] for r in selected)
            if all("observation_diagnostics" in r for r in selected)
            else None
        )
        total["explicit_rejects"] = (
            sum(r["observation_diagnostics"]["summary"]["resolved_reject"] for r in selected)
            if all("observation_diagnostics" in r for r in selected)
            else None
        )
        totals[h] = total
    summary = record(
        "finqa_v21_diagnostic_summary",
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
