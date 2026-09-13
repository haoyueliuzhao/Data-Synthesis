"""Publish only closed recovery evidence; never run a producer, GPU, or API.

Run after the external operator exits. This one-shot helper does not alter the
protected main worktree, reconstruct archives, reopen raw packages, or read .env.
It checks manifest/path/byte bindings, writes a factual summary, commits an exact
allowlist on the recovery branch, and attempts one non-forced push to remote main.
An unrelated staged change or a non-fast-forward push is an explicit failure.
"""

import argparse
import hashlib
import importlib
import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

REMOTE = "https://github.com/haoyueliuzhao/Data-Synthesis.git"
REFSPEC = "HEAD:refs/heads/main"
STAGES = ("materials_seal", "prepare", "execute", "results_seal")
TERMINALS = {
    "COMPLETE_ACTUAL_EXECUTION_AND_SEALS",
    "COMPLETE_ACTUAL_EXECUTION_PUBLICATION_FAILED",
    "STOP_EXISTING_MATERIAL_GATE_FAIL",
    "STOP_OPERATOR_OR_CHILD_FAILURE",
}
SMALL_LIMIT = 4 * 1024 * 1024
SHARD_LIMIT = 32 * 1024 * 1024
SUMMARY = "trusted_data_synthesis/docs/fixed_kernel_writer_recovery_actual_results_20260913.md"
OPERATOR_SCRIPT = (
    "trusted_data_synthesis/scripts/run_fixed_kernel_writer_recovery_followthrough_20260913.py"
)
RAW_REPORTS = {
    "generation_report.json": "material_generation_report",
    "budget_finalization.json": "kernel_budget_finalization",
    "material_gate.json": "material_gate",
    "student_execution/report.json": "execution_report",
    "student_execution/decision.json": "actual_direction_decision",
    "student_execution/confirmation.json": "confirmation_analysis",
    "student_execution/execution_failure.json": "execution_failure",
}


def require(condition, code):
    if not condition:
        raise ValueError("recovery_publication." + code)


def regular(root, name, limit):
    relative = PurePosixPath(name)
    require(
        name
        and not relative.is_absolute()
        and relative.as_posix() == name
        and not {"..", ".", ".git"} & set(relative.parts)
        and "\\" not in name
        and not any(ord(char) < 32 for char in name),
        "regular_relative_path",
    )
    path = root / name
    require(
        path.is_file()
        and not any(part.is_symlink() for part in (path, *path.parents))
        and path.stat().st_size <= limit,
        "regular_bounded_file",
    )
    return path


def descriptor(root, name, limit=SMALL_LIMIT):
    path = regular(root, name, limit)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return {"path": name, "bytes": path.stat().st_size, "sha256": digest.hexdigest()}


def read_record(root, name, kind, p):
    raw = regular(root, name, SMALL_LIMIT).read_bytes()
    value = p.checked(json.loads(raw), kind)
    require(p.encode(value) == raw, "canonical_record")
    return value


