"""Sixteen fixed fresh sessions; unchanged H1/H2 and separately exported targets."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Literal

from trusted_synthesis.canonical_json import canonical_json_bytes
from trusted_synthesis.domains.finance.qa_vnext.protocol import record, require
from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore
from trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.audit import (
    manifest,
    no_plan,
    qualify,
    read,
)
from trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.audit import (
    policy as measurement_policy,
)
from trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.runtime import (
    StudyRuntime,
)
from trusted_synthesis.experiments.finance_qa_vnext_harness_responsibility.stage import (
    SYSTEM,
    review,
)
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
from trusted_synthesis.experiments.qa_reasoning_share_training_preflight import (
    tokenization as assets,
)

from . import representation
from .panel import TASKS, Panel

PARENT = "bf602a421b27183f1281ca47fa1e29622786d112"
OUTPUT = (
    "trusted_data_synthesis/artifacts/qa_vnext_harness_transfer/h1_h2_four_instance_v1_20260907"
)
DESIGN = "trusted_data_synthesis/docs/finance_qa_vnext_h1_h2_cross_instance_transfer.md"
AUDIT = "2e5e4d720aefa236e6751470e8af5c2dc05985626a1da55ffa7bf351f73da008"
LABELS = tuple(
    f"{task}_{condition}_{wave:02d}"
    for wave in (1, 2)
    for task in TASKS
    for condition in ("H1", "H2")
)


class TransferConfig(TransportConfig):
    maximum_pilot_attempts: Literal[512] = 512


def configuration():
    return TransferConfig(system_prompt=SYSTEM)


def history_guard(root):
    prefixes = [
        "trusted_data_synthesis/artifacts",
        ":(exclude)trusted_data_synthesis/artifacts/qa_vnext_harness_transfer",
    ]
    status = subprocess.check_output(["git", "status", "--porcelain", "--", *prefixes], cwd=root)
    changed = subprocess.check_output(
        ["git", "diff", "--name-only", PARENT, "--", *prefixes], cwd=root
    )
    require(not status and not changed, "transfer.historical_artifacts_changed")
    inherited = (
        "trusted_data_synthesis/src/trusted_synthesis/experiments/"
        "finance_qa_vnext_harness_responsibility"
    )
    require(
        not subprocess.check_output(
            ["git", "diff", "--name-only", PARENT, "--", inherited], cwd=root
        ),
        "transfer.inherited_harness_changed",
    )
    return {
        "parent_commit": PARENT,
        "historical_artifacts_unchanged": True,
        "previous_harness_source_unchanged": True,
        "historical_measurements_recomputed": False,
    }


def prepare(root):
    output = root / OUTPUT
    require(not output.exists(), "transfer.preparation_already_exists")
    implementation = source_snapshot(root)
    panel, config = Panel(root), configuration()
    store = DurableStore(output / "preparation")
    store.json("implementation.json", implementation)
    store.json("source_bindings.json", panel.bindings())
    store.json("history_guard.json", history_guard(root))
    store.json("configuration.json", config.as_record())
    store.json("measurement_policy.json", measurement_policy())
    binding = assets.register_tokenizer(root)
    rep_policy = representation.policy(binding)
    store.json("tokenizer_binding.json", binding)
    store.json("representation_policy.json", rep_policy)
    design = (root / DESIGN).read_bytes()
    store.write("design_at_freeze.md", design)
    test_path = "trusted_data_synthesis/tests/test_qa_vnext_harness_transfer.py"
    check = subprocess.run(
        [
            str(root / "trusted_data_synthesis/.venv/bin/python"),
            "-m",
            "pytest",
            "-q",
            "--tb=short",
            test_path,
        ],
        cwd=root,
        capture_output=True,
        check=False,
    )
    store.write("controls_stdout.txt", check.stdout)
    store.write("controls_stderr.txt", check.stderr)
    store.json(
        "controls.json",
        {
            "exit_code": check.returncode,
            "provider_calls": 0,
            "test_sha256": hashlib.sha256((root / test_path).read_bytes()).hexdigest(),
            "historical_tests_rerun": False,
            "population_samples": 0,
        },
    )
    require(check.returncode == 0, "transfer.new_binding_controls_failed")
    registrations = []
    for ordinal, label in enumerate(LABELS, 1):
        key, h, wave = label.split("_")
        base = panel.adapter(key)
        registrations.append(
            record(
                "transfer_registration",
                label=label,
                task_key=key,
                task_group=TASKS[key][0],
                condition=h,
                wave=int(wave),
                ordinal=ordinal,
                task_id=base.context["task_id"],
                base_context_id=base.context["id"],
                source_binding_id=base.context["source_binding"]["id"],
                model_configuration_id=config.as_record()["id"],
                fresh_session=True,
                maximum_actions=12,
                maximum_submissions=32,
                maximum_provider_attempts=32,
            )
        )
    condition = record(
        "transfer_condition",
        audit_sha256=AUDIT,
        source_commit=implementation["source_commit"],
        implementation_id=implementation["id"],
        task_keys=list(TASKS),
        labels=list(LABELS),
        source_bindings_id=record("transfer_sources", rows=panel.bindings())["id"],
        design_sha256=hashlib.sha256(design).hexdigest(),
        model_configuration_id=config.as_record()["id"],
        measurement_policy_id=measurement_policy()["id"],
        representation_policy_id=rep_policy["id"],
        waves=[list(LABELS[:8]), list(LABELS[8:])],
        maximum_parallel_sessions=8,
        registered_sessions=16,
        task_marginal_per_condition={h: {k: "1/4" for k in TASKS} for h in ("H1", "H2")},
        maximum_provider_attempts=512,
        maximum_reserved_tokens=512 * 107520,
        attempts_per_session=32,
        actions_per_session=12,
        H0_included=False,
        neutral_system_identical_to_predecessor=True,
        source_usage="known_source_instance_transfer_not_blindtest",
        HII_two_instances_share_one_source_document=True,
        prompts_or_tools_or_final_rules_modified=False,
        Share_binding_bridge="remove reference membership, "
        "preserve original semantic/source verification",
        automatic_retries=0,
        fallback=0,
        resume=False,
        replacements=0,
        success_stops_immediately=True,
        stop_next_wave_on_integrity_failure=True,
        negative_results_do_not_trigger_resampling=True,
        student_weights=0,
        student_forward=0,
        student_updates=0,
        vtdo_updates=0,
    )
    store.json("condition.json", condition)
    store.json("registrations.json", registrations)
    for key in TASKS:
        for h in ("H1", "H2"):
            callback = type(
                "NoCall", (), {"binding": record("callback_binding", origin="adapter_mock")}
            )()
            runtime = StudyRuntime(
                panel.adapter(key),
                TASKS[key][0],
                h,
                callback,
                output / "preparation/initial_views" / f"{key}_{h}",
            )
            request = runtime.request()
            http = render_http_request(
                request, config, session_id=f"initial_{key}_{h}", attempt_index=0
            )
            require(http["body_byte_count"] <= 98304, "transfer.initial_input_budget")
            if h == "H2":
                no_plan(json.loads(http["body"]["messages"][1]["content"]))
            store.json(f"initial_requests/{key}_{h}.json", request)
            store.write(f"initial_http/{key}_{h}.body", http["body_json"].encode())
    seal_directory(store, kind="transfer_preparation_manifest", condition_id=condition["id"])
    return condition


def run_one(panel, registration, child, config, key):
    task, h, group = registration["task_key"], registration["condition"], registration["task_group"]
    callback = OnlineModelCallback(
        config,
        session_id=registration["id"],
        evidence_directory=child.root / "transport",
        api_key=key,
    )
    StudyRuntime(panel.adapter(task), group, h, callback, child.root / "runtime").run()
    callback.finalize()
    q = qualify(panel.adapter(task), group, h, child.root, config)
    child.json("qualification.json", q)
    if q["status"] != "unknown":
        review(child, registration["label"], q)
    seal_directory(
        child,
        kind="transfer_session_manifest",
        registration_id=registration["id"],
        qualification_id=q["id"],
    )
    return q


def summarize(rows, registrations, condition):
    by_label = {r["label"]: r for r in registrations}
    cells = []
    for h in ("H1", "H2"):
        for task in TASKS:
            qs = [
                r["qualification"]
                for r in rows
                if by_label[r["label"]]["task_key"] == task
                and by_label[r["label"]]["condition"] == h
            ]
            require(len(qs) == 2, "transfer.fixed_cell_denominator")
            counts = Counter(q["status"] for q in qs)
            known = [q for q in qs if q["status"] != "unknown"]
            cells.append(
                {
                    "condition": h,
                    "task_key": task,
                    "denominator": 2,
                    "qualified": counts["qualified"],
                    "known_failure": counts["known_failure"],
                    "unknown": counts["unknown"],
                    "q": f"{counts['qualified']}/2",
                    "attempts": sum(q["transport"]["attempts"] for q in known)
                    if len(known) == 2
                    else None,
                    "actions": sum(q["actions"] for q in known) if len(known) == 2 else None,
                    "errors": [e for q in known for e in q["errors"]],
                    "method_signatures": sorted(
                        {q["method"]["signature"] for q in known if q["method"]}
                    ),
                    "usage": {
                        key: sum(q["transport"]["usage"][key]["total"] for q in known)
                        if len(known) == 2
                        and all(q["transport"]["usage"][key]["total"] is not None for q in known)
                        else None
                        for key in ("prompt_tokens", "completion_tokens", "total_tokens")
                    },
                    "cost_includes_known_failures": True,
                }
            )
    return record(
        "transfer_report",
        condition_id=condition["id"],
        registrations=registrations,
        cells=cells,
        sessions=rows,
        H1_H2_separate=True,
        denominator=16,
        generalization_or_training_benefit_claimed=False,
    )


def run(root):
    output = root / OUTPUT
    preparation = output / "preparation"
    manifest(preparation)
    implementation = read(preparation / "implementation.json")
    verify_source_snapshot(root, implementation)
    require(
        history_guard(root) == read(preparation / "history_guard.json"), "transfer.history_binding"
    )
    config = configuration()
    require(
        config.as_record() == read(preparation / "configuration.json"),
        "transfer.fixed_configuration",
    )
    require(
        measurement_policy() == read(preparation / "measurement_policy.json"),
        "transfer.fixed_measurement",
    )
    condition, registrations = (
        read(preparation / "condition.json"),
        read(preparation / "registrations.json"),
    )
    require(
        condition["labels"] == [r["label"] for r in registrations] == list(LABELS),
        "transfer.fixed_order",
    )
    panel = Panel(root)
    require(
        canonical_json_bytes(panel.bindings())
        == (preparation / "source_bindings.json").read_bytes(),
        "transfer.fixed_sources",
    )
    require(not (output / "execution").exists(), "transfer.no_online_resume")
    store = DurableStore(output / "execution")
    store.json("run_binding.json", condition)
    store.json("registrations.json", registrations)
    key = _credential(root / "trusted_data_synthesis/.env")
    results, halt = {}, None
    for wave in (1, 2):
        futures = {}
        with ThreadPoolExecutor(max_workers=8, thread_name_prefix="harness-transfer") as pool:
            for r in [item for item in registrations if item["wave"] == wave]:
                label = r["label"]
                child = DurableStore(store.root / "sessions" / label)
                child.json("registration.json", r)
                child.json(
                    "start.json",
                    record(
                        "transfer_start",
                        registration_id=r["id"],
                        started=halt is None,
                        reason=halt or "fixed_wave",
                    ),
                )
                print(f"START {label} wave={wave} enabled={halt is None}", flush=True)
                if halt:
                    q = record(
                        "responsibility_qualification",
                        task=r["task_group"],
                        condition=r["condition"],
                        status="unknown",
                        not_started=True,
                        reason=halt,
                    )
                    child.json("qualification.json", q)
                    seal_directory(child, kind="transfer_session_manifest", registration_id=r["id"])
                    results[label] = q
                else:
                    futures[pool.submit(run_one, panel, r, child, config, key)] = (r, child)
            for future in as_completed(futures):
                r, child = futures[future]
                try:
                    q = future.result()
                except Exception as error:
                    q = record(
                        "responsibility_qualification",
                        task=r["task_group"],
                        condition=r["condition"],
                        status="unknown",
                        reason=type(error).__name__,
                    )
                    if not (child.root / "qualification.json").exists():
                        child.json("qualification.json", q)
                    child.json(
                        "worker_failure.json", {"type": type(error).__name__, "message": str(error)}
                    )
                results[r["label"]] = q
                if q["status"] == "unknown":
                    halt = "integrity_failure_no_replacement"
                print(
                    f"END {r['label']} status={q['status']} "
                    f"attempts={q.get('transport', {}).get('attempts')} reason={q.get('reason')}",
                    flush=True,
                )
    key = None
    rows = [{"label": label, "qualification": results[label]} for label in LABELS]
    store.json("qualifications.json", rows)
    report = summarize(rows, registrations, condition)
    store.json("report.json", report)
    require(
        sum(q.get("transport", {}).get("attempts", 0) for q in results.values()) <= 512,
        "transfer.population_budget",
    )
    verify_source_snapshot(root, implementation)
    history_guard(root)
    seal_directory(
        store,
        kind="transfer_execution_manifest",
        condition_id=condition["id"],
        report_id=report["id"],
    )
    representation.build(
        output,
        registrations,
        rows,
        read(preparation / "tokenizer_binding.json"),
        read(preparation / "representation_policy.json"),
    )
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["prepare", "run", "verify"])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.root.resolve()
    if args.command == "prepare":
        result = prepare(root)
    elif args.command == "run":
        result = run(root)
    else:
        result = {
            part: manifest(root / OUTPUT / part)["id"]
            for part in ("preparation", "execution", "representation")
        }
    print(json.dumps({k: result[k] for k in ("id", "cells") if k in result} or result), flush=True)


if __name__ == "__main__":
    main()
