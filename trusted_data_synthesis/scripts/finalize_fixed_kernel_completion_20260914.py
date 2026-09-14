"""Publish closed completion evidence; never start producers, API calls or GPUs.

This external, one-shot helper is outside the scientific code-snapshot glob.
It reads fixed small reports and manifest-listed sealed files, verifies their
byte bindings, writes a factual amendment-aware summary, then stages an exact
allowlist with ``--sparse --force`` and attempts one ordinary push to main.
"""

import argparse
import importlib
import importlib.util
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

_SPEC = importlib.util.spec_from_file_location(
    "closed_kernel_publication_primitives",
    Path(__file__).with_name("finalize_fixed_kernel_writer_recovery_publication_20260913.py"),
)
_PRIOR = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_PRIOR)
regular, descriptor, read_record, git = (
    _PRIOR.regular,
    _PRIOR.descriptor,
    _PRIOR.read_record,
    _PRIOR.git,
)

REMOTE, REFSPEC = _PRIOR.REMOTE, _PRIOR.REFSPEC
SMALL_LIMIT, SHARD_LIMIT = _PRIOR.SMALL_LIMIT, _PRIOR.SHARD_LIMIT
BRANCH = "codex/fixed-kernel-completion-20260914"
OUTPUT = (
    "trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/study_20260914_budget_completion"
)
RUNTIME = "trusted_data_synthesis/runtime/fixed_kernel_completion_20260914"
SUMMARY = "trusted_data_synthesis/docs/fixed_kernel_budget_completion_actual_results_20260914.md"
COMPLETION_SOURCE = (
    "trusted_data_synthesis/src/trusted_synthesis/experiments/"
    "finance_qa_vnext_fixed_kernel_value/completion.py"
)
TERMINALS = _PRIOR.TERMINALS
RAW_REPORTS = {
    "freeze.json": "study_freeze",
    "completion_freeze.json": "kernel_completion_freeze",
    "completion_code_snapshot.json": "study_code_snapshot",
    "authorization.json": "kernel_completion_authorization",
    "parent_binding.json": "completion_parent_binding",
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
        raise ValueError("completion_publication." + code)


def signature(path):
    value = path.stat()
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)