def collect(root, p):
    """Read only fixed small reports and manifest-listed sealed containers/pages."""
    workflow = p.OUTPUT + "_workflow"
    terminal = read_record(root, workflow + "/terminal.json", "operator_workflow_terminal", p)
    started = read_record(root, workflow + "/started.json", "operator_workflow_started", p)
    require(
        terminal["status"] in TERMINALS and terminal["started_id"] == started["id"],
        "bound_operator_terminal_required",
    )
    require(not terminal.get("active_child_pids"), "terminal_has_unclosed_children")
    require(
        started.get("process_launcher_injected") is False
        and terminal.get("process_launcher_injected") is False,
        "actual_operator_required",
    )
    require(
        terminal.get("source_script_sha256")
        == started["operator_source_sha256"]
        == descriptor(root, OPERATOR_SCRIPT)["sha256"]
        and started["code_root"] == str(root)
        and started["raw_directory"] == str(root / p.OUTPUT),
        "operator_source_and_location_continuity",
    )
    selected = {}

    def add(name, limit=SMALL_LIMIT):
        require(name not in selected, "unique_selected_path")
        selected[name] = descriptor(root, name, limit)

    for name in ("started.json", "terminal.json", "observed_closure.json", "events.jsonl"):
        relative = workflow + "/" + name
        if (root / relative).exists():
            add(relative, 16 * 1024 * 1024 if name == "events.jsonl" else SMALL_LIMIT)
    for stage in STAGES:
        for name in ("command.json", "started.json", "exit.json", "result.json"):
            relative = workflow + "/stages/" + stage + "/" + name
            if (root / relative).exists():
                add(relative)
    reports = {}
    for name, kind in RAW_REPORTS.items():
        relative = p.OUTPUT + "/" + name
        if (root / relative).exists():
            reports[name] = read_record(root, relative, kind, p)
            add(relative)
    generation = reports.get("generation_report.json")
    final = reports.get("budget_finalization.json")
    gate = reports.get("material_gate.json")
    execution = reports.get("student_execution/report.json")
    if terminal["status"] != "STOP_OPERATOR_OR_CHILD_FAILURE":
        require(generation and final and gate, "closed_producer_reports_required")
    if generation and final:
        require(
            generation["generation_closed"]
            and generation["no_inflight_requests"]
            and final["purpose_closed"]
            and final["report_id"] == generation["id"],
            "existing_generation_budget_join",
        )
    if gate:
        require(
            generation
            and gate["generation_report_id"] == generation["id"]
            and terminal.get("material_gate_id", gate["id"]) == gate["id"],
            "existing_gate_join",
        )
    if terminal["actual_execution_complete"]:
        require(
            execution
            and execution["actual_complete"] is True
            and execution["id"] == terminal["actual_execution_report_id"],
            "actual_execution_report_join",
        )
        decision = reports.get("student_execution/decision.json")
        require(decision and execution["decision_id"] == decision["id"], "actual_decision_join")
        if execution.get("confirmation_id"):
            confirmation = reports.get("student_execution/confirmation.json")
            require(
                confirmation and execution["confirmation_id"] == confirmation["id"],
                "actual_confirmation_join",
            )
    else:
        require(execution is None, "partial_execution_not_relabelled")
    if terminal["status"] == "STOP_EXISTING_MATERIAL_GATE_FAIL":
        require(
            gate["training_gate"] == "FAIL"
            and not {"prepare", "execute"} & set(terminal["child_exit_codes"]),
            "failed_material_gate_did_not_launch_student",
        )
    seals = {}
    for stage in ("materials", "results"):
        relative = p.OUTPUT + "_publication/" + stage
        name = relative + "/publication_manifest.json"
        exit_code = terminal["child_exit_codes"].get(stage + "_seal")
        if not (root / name).exists():
            require(exit_code != 0, "successful_seal_requires_manifest")
            continue
        manifest = read_record(root, name, "publication_manifest", p)
        report = generation if stage == "materials" else execution
        require(
            report
            and manifest["stage"] == stage
            and manifest["source_root"] == p.OUTPUT
            and manifest["closure"]["report_id"] == report["id"]
            and manifest["actual_credential_scanned"] is True
            and manifest["credential_hits"] == 0
            and manifest["wallet_runtime_credentials_or_base_weights_published"] is False
            and manifest["all_original_member_SHA_and_roundtrips_verified"] is True,
            "closed_stage_manifest_binding",
        )
        receipt_name = workflow + "/stages/" + stage + "_seal/result.json"
        if (root / receipt_name).exists():
            receipt = read_record(root, receipt_name, "operator_stage_result", p)
            require(
                receipt["stage"] == stage + "_seal" and receipt["result_id"] == manifest["id"],
                "operator_seal_result_join",
            )
        else:
            require(exit_code != 0, "successful_seal_requires_operator_receipt")
        add(name)
        require(manifest["archives"], "nonempty_closed_archives")
        groups = [("archives", r"raw-[0-9]{5}\.tar\.gz", SHARD_LIMIT)]
        groups += [
            (key + "_pages", kind + r"-[0-9]{5}\.json", SMALL_LIMIT)
            for key, kind in (
                ("member_index", "original_member_index"),
                ("physical_member_index", "physical_member_index"),
                ("duplicate_content_index", "duplicate_content_index"),
            )
        ]
        for key, pattern, limit in groups:
            for row in manifest[key]:
                require(
                    re.fullmatch(pattern, row["path"]) is not None,
                    "manifest_only_known_container_or_page_names",
                )
                member = relative + "/" + row["path"]
                add(member, limit)
                require(
                    all(selected[member][field] == row[field] for field in ("bytes", "sha256")),
                    "manifest_exact_sealed_byte_binding",
                )
        seals[stage] = manifest
    return dict(
        terminal=terminal,
        reports=reports,
        seals=seals,
        members=sorted(selected.values(), key=lambda row: row["path"]),
    )


