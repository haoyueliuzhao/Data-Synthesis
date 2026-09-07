"""One preregistered 12-session study, no online resume, retries or replacement."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from trusted_synthesis.domains.finance.qa_vnext.protocol import record, require
from trusted_synthesis.domains.finance.qa_vnext.runtime import DurableStore
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
from trusted_synthesis.experiments.finance_qa_vnext_task_panel.plan import load_panel

from .audit import manifest, no_plan, policy, qualify, read
from .interface import VERSION
from .runtime import StudyRuntime

OUTPUT = "trusted_data_synthesis/artifacts/qa_vnext_harness_responsibility/harness_v1_20260907"
DESIGN = "trusted_data_synthesis/docs/finance_qa_vnext_harness_responsibility_pilot.md"
AUDIT_SHA256 = "ecbd7f870150564b2ea6afbb12d73c7c798ad74b073d6567c8bbfd7f8e0a98e6"
PARENT = "d91f0e55d4a67dd2c8b183939d979ec3ed6c4226"
SYSTEM = (
    "Follow the public QA protocol in the user message. It contains the current task, "
    "evidence, state, tool/interface rules and strict response schemas. Make the choices "
    "required by that interface and return exactly one allowed JSON Action, Update, or Final. "
    "Use only this request. Do not output Markdown, private reasoning or native tool calls. "
    "Do not invent evidence or alter the contract."
)
LABELS = tuple(f"{g}_{h}_{n:02d}" for n in (1, 2) for h in ("H0", "H1", "H2") for g in ("S", "B"))


def configuration():
    return TransportConfig(system_prompt=SYSTEM)


def historical_guard(root):
    """No historical replay: compare previously committed paths, excluding this new stage."""
    prefixes = [
        "trusted_data_synthesis/artifacts/" + value
        for value in (
            "qa_vnext_integration",
            "qa_vnext_model_execution",
            "qa_vnext_update_calibration",
            "qa_vnext_repaired_full_task",
            "qa_vnext_action_branch",
            "qa_vnext_length_adaptation",
            "qa_vnext_task_panel",
            "qa_vnext_panel_quotient",
            "qa_vnext_support_exploration",
            "qa_vnext_support_transition",
            "qa_vnext_cross_binding",
            "qa_vnext_final_publication",
        )
    ]
    status = subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=all", "--", *prefixes], cwd=root
    )
    diff = subprocess.check_output(
        ["git", "diff", "--name-only", PARENT, "--", *prefixes], cwd=root
    )
    require(not status and not diff, "study.historical_artifacts_changed")
    tree = subprocess.check_output(["git", "ls-tree", "-r", PARENT, "--", *prefixes], cwd=root)
    return {
        "parent_commit": PARENT,
        "historical_git_tree_listing_sha256": hashlib.sha256(tree).hexdigest(),
        "historical_paths": len(tree.splitlines()),
        "old_artifacts_unchanged": True,
        "old_qualification_or_quotient_recomputed": False,
    }


def prepare(root):
    output = root / OUTPUT
    require(not output.exists(), "study.already_prepared")
    implementation = source_snapshot(root)
    panel = load_panel(root)
    config = configuration()
    store = DurableStore(output / "preparation")
    store.json("implementation.json", implementation)
    store.json("configuration.json", config.as_record())
    store.json("measurement_policy.json", policy())
    store.json("historical_guard.json", historical_guard(root))
    test_path = "trusted_data_synthesis/tests/test_qa_vnext_harness_responsibility.py"
    test_bytes = (root / test_path).read_bytes()
    control = subprocess.run(
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
    store.write("controls_stdout.txt", control.stdout)
    store.write("controls_stderr.txt", control.stderr)
    store.json(
        "controls.json",
        record(
            "responsibility_controls",
            exit_code=control.returncode,
            provider_calls=0,
            test_source_sha256=hashlib.sha256(test_bytes).hexdigest(),
            source_path=test_path,
            population_samples=0,
            historical_tests_reopened=False,
        ),
    )
    require(control.returncode == 0, "study.new_risk_controls_failed")
    design = (root / DESIGN).read_bytes()
    store.write("design_at_freeze.md", design)
    registrations = []
    for ordinal, label in enumerate(LABELS, 1):
        group, condition, repetition = label.split("_")
        base = panel.adapter(group)
        registrations.append(
            record(
                "responsibility_registration",
                label=label,
                task_group=group,
                condition=condition,
                repetition=int(repetition),
                wave=int(repetition),
                ordinal=ordinal,
                task_id=base.context["task_id"],
                base_context_id=base.context["id"],
                source_binding_id=base.context["source_binding"]["id"],
                model_configuration_id=config.as_record()["id"],
                fresh_session=True,
                maximum_actions=12,
                maximum_submissions=32,
                maximum_provider_attempts=32,
                neutral_task_prompt=True,
                route_preference_prompt=False,
                replacement_allowed=False,
            )
        )
    condition = record(
        "responsibility_condition",
        version=VERSION,
        audit_sha256=AUDIT_SHA256,
        source_commit=implementation["source_commit"],
        implementation_id=implementation["id"],
        model_configuration_id=config.as_record()["id"],
        measurement_policy_id=policy()["id"],
        design_sha256=hashlib.sha256(design).hexdigest(),
        labels=list(LABELS),
        waves=[list(LABELS[:6]), list(LABELS[6:])],
        maximum_parallel_sessions=6,
        registered_sessions=12,
        maximum_provider_attempts=384,
        maximum_reserved_token_allowance=384 * 107520,
        task_marginal_per_condition={h: {"S": "1/2", "B": "1/2"} for h in ("H0", "H1", "H2")},
        generation_environments={
            "H0": "original plan, bound candidates, full submission, common Final",
            "H1": "same plan and candidates; declared compact language",
            "H2": "compact proposal language; finite source/type composition",
        },
        automatic_network_retries=0,
        model_fallbacks=0,
        online_resume=False,
        failed_session_replacement=False,
        success_stops_session_immediately=True,
        wave2_on_integrity_failure="not_started_unknown; preserve all twelve registrations",
        dispatch_order="Fixed launch order within each wave; "
        "concurrent HTTP arrival order is not fixed",
        student_loaded=False,
        training=False,
        gpu_training=False,
        vtdo_weight_update=False,
        equal_submission_cap_does_not_imply_equal_actual_cost=True,
    )
    store.json("condition.json", condition)
    store.json("registrations.json", registrations)
    for group in ("S", "B"):
        for h in ("H0", "H1", "H2"):
            # A zero-call runtime supplies only the actual rendered initial Request.
            callback = type(
                "NoCall", (), {"binding": record("callback_binding", origin="adapter_mock")}
            )()
            view = StudyRuntime(
                panel.adapter(group),
                group,
                h,
                callback,
                output / "preparation" / "initial_views" / f"{group}_{h}",
            )
            request = view.request()
            http = render_http_request(
                request, config, session_id=f"initial_{group}_{h}", attempt_index=0
            )
            require(http["body_byte_count"] <= 98304, "study.initial_request_budget")
            if h == "H2":
                no_plan(json.loads(http["body"]["messages"][1]["content"]))
            store.json(f"initial_requests/{group}_{h}.json", request)
            store.write(f"initial_http/{group}_{h}.body", http["body_json"].encode())
    seal_directory(store, kind="responsibility_preparation_manifest", condition_id=condition["id"])
    return condition


def _run_one(panel, registration, store, config, key):
    group, condition, label = (
        registration["task_group"],
        registration["condition"],
        registration["label"],
    )
    callback = OnlineModelCallback(
        config,
        session_id=registration["id"],
        evidence_directory=store.root / "transport",
        api_key=key,
    )
    runtime = StudyRuntime(panel.adapter(group), group, condition, callback, store.root / "runtime")
    runtime.run()
    callback.finalize()
    result = qualify(panel.adapter(group), group, condition, store.root, config)
    store.json("qualification.json", result)
    if result["status"] != "unknown":
        review(store, label, result)
    seal_directory(
        store,
        kind="responsibility_session_manifest",
        registration_id=registration["id"],
        qualification_id=result["id"],
    )
    return result


def review(store, label, result):
    session = read(store.root / "runtime/session.json")
    lines = [
        f"# {label}",
        "",
        f"资格：{result['status']}。接口：{result['condition']}。",
        "",
        "模型原始字段与 SYSTEM 引用展开分别保存在每轮 response.txt / language_binding.json。",
        "下表中的 H0/H1 子目标来自已展示候选；H2 子目标和简短理由来自模型的实际提案。",
        "",
        "| 提交 | 类型 | 实际行为／拒绝 |",
        "| --- | --- | --- |",
    ]
    for event in session["events"]:
        parsed = event["parsed"] or {}
        if not event["receipt"]["admitted"]:
            detail = "拒绝：" + event["receipt"]["error_code"]
        elif "execution" in event:
            option = event["execution"]["selected_action"]
            detail = json.dumps(
                {
                    "子目标": option["subgoal"],
                    "理由": option.get("reason"),
                    "操作": option["operation"],
                    "输入": option["inputs"],
                    "观察": event["execution"]["proposition"]["output"],
                },
                ensure_ascii=False,
            )
        elif "claim" in event:
            detail = "明确接受整个观察：" + event["claim"]["observation_id"]
        elif "final" in event:
            detail = "Final 校验通过：" + json.dumps(event["final"]["answer"], ensure_ascii=False)
        else:
            detail = "拒绝观察或执行终止"
        lines.append(
            f"| {event['sequence'] + 1} | {parsed.get('kind', 'invalid')} | "
            + detail.replace("|", "\\|").replace("\n", " ")
            + " |"
        )
    if result.get("method"):
        lines += [
            "",
            "## 实际 Final 支持图（不是完整行为商）",
            "",
            "```json",
            json.dumps(result["method"], ensure_ascii=False, indent=2),
            "```",
            "",
        ]
    store.write("review.md", "\n".join(lines).encode())


def run(root):
    output = root / OUTPUT
    manifest(output / "preparation")
    preparation = output / "preparation"
    condition, registrations = (
        read(preparation / "condition.json"),
        read(preparation / "registrations.json"),
    )
    require(
        condition["labels"] == list(LABELS) and [r["label"] for r in registrations] == list(LABELS),
        "study.fixed_schedule",
    )
    implementation = read(preparation / "implementation.json")
    verify_source_snapshot(root, implementation)
    require(
        read(preparation / "configuration.json") == configuration().as_record(),
        "study.frozen_config",
    )
    require(read(preparation / "measurement_policy.json") == policy(), "study.frozen_measurement")
    require(
        read(preparation / "historical_guard.json") == historical_guard(root),
        "study.history_preserved",
    )
    execution = output / "execution"
    require(not execution.exists(), "study.no_online_resume_or_replacement")
    store = DurableStore(execution)
    store.json("run_binding.json", condition)
    store.json("registrations.json", registrations)
    panel, config = load_panel(root), configuration()
    key = _credential(root / "trusted_data_synthesis/.env")
    results, halt = {}, None
    for wave in (1, 2):
        futures = {}
        with ThreadPoolExecutor(max_workers=6, thread_name_prefix="harness-responsibility") as pool:
            for registration in [r for r in registrations if r["wave"] == wave]:
                label = registration["label"]
                child = DurableStore(execution / "sessions" / label)
                child.json("registration.json", registration)
                child.json(
                    "start.json",
                    record(
                        "responsibility_start",
                        label=label,
                        registration_id=registration["id"],
                        started=halt is None,
                        reason=halt or "fixed_nonadaptive_wave",
                    ),
                )
                print(f"START {label} wave={wave} authorized={halt is None}", flush=True)
                if halt:
                    result = record(
                        "responsibility_qualification",
                        task=registration["task_group"],
                        condition=registration["condition"],
                        status="unknown",
                        reason=halt,
                        not_started=True,
                        known_denominator_preserved=True,
                    )
                    child.json("qualification.json", result)
                    seal_directory(
                        child,
                        kind="responsibility_session_manifest",
                        registration_id=registration["id"],
                        qualification_id=result["id"],
                    )
                    results[label] = result
                else:
                    future = pool.submit(_run_one, panel, registration, child, config, key)
                    futures[future] = (registration, child)
            for future in as_completed(futures):
                registration, child = futures[future]
                label = registration["label"]
                try:
                    result = future.result()
                except Exception as error:
                    halt = "worker_or_integrity_failure"
                    # Preserve partial evidence; never fabricate a missing runtime/transport tail.
                    result = record(
                        "responsibility_qualification",
                        task=registration["task_group"],
                        condition=registration["condition"],
                        status="unknown",
                        reason=type(error).__name__,
                        known_denominator_preserved=True,
                    )
                    if not (child.root / "qualification.json").exists():
                        child.json("qualification.json", result)
                    child.json(
                        "worker_failure.json",
                        {"exception_type": type(error).__name__, "message": str(error)},
                    )
                results[label] = result
                if result["status"] == "unknown":
                    halt = "worker_or_integrity_failure"
                print(
                    f"END {label} status={result['status']} "
                    f"attempts={result.get('transport', {}).get('attempts')} "
                    f"reason={result.get('reason')}",
                    flush=True,
                )
    key = None
    ordered = [{"label": label, "qualification": results[label]} for label in LABELS]
    store.json("qualifications.json", ordered)
    verify_source_snapshot(root, implementation)
    require(
        read(preparation / "historical_guard.json") == historical_guard(root),
        "study.history_preserved",
    )
    report = summarize(ordered, condition)
    store.json("report.json", report)
    store.write("report.md", render_report(report).encode())
    seal_directory(
        store,
        kind="responsibility_execution_manifest",
        condition_id=condition["id"],
        report_id=report["id"],
    )
    return report


def summarize(rows, condition):
    cells = []
    for h in ("H0", "H1", "H2"):
        for group in ("S", "B"):
            selected = [
                row["qualification"]
                for row in rows
                if row["qualification"]["condition"] == h and row["qualification"]["task"] == group
            ]
            require(len(selected) == 2, "study.fixed_cell_denominator")
            statuses = Counter(q["status"] for q in selected)
            measured = [q for q in selected if q["status"] != "unknown"]
            cells.append(
                {
                    "condition": h,
                    "task": group,
                    "denominator": 2,
                    "qualified": statuses["qualified"],
                    "known_failure": statuses["known_failure"],
                    "unknown": statuses["unknown"],
                    "q": f"{statuses['qualified']}/2",
                    "provider_attempts": sum(q["transport"]["attempts"] for q in measured)
                    if len(measured) == 2
                    else None,
                    "submissions": sum(q["submissions"] for q in measured)
                    if len(measured) == 2
                    else None,
                    "actions": sum(q["actions"] for q in measured) if len(measured) == 2 else None,
                    "interface_errors": sum(
                        e["category"] == "interface" for q in measured for e in q["errors"]
                    ),
                    "error_categories": dict(
                        Counter(e["category"] for q in measured for e in q["errors"])
                    ),
                    "method_signatures": sorted(
                        {q["method"]["signature"] for q in measured if q["method"]}
                    ),
                    "usage": {
                        key: sum(q["transport"]["usage"][key]["total"] for q in measured)
                        if len(measured) == 2
                        and all(q["transport"]["usage"][key]["total"] is not None for q in measured)
                        else None
                        for key in ("prompt_tokens", "completion_tokens", "total_tokens")
                    },
                }
            )
    attempts = [cell["provider_attempts"] for cell in cells]
    lower = sum(v for v in attempts if v is not None)
    require(lower <= 384, "study.population_attempt_cap")
    return record(
        "responsibility_report",
        condition_id=condition["id"],
        registered_sessions=12,
        registered_tasks=2,
        conditions_separate=True,
        cells=cells,
        sessions=rows,
        provider_attempts=sum(attempts) if all(v is not None for v in attempts) else None,
        declared_provider_attempt_cap=384,
        statistical_generalization_claimed=False,
        full_behavior_quotient_inherited=False,
        training_or_vtdo_updates=False,
    )


def render_report(report):
    lines = [
        "# H0/H1/H2 有限责任对照结果",
        "",
        "每单元分母固定为 2。未知不删行，历史轨迹不进入本轮分母。",
        "",
        "| 条件 | 任务 | 有效 / 2 | 已知失败 | 未知 | API 次数 | 接口错误 | "
        "Prompt Tokens | Completion Tokens |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for cell in report["cells"]:
        lines.append(
            f"| {cell['condition']} | {cell['task']} | {cell['q']} | {cell['known_failure']} "
            f"| {cell['unknown']} | {cell['provider_attempts']} | {cell['interface_errors']} "
            f"| {cell['usage']['prompt_tokens']} | {cell['usage']['completion_tokens']} |"
        )
    lines += [
        "",
        "同一提交上限不等于相同实际计算成本。两个条件差异是设计包对照，不识别单字段因果效应。",
        "方法签名只描述实际有效支持图，不是完整行为商、内部思考证明或训练价值。",
        "",
    ]
    for row in report["sessions"]:
        q = row["qualification"]
        lines.append(f"- [{row['label']}](sessions/{row['label']}/review.md)：{q['status']}")
    return "\n".join(lines) + "\n"


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
        manifest(root / OUTPUT / "preparation")
        result = manifest(root / OUTPUT / "execution")
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