def collect(root, p):
    """No raw-tree enumeration, archive extraction, secret scan or reassessment."""
    workflow = p.OUTPUT + "_workflow"
    terminal = read_record(root, workflow + "/terminal.json", "completion_workflow_terminal", p)
    started = read_record(root, workflow + "/started.json", "completion_workflow_started", p)
    require(terminal["status"] in TERMINALS, "recognized_closed_workflow_terminal")
    require(not terminal.get("active_child_pids"), "terminal_has_unclosed_children")
    require(
        terminal.get("started_id") == started["id"]
        and terminal.get("process_launcher_injected") is False
        and started.get("process_launcher_injected") is False
        and type(terminal.get("actual_execution_complete")) is bool
        and isinstance(terminal.get("ended_at"), str)
        and terminal["ended_at"],
        "bound_actual_workflow_terminal",
    )
    require(
        terminal.get("completion_source_sha256")
        == started.get("completion_source_sha256")
        == descriptor(root, COMPLETION_SOURCE)["sha256"],
        "completion_source_continuity",
    )
    selected, signatures = {}, {}

    def add(name, limit=SMALL_LIMIT):
        require(name not in selected, "unique_selected_path")
        path = regular(root, name, limit)
        before = signature(path)
        selected[name] = descriptor(root, name, limit)
        signatures[name] = signature(path)
        require(before == signatures[name], "sealed_file_changed_during_hash")

    for name in ("started.json", "terminal.json"):
        add(workflow + "/" + name)
    for stage in ("materials_seal", "results_seal"):
        for name in ("command.json", "started.json", "exit.json"):
            relative = workflow + "/stages/" + stage + "/" + name
            if (root / relative).exists():
                add(relative)
    reports = {}
    for name, kind in RAW_REPORTS.items():
        relative = p.OUTPUT + "/" + name
        if (root / relative).exists():
            reports[name] = read_record(root, relative, kind, p)
            add(relative)
    for name in (
        "freeze.json",
        "completion_freeze.json",
        "completion_code_snapshot.json",
        "authorization.json",
        "parent_binding.json",
    ):
        require(name in reports, "completion_amendment_records_required")
    original = reports["freeze.json"]
    frozen = reports["completion_freeze.json"]
    authorization = reports["authorization.json"]
    parent = reports["parent_binding.json"]
    require(
        terminal["completion_freeze_id"] == started["completion_freeze_id"] == frozen["id"]
        and frozen["original_freeze_id"] == original["id"] == parent["original_freeze_id"]
        and frozen["authorization_id"] == authorization["id"]
        and frozen["parent_binding_id"] == parent["id"]
        and frozen["parent_commit"] == parent["commit"]
        and frozen["output_directory"] == p.OUTPUT
        and terminal.get("code_snapshot_id")
        == started.get("code_snapshot_id")
        == frozen["code_snapshot_id"]
        == reports["completion_code_snapshot.json"]["id"],
        "new_authorization_old_registry_and_actual_code_join",
    )
    require(
        authorization["original_combined_token_cap"] == 250000000
        and authorization["amended_combined_token_cap"] == 350000000
        and authorization["new_purpose_token_cap"] == 109024251
        and authorization["new_HTTP_request_cap"] == 8300
        and authorization["common_token_cap"] == 1000000000
        and authorization["already_finished_retained"] == 9968
        and authorization["unfinished_slots"] == 272
        and authorization["authenticated_prefix_responses"] == 404
        and authorization["amendment_after_parent_budget_stop"] is True
        and authorization["unamended_preregistration_claimed"] is False,
        "explicit_prospective_budget_amendment",
    )
    generation = reports.get("generation_report.json")
    final = reports.get("budget_finalization.json")
    gate = reports.get("material_gate.json")
    execution = reports.get("student_execution/report.json")
    if terminal["status"] != "STOP_OPERATOR_OR_CHILD_FAILURE":
        require(generation and final and gate, "closed_generation_and_gate_required")
    if generation and final:
        require(
            generation["generation_closed"] is True
            and generation["no_inflight_requests"] is True
            and final["purpose_closed"] is True
            and final["report_id"] == generation["id"]
            and generation["completion_freeze_id"] == final["completion_freeze_id"] == frozen["id"]
            and generation["freeze_id"] == final["freeze_id"] == original["id"]
            and generation["budget_amendment_id"] == authorization["id"]
            and generation["parent_generation_report_id"] == parent["generation_report_id"]
            and final["purpose"] == "kernel_completion_registration",
            "closed_seventh_purpose_generation_join",
        )
    if gate:
        require(
            generation
            and gate["generation_report_id"] == generation["id"]
            and terminal["material_gate_id"] == started["material_gate_id"] == gate["id"],
            "existing_material_gate_join",
        )
    if terminal["actual_execution_complete"]:
        require(
            execution
            and execution["actual_complete"] is True
            and execution["id"] == terminal["actual_execution_report_id"]
            and gate
            and gate["training_gate"] == "PASS",
            "actual_execution_not_engineering_probe",
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
    codes = terminal.get("child_exit_codes")
    require(
        isinstance(codes, dict) and all(type(x) is int for x in codes.values()),
        "explicit_child_exit_codes",
    )
    if terminal["status"] == "STOP_EXISTING_MATERIAL_GATE_FAIL":
        require(
            gate["training_gate"] == "FAIL"
            and not terminal["actual_execution_complete"]
            and "results_seal" not in codes,
            "failed_gate_did_not_launch_formal_student",
        )
    if terminal["status"] == "COMPLETE_ACTUAL_EXECUTION_AND_SEALS":
        require(
            terminal["actual_execution_complete"]
            and codes == {"materials_seal": 0, "results_seal": 0},
            "complete_requires_actual_execution_and_two_closed_seals",
        )
    seals = {}
    for stage in ("materials", "results"):
        relative = p.OUTPUT + "_publication/" + stage
        name = relative + "/publication_manifest.json"
        exit_code = codes.get(stage + "_seal")
        exit_name = workflow + "/stages/" + stage + "_seal/exit.json"
        if exit_code == 0:
            observed = read_record(root, exit_name, "completion_stage_exit", p)
            require(
                observed["stage"] == stage + "_seal" and observed["return_code"] == 0,
                "successful_seal_exit_join",
            )
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
                    "only_known_manifest_container_and_page_names",
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
        signatures=signatures,
        members=sorted(selected.values(), key=lambda row: row["path"]),
    )