def summary(evidence):
    terminal, reports = evidence["terminal"], evidence["reports"]
    generation, gate = (
        reports.get("generation_report.json", {}),
        reports.get("material_gate.json", {}),
    )
    execution = reports.get("student_execution/report.json")

    def value(item):
        return "未提供／未测量" if item is None else json.dumps(item, ensure_ascii=False)

    lines = [
        "# Fixed-kernel writer recovery：实际终态记录",
        "",
        "本页只汇总已写出的原始报告，不重新运行实验，也不把封存成功视为科学结果通过。",
        "旧失败批次及其完整分母保持封闭；恢复批不导入旧成功前缀。",
        "",
        "## 采集与材料门",
        "",
        f"- Operator 终态：`{terminal['status']}`；记录：`{terminal['id']}`。",
    ]
    for label, item in (
        ("采集状态", generation.get("status")),
        ("预注册 session 分母", generation.get("registered_sessions")),
        ("finished session 数", generation.get("finished_sessions")),
        ("未发出请求的 session 数", generation.get("unrequested_sessions")),
        ("实际 HTTP 请求数", generation.get("actual_HTTP_request_count")),
        (
            "恢复批保守 token 扣账（不等同于全部已知 usage）",
            generation.get("kernel_conservative_debit"),
        ),
        ("既有 training gate", gate.get("training_gate")),
        ("共同干预任务数", gate.get("common_intervention_task_count")),
        ("全局质量移动量", gate.get("global_mass_movement")),
    ):
        lines.append(f"- {label}：{value(item)}。")
    lines += ["", "## Student 实际结果", ""]
    if execution:
        for key in (
            "status",
            "actual_training_runs",
            "actual_evaluation_sessions",
            "confirmation_sessions",
            "independent_positive_effect_confirmed",
        ):
            lines.append(f"- `{key}`：{value(execution.get(key))}。")
        lines.append(f"- 原始执行报告：`{execution['id']}`。")
        decision = reports["student_execution/decision.json"]
        lines.append(
            f"- 开发集既定选择：{value(decision.get('selected_arm'))}；"
            f"配对均值增益：{value(decision.get('paired_mean_gain'))}。"
        )
        confirmation = reports.get("student_execution/confirmation.json")
        if confirmation:
            primary = confirmation["pools"]["B"]
            lines.append(
                f"- 独立 B 确认状态：{value(confirmation['status'])}；"
                f"配对种子均值增益：{value(primary['paired_seed_mean_gain'])}；"
                f"95% 区间：[{value(primary['lower'])}, {value(primary['upper'])}]。"
            )
        lines.append("以上是既有报告的作用域内结论，不推断未执行分支或总体效果。")
    elif terminal["status"] == "STOP_EXISTING_MATERIAL_GATE_FAIL":
        lines.append("材料门 FAIL；operator 未启动 Student prepare/execute，训练与评估均未运行。")
    else:
        lines.append("没有完整的实际执行报告；不将部分产物记为完成，不推断训练次数或效果。")
    lines += ["", "## 已闭合封存", ""]
    for stage in ("materials", "results"):
        seal = evidence["seals"].get(stage)
        lines.append(
            f"- {stage}："
            + (
                f"manifest `{seal['id']}`；{seal['original_file_count']} 个原文件、"
                f"{seal['original_bytes']} 字节、{len(seal['archives'])} 个 archive。"
                if seal
                else "未提供闭合 manifest；没有宣称该阶段已封存。"
            )
        )
    lines += [
        "",
        "## 发布范围与限制",
        "",
        "仅提交固定 workflow 元数据、少量原始顶层报告、清单绑定的 index 页面与 archive。",
        "不直接暂存原始 session/token/kernel 巨型 JSON、控制台日志、钱包、.env 或模型基础权重。",
        "已有 publisher 完成秘密扫描与原件往返验证；本 helper 只核对清单、路径和字节绑定，",
        "没有重做财务语义验证、归档解包、API 请求或 GPU 操作。",
        "项目忽略 artifacts 目录；git add --force 仅用于已验证的精确文件白名单，不扩大暂存范围。",
        f"目标为 {REMOTE} 的 main，普通非强制 push；本页不预先宣称 push 成功。",
        "实际 commit/push 回执保存在隔离 runtime/final_publication_receipt.json。",
        "",
    ]
    return "\n".join(lines).encode("utf-8")


def git(root, *args, input=None):
    return subprocess.run(
        ["git", "--literal-pathspecs", "-C", str(root), *args],
        input=input,
        capture_output=True,
        check=True,
    )