def summary(evidence):
    terminal, reports = evidence["terminal"], evidence["reports"]
    generation, gate = (
        reports.get("generation_report.json", {}),
        reports.get("material_gate.json", {}),
    )
    authorization = reports["authorization.json"]
    execution = reports.get("student_execution/report.json")

    def value(item):
        return "未提供／未测量" if item is None else json.dumps(item, ensure_ascii=False)

    lines = [
        "# Fixed-kernel 预算修订补完：实际终态记录",
        "",
        "本页只汇总已有闭合报告；封存成功或实际训练完成都不等于科学结果为正。",
        "本轮是在旧批次预算停止后，由用户明确授权的前瞻性预算修订，",
        "不是原始未修订预注册方案的完整执行。旧 STOP 报告、关闭用途及历史扣账未改写。",
        "",
        "## 预算修订与保留范围",
        "",
        f"- 授权记录：`{authorization['id']}`。",
        "- 原两批合计 token 上限由 250,000,000 提高至 350,000,000；共同上限仍为 1,000,000,000。",
        "- 第七用途仅允许补完原 272 槽位，额度 109,024,251 tokens、最多 8,300 个新增 HTTP 请求。",
        "- 原 9,968 个 finished 槽位原样保留；404 个已认证响应只作离线前缀，不重新请求或扣账。",
        "- 原未知用量扣账继续保留；提高额度不释放历史未知成本，也不提供失败或未知请求重试。",
        "- 额度是受控追加上限，不是必须消耗的费用，也不是完成所有理论最坏响应长度的保证。",
        "",
        "## 采集与材料门",
        "",
        f"- Workflow 终态：`{terminal['status']}`；记录：`{terminal['id']}`。",
    ]
    for label, item in (
        ("采集状态", generation.get("status")),
        ("原始 session 总分母", generation.get("registered_sessions")),
        ("最终 finished session 数", generation.get("finished_sessions")),
        ("保留原 finished 数", generation.get("inherited_finished_sessions")),
        ("本轮新写 session 记录数", generation.get("newly_generated_session_records")),
        ("仍未请求 session 数", generation.get("unrequested_sessions")),
        ("本轮新增 HTTP 请求数", generation.get("new_HTTP_request_count")),
        ("报告口径累计 HTTP 请求数", generation.get("actual_HTTP_request_count")),
        ("本轮保守 token 扣账", generation.get("completion_conservative_debit")),
        ("恢复批及补完批累计保守 token 扣账", generation.get("kernel_conservative_debit")),
        ("共同保守 token 扣账", generation.get("common_conservative_debit")),
        ("既有 training gate", gate.get("training_gate")),
        ("共同干预任务数", gate.get("common_intervention_task_count")),
        ("全局质量移动量", gate.get("global_mass_movement")),
    ):
        lines.append(f"- {label}：{value(item)}。")
    lines += ["", "## 正式 Student 实际结果", ""]
    if execution:
        for key in (
            "status",
            "actual_training_runs",
            "actual_evaluation_sessions",
            "confirmation_sessions",
            "independent_positive_effect_confirmed",
        ):
            lines.append(f"- `{key}`：{value(execution.get(key))}。")
        lines.append(f"- 原始正式执行报告：`{execution['id']}`。")
        decision = reports["student_execution/decision.json"]
        lines.append(
            f"- 开发集既定选择：{value(decision.get('selected_arm'))}；"
            f"配对均值增益：{value(decision.get('paired_mean_gain'))}。"
        )
        confirmation = reports.get("student_execution/confirmation.json")
        if confirmation:
            primary = confirmation["pools"]["B"]
            lines.append(
                f"- 独立 B 确认：{value(confirmation['status'])}；"
                f"配对种子均值增益：{value(primary['paired_seed_mean_gain'])}；"
                f"95% 区间：[{value(primary['lower'])}, {value(primary['upper'])}]。"
            )
        lines.append("以上只转述实际执行报告，不推断未执行分支；工程冒烟与正式训练分开计数。")
    elif terminal["status"] == "STOP_EXISTING_MATERIAL_GATE_FAIL":
        lines.append("材料门 FAIL，本工作流未启动正式 Student 训练；没有正式训练效果可报告。")
    else:
        lines.append("没有完整正式执行报告；不把部分产物或工程检查记为正式训练完成。")
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
        "仅暂存固定 workflow 元数据、少量顶层报告及已封存清单明确列出的 index 页面与 archive。",
        "不遍历 raw，不提交 session/kernel 巨型 JSON、console 日志、钱包、.env 或基础模型权重。",
        "秘密扫描、财务语义与原件往返验证沿用既有 publisher 的闭合声明；本 helper 不重跑这些步骤。",
        "每个封存文件只做一次清单 SHA/长度核验，暂存后检查文件身份/时间戳及 Git 索引一致性。",
        "稀疏且忽略的 artifacts 通过 git add --sparse --force 的精确白名单加入，不扩大暂存范围。",
        f"目标为 {REMOTE} 的 main；只尝试一次普通非强制 push，本页不预先宣称 push 成功。",
        "实际 commit/push 回执位于隔离 runtime/final_publication_receipt.json。",
        "",
    ]
    return "\n".join(lines).encode()


def finalize(root, p, *, runner=git):
    root = Path(root).absolute()
    require(not any(path.is_symlink() for path in (root, *root.parents)), "regular_code_root")
    require(
        runner(root, "branch", "--show-current").stdout.decode().strip() == p.BRANCH,
        "completion_branch_only",
    )
    require(
        not runner(root, "diff", "--cached", "--name-only", "-z").stdout,
        "preexisting_staged_changes_refused",
    )
    parent_commit = runner(root, "rev-parse", "HEAD").stdout.decode().strip()
    evidence = collect(root, p)
    runner(
        root,
        "merge-base",
        "--is-ancestor",
        evidence["reports"]["parent_binding.json"]["commit"],
        "HEAD",
    )
    summary_path = root / SUMMARY
    require(not summary_path.exists() and not summary_path.is_symlink(), "one_shot_summary_only")
    require(not any(path.is_symlink() for path in summary_path.parents), "regular_summary_parents")
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with summary_path.open("xb") as stream:
        stream.write(summary(evidence))
    members = evidence["members"] + [descriptor(root, SUMMARY)]
    signatures = {**evidence["signatures"], SUMMARY: signature(summary_path)}
    inventory_name = p.OUTPUT + "_workflow/final_publication_inventory.json"
    inventory = p.record(
        "completion_git_publication_inventory",
        parent_commit=parent_commit,
        completion_freeze_id=evidence["terminal"]["completion_freeze_id"],
        workflow_terminal_id=evidence["terminal"]["id"],
        members=members,
        remote=REMOTE,
        refspec=REFSPEC,
        force_push=False,
        sparse_exact_allowlist=True,
        ignored_files_added_only_by_exact_verified_allowlist=True,
        raw_packages_reopened=False,
        archive_revalidation="one_SHA_pass_then_stat_and_index_continuity",
        API_calls=0,
        GPU_operations=0,
        credentials_read=False,
        original_budget_amendment_not_hidden=True,
    )
    p.write_once(root / inventory_name, inventory)
    members += [descriptor(root, inventory_name)]
    signatures[inventory_name] = signature(root / inventory_name)
    names = sorted(row["path"] for row in members)
    require(
        runner(root, "rev-parse", "HEAD").stdout.decode().strip() == parent_commit,
        "parent_unchanged_before_staging",
    )
    require(
        not runner(root, "diff", "--cached", "--name-only", "-z").stdout,
        "concurrent_staged_changes_refused",
    )
    runner(
        root,
        "add",
        "--sparse",
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
        path = regular(root, row["path"], max(SHARD_LIMIT, row["bytes"]))
        require(signature(path) == signatures[row["path"]], "selected_file_changed_after_hash")
    runner(root, "diff", "--quiet", "--", *sorted(staged))
    require(
        runner(root, "rev-parse", "HEAD").stdout.decode().strip() == parent_commit,
        "parent_unchanged_before_commit",
    )
    runner(root, "commit", "-m", "Document and publish amended fixed-kernel completion results")
    commit = runner(root, "rev-parse", "HEAD").stdout.decode().strip()
    receipt = dict(
        parent_commit=parent_commit,
        commit=commit,
        inventory_id=inventory["id"],
        remote=REMOTE,
        refspec=REFSPEC,
        force_push=False,
        completion_freeze_id=evidence["terminal"]["completion_freeze_id"],
        local_main_worktree_modified=False,
    )
    try:
        runner(root, "push", REMOTE, REFSPEC)
    except Exception as error:
        p.write_once(
            root / p.RUNTIME / "final_publication_receipt.json",
            p.record(
                "completion_git_publication_receipt",
                status="COMMITTED_PUSH_FAILED",
                **receipt,
                error_type=type(error).__name__,
                automatic_retry=False,
            ),
        )
        raise
    result = p.record(
        "completion_git_publication_receipt", status="COMMITTED_AND_PUSHED", **receipt
    )
    p.write_once(root / p.RUNTIME / "final_publication_receipt.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code-root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    root = args.code_root.absolute()
    sys.path[:0] = [str(root / "trusted_data_synthesis/src"), str(root / "raw_financial_data_lake")]
    protocol = importlib.import_module(
        "trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value.protocol"
    )
    require(Path(protocol.__file__).resolve().is_relative_to(root), "correct_protocol_location")
    p = SimpleNamespace(
        OUTPUT=OUTPUT,
        RUNTIME=RUNTIME,
        BRANCH=BRANCH,
        **{
            name: getattr(protocol, name)
            for name in ("record", "checked", "read_json", "write_once", "encode")
        },
    )
    print(p.encode(finalize(root, p)).decode(), flush=True)


if __name__ == "__main__":
    main()