def finalize(root, p, *, runner=git):
    root = Path(root).absolute()
    require(not any(path.is_symlink() for path in (root, *root.parents)), "regular_code_root")
    require(
        runner(root, "branch", "--show-current").stdout.decode().strip() == p.BRANCH,
        "recovery_branch_only_no_main_checkout",
    )
    require(
        not runner(root, "diff", "--cached", "--name-only", "-z").stdout,
        "preexisting_staged_changes_refused",
    )
    parent = runner(root, "rev-parse", "HEAD").stdout.decode().strip()
    recovery = read_record(
        root, p.OUTPUT + "/recovery_parent_binding.json", "recovery_parent_binding", p
    )
    runner(root, "merge-base", "--is-ancestor", recovery["protected_parent_commit"], "HEAD")
    evidence = collect(root, p)
    summary_path = root / SUMMARY
    require(not summary_path.exists() and not summary_path.is_symlink(), "one_shot_summary_only")
    require(not any(path.is_symlink() for path in summary_path.parents), "regular_summary_parents")
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with summary_path.open("xb") as stream:
        stream.write(summary(evidence))
    members = evidence["members"] + [descriptor(root, SUMMARY)]
    inventory_name = p.OUTPUT + "_workflow/final_publication_inventory.json"
    inventory = p.record(
        "operator_git_publication_inventory",
        parent_commit=parent,
        operator_terminal_id=evidence["terminal"]["id"],
        members=members,
        remote=REMOTE,
        refspec=REFSPEC,
        force_push=False,
        ignored_files_added_only_by_exact_verified_allowlist=True,
        raw_packages_reopened=False,
        archive_revalidation="path_size_SHA_only",
        API_calls=0,
        GPU_operations=0,
        credentials_read=False,
    )
    p.write_once(root / inventory_name, inventory)
    members += [descriptor(root, inventory_name)]
    names = sorted(row["path"] for row in members)
    require(
        runner(root, "rev-parse", "HEAD").stdout.decode().strip() == parent,
        "parent_unchanged_before_staging",
    )
    require(
        not runner(root, "diff", "--cached", "--name-only", "-z").stdout,
        "concurrent_staged_changes_refused",
    )
    runner(
        root,
        "add",
        "--force",
        "--pathspec-from-file=-",
        "--pathspec-file-nul",
        input=b"\0".join(name.encode() for name in names) + b"\0",
    )
    staged = set(
        runner(root, "diff", "--cached", "--name-only", "-z").stdout.decode().split("\0")
    ) - {""}
    require(staged and staged <= set(names), "only_exact_owned_allowlist_staged")
    for row in members:
        require(
            descriptor(root, row["path"], max(SHARD_LIMIT, row["bytes"])) == row,
            "selected_bytes_unchanged_before_commit",
        )
    runner(root, "diff", "--quiet", "--", *sorted(staged))
    require(
        runner(root, "rev-parse", "HEAD").stdout.decode().strip() == parent,
        "parent_unchanged_before_commit",
    )
    runner(root, "commit", "-m", "Document and publish closed fixed-kernel writer recovery results")
    commit = runner(root, "rev-parse", "HEAD").stdout.decode().strip()
    receipt = dict(
        parent_commit=parent,
        commit=commit,
        inventory_id=inventory["id"],
        remote=REMOTE,
        refspec=REFSPEC,
        force_push=False,
        local_main_worktree_modified=False,
    )
    try:
        runner(root, "push", REMOTE, REFSPEC)
    except Exception as error:
        p.write_once(
            root / p.RUNTIME / "final_publication_receipt.json",
            p.record(
                "operator_git_publication_receipt",
                status="COMMITTED_PUSH_FAILED",
                **receipt,
                error_type=type(error).__name__,
                automatic_retry=False,
            ),
        )
        raise
    result = p.record("operator_git_publication_receipt", status="COMMITTED_AND_PUSHED", **receipt)
    p.write_once(root / p.RUNTIME / "final_publication_receipt.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code-root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    root = args.code_root.absolute()
    sys.path[:0] = [str(root / "trusted_data_synthesis/src"), str(root / "raw_financial_data_lake")]
    p = importlib.import_module(
        "trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value.protocol"
    )
    require(Path(p.__file__).resolve().is_relative_to(root), "correct_frozen_protocol_location")
    print(p.encode(finalize(root, p)).decode(), flush=True)


if __name__ == "__main__":
    main()
