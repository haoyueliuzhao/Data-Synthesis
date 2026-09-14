"""One-shot external fast-execution seal/copy/lineage/publication operator.

With --wait, only existence of three closure files is polled every ten seconds.
No collection, token encoding, training, old-workflow terminal fabrication, or
old-material resealing is performed. The already closed old material archive is
copied by its exact manifest; only the new actual results invoke the publisher.
"""

import argparse
import hashlib
import importlib
import importlib.util
import json
import os
import re
import sys
import time
from pathlib import Path, PurePosixPath
from types import SimpleNamespace

_SPEC = importlib.util.spec_from_file_location(
    "fast_publication_primitives",
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
RECEIPT_LIMIT = 128 * 1024 * 1024
SCRIPT = "trusted_data_synthesis/scripts/finalize_fixed_kernel_fast_execution_20260914.py"
DEPENDENCY = (
    "trusted_data_synthesis/scripts/finalize_fixed_kernel_writer_recovery_publication_20260913.py"
)
SUMMARY = "trusted_data_synthesis/docs/fixed_kernel_fast_execution_actual_results_20260914.md"


def require(value, code):
    if not value:
        raise ValueError("fast_publication." + code)


def signature(path):
    row = path.stat()
    return row.st_dev, row.st_ino, row.st_size, row.st_mtime_ns, row.st_ctime_ns


def publication_names(manifest):
    """Only fixed manifest/index/container names can cross worktree boundaries."""
    groups = [("archives", r"raw-[0-9]{5}\.tar\.gz", SHARD_LIMIT)]
    groups += [
        (key + "_pages", kind + r"-[0-9]{5}\.json", SMALL_LIMIT)
        for key, kind in (
            ("member_index", "original_member_index"),
            ("physical_member_index", "physical_member_index"),
            ("duplicate_content_index", "duplicate_content_index"),
        )
    ]
    seen = set()
    require(manifest["archives"], "closed_manifest_has_archives")
    for key, pattern, limit in groups:
        for row in manifest[key]:
            require(
                re.fullmatch(pattern, row["path"]) is not None and row["path"] not in seen,
                "exact_unique_manifest_member_names",
            )
            require(
                type(row["bytes"]) is int and 0 <= row["bytes"] <= limit, "bounded_manifest_member"
            )
            seen.add(row["path"])
            yield row, limit


def validate_manifest(manifest, *, stage, source_root, report_id):
    require(
        manifest["stage"] == stage
        and manifest["source_root"] == source_root
        and manifest["closure"]["report_id"] == report_id
        and manifest["actual_credential_scanned"] is True
        and manifest["credential_hits"] == 0
        and manifest["wallet_runtime_credentials_or_base_weights_published"] is False
        and manifest["all_original_member_SHA_and_roundtrips_verified"] is True,
        "actual_closed_publication_manifest_join",
    )
    return manifest


def capture_sources(root, p, runner):
    head = runner(root, "rev-parse", "HEAD").stdout.decode().strip()
    members = []
    for name in (SCRIPT, DEPENDENCY):
        item = descriptor(root, name)
        committed = runner(root, "show", head + ":" + name).stdout
        require(
            hashlib.sha256(committed).hexdigest() == item["sha256"],
            "operator_sources_committed_before_start",
        )
        members.append(item)
    return p.record(
        "fast_publication_source_capture",
        head_commit=head,
        sources=members,
        automatic_retry=False,
        old_workflow_not_impersonated=True,
    )


def wait_for_closure(root, p, *, wait, sleeper=time.sleep):
    paths = (
        root / p.OUTPUT / "report.json",
        root / p.OUTPUT / "manifest.json",
        p.PARENT_ROOT / (p.MATERIALS + "_publication/materials/publication_manifest.json"),
    )
    failure = root / p.OUTPUT / "execution_failure.json"
    while not all(path.exists() for path in paths):
        require(not failure.exists(), "actual_execution_failed_no_publication")
        require(wait, "actual_result_and_closed_material_manifest_not_ready")
        sleeper(10)
    require(not failure.exists(), "actual_execution_failure_not_relabelled_complete")
    return paths


def inputs(root, p):
    def read(name, kind):
        return read_record(root, name, kind, p)

    output, material = p.OUTPUT, p.MATERIALS
    report = read(output + "/report.json", "execution_report")
    closed = read(output + "/manifest.json", "evaluation_manifest")
    frozen = read(output + "/preparation/execution_freeze.json", "execution_freeze")
    authority = read(
        output + "/preparation/fast_execution_authority.json", "fast_execution_authority"
    )
    decision = read(output + "/decision.json", "actual_direction_decision")
    generation = read(material + "/generation_report.json", "material_generation_report")
    gate = read(material + "/material_gate.json", "material_gate")
    original_gate = read_record(p.PARENT_ROOT, material + "/material_gate.json", "material_gate", p)
    completion = read(material + "/completion_freeze.json", "kernel_completion_freeze")
    original = read(material + "/freeze.json", "study_freeze")
    authorization = read(material + "/authorization.json", "kernel_completion_authorization")
    require(
        report["actual_complete"] is True
        and report["status"] in {"COMPLETE_NO_POSITIVE_DIRECTION", "COMPLETE_FIXED_CONFIRMATION"}
        and closed["report_id"] == report["id"]
        and closed["phase"] == "fixed_kernel_value_execution"
        and decision["actual_complete"] is True
        and decision["id"] == report["decision_id"],
        "actual_complete_fast_execution_and_producer_manifest",
    )
    require(
        gate == original_gate
        and gate["id"] == p.EXPECTED_GATE
        and gate["training_gate"] == gate["material_gate"] == gate["dose_gate"] == "PASS"
        and gate["kernel_id"]
        == authority["original_kernel_id"]
        == frozen["kernel_id"]
        == report["kernel_id"]
        == p.EXPECTED_KERNEL
        and generation["id"]
        == gate["generation_report_id"]
        == authority["original_generation_report_id"]
        and generation["registered_sessions"] == generation["finished_sessions"] == 10240
        and generation["generation_closed"] is True
        and generation["no_inflight_requests"] is True,
        "actual_original_complete_gate_and_exact_kernel_lineage",
    )
    require(
        authority["execution_freeze_id"] == frozen["id"]
        and authority["original_material_gate_id"] == gate["id"]
        and authority["completion_freeze_id"] == completion["id"]
        and authority["original_registry_freeze_id"] == original["id"] == report["study_freeze_id"]
        and frozen["study_freeze_id"] == original["id"]
        and frozen["output_directory"] == output
        and authority["execution_only_performance_revision"] is True
        and authority["numerical_or_scientific_conditions_changed"] is False
        and authority["actual_full_original_kernel_ID_equal"] is True
        and authority["original_parent_reports_relabelled"] is False
        and authority["training_configuration_id"]
        == frozen["training_configuration"]["id"]
        == report["training_configuration_id"]
        and completion["authorization_id"] == authorization["id"]
        and authorization["amended_combined_token_cap"] == 350000000
        and authorization["amendment_after_parent_budget_stop"] is True
        and authorization["unamended_preregistration_claimed"] is False,
        "separate_budget_amendment_and_execution_only_revision",
    )
    require(
        not (p.PARENT_ROOT / material / "student_execution/execution_started.json").exists(),
        "parent_not_a_second_Student_execution",
    )
    receipt = frozen["material_input_receipt"]
    require(
        receipt["path"] == output + "/preparation/material_input_receipt.json"
        and descriptor(root, receipt["path"], RECEIPT_LIMIT) == receipt,
        "actual_content_bound_preflight_receipt",
    )
    approved = [("A", arm, seed) for arm in p.ARMS for seed in p.SEEDS]
    if report["status"] == "COMPLETE_FIXED_CONFIRMATION":
        require(decision["selected_arm"] in ("plus", "minus"), "one_actual_confirmation_direction")
        approved += [
            ("B", arm, seed) for arm in ("alpha0", decision["selected_arm"]) for seed in p.SEEDS
        ]
    else:
        require(decision["selected_arm"] == "alpha0", "actual_no_move_selection")
    require(report["actual_training_runs"] == len(approved), "actual_final_adapter_denominator")
    leaf = PurePosixPath(output).name
    adapters = [
        f"{leaf}/training/{pool}_{arm}_{seed}/final_adapter.safetensors"
        for pool, arm, seed in approved
    ]
    manifest_path = material + "_publication/materials/publication_manifest.json"
    material_manifest = read_record(p.PARENT_ROOT, manifest_path, "publication_manifest", p)
    validate_manifest(
        material_manifest, stage="materials", source_root=material, report_id=generation["id"]
    )
    return dict(
        report=report,
        producer_manifest=closed,
        frozen=frozen,
        authority=authority,
        decision=decision,
        generation=generation,
        gate=gate,
        completion=completion,
        original=original,
        authorization=authorization,
        material_manifest=material_manifest,
        material_receipt=receipt,
        approved_adapter_paths=adapters,
    )


def copy_materials(root, p, manifest):
    """Read only sealed containers/pages; preserve exact bytes and old closure IDs."""
    relative = p.MATERIALS + "_publication/materials"
    destination = root / relative
    require(
        not destination.exists() and not any(part.is_symlink() for part in destination.parents),
        "exclusive_material_archive_copy_destination",
    )
    rows = list(publication_names(manifest))
    manifest_bytes = descriptor(p.PARENT_ROOT / relative, "publication_manifest.json")
    require(
        manifest_bytes["sha256"] == hashlib.sha256(p.encode(manifest)).hexdigest(),
        "parent_material_manifest_unchanged_before_copy",
    )
    rows.append((manifest_bytes, SMALL_LIMIT))
    destination.mkdir(parents=True, exist_ok=False)
    members, signatures = [], {}
    for row, limit in rows:
        name = relative + "/" + row["path"]
        source = regular(p.PARENT_ROOT, name, limit)
        before = signature(source)
        target = destination / row["path"]
        digest, count = hashlib.sha256(), 0
        with source.open("rb") as incoming, target.open("xb") as outgoing:
            for block in iter(lambda: incoming.read(1024 * 1024), b""):
                digest.update(block)
                count += len(block)
                outgoing.write(block)
            outgoing.flush()
            os.fsync(outgoing.fileno())
        require(
            signature(source) == before
            and count == row["bytes"]
            and digest.hexdigest() == row["sha256"]
            and target.stat().st_size == count,
            "copied_sealed_original_stream_exact_SHA_and_length",
        )
        members.append({"path": name, "bytes": count, "sha256": digest.hexdigest()})
        signatures[name] = signature(target)
    return members, signatures


def collect_results(root, p, manifest, report):
    namespace = str(PurePosixPath(p.OUTPUT).parent)
    validate_manifest(manifest, stage="results", source_root=namespace, report_id=report["id"])
    relative = namespace + "_publication/results"
    require(
        read_record(root, relative + "/publication_manifest.json", "publication_manifest", p)
        == manifest,
        "actual_results_manifest_matches_sealer_return",
    )
    members, signatures = [], {}
    for row, limit in publication_names(manifest):
        name = relative + "/" + row["path"]
        path = regular(root, name, limit)
        before = signature(path)
        actual = descriptor(root, name, limit)
        require(
            all(actual[key] == row[key] for key in ("bytes", "sha256"))
            and signature(path) == before,
            "closed_results_manifest_exact_bytes",
        )
        members.append(actual)
        signatures[name] = before
    name = relative + "/publication_manifest.json"
    members.append(descriptor(root, name))
    signatures[name] = signature(root / name)
    return members, signatures


def summary(data, terminal):
    report, generation, gate, authority = (
        data["report"],
        data["generation"],
        data["gate"],
        data["authority"],
    )

    def value(item):
        return "未提供／未测量" if item is None else json.dumps(item, ensure_ascii=False)

    lines = [
        "# Fixed-kernel：预算补完及独立快速执行的实际结果",
        "",
        "本页汇总实际报告，不将封存成功、运行结束或训练完成等同于正科学效应。",
        "预算在旧批次停止后经用户授权由合计 250,000,000 提高至 350,000,000 tokens；",
        "该补完是预算修订，不是原始未修订预注册方案。旧 STOP 报告和历史扣账保持不变。",
        "",
        "## 完整材料与执行来源",
        "",
        f"- 原始 10,240 槽位最终 finished：{value(generation.get('finished_sessions'))}。",
        "- 已完成的 9,968 槽位保留；272 槽位补完时复用 404 个已认证响应前缀，不重采旧响应。",
        f"- 新增 HTTP 请求：{value(generation.get('new_HTTP_request_count'))}；"
        f"本轮补完保守 token 扣账：{value(generation.get('completion_conservative_debit'))}。",
        f"- 原材料门：`{gate['id']}`，{gate['training_gate']}；原 kernel：`{gate['kernel_id']}`。",
        f"- 独立 execution-only authority：`{authority['id']}`。",
        "- 正式 Student 由新 fast-execution 源码执行；不是旧 completion 主进程直接执行。",
        "- 仅改不可变材料所有权和内容绑定验证收据复用；不重编码、不再采集，",
        "  Qwen/LoRA/AdamW/loss、400 updates、抽样、SEEDS 和 greedy 评估条件未改变。",
        "- 新完整预检得到的实际 kernel ID 与原材料门严格相同；这不是用新标签替换旧记录。",
        "",
        "## 正式 Student 实测",
        "",
    ]
    for key in (
        "status",
        "actual_training_runs",
        "actual_evaluation_sessions",
        "confirmation_sessions",
        "independent_positive_effect_confirmed",
    ):
        lines.append(f"- `{key}`：{value(report.get(key))}。")
    decision = data["decision"]
    lines += [
        f"- 开发集选择：{value(decision.get('selected_arm'))}；"
        f"配对均值增益：{value(decision.get('paired_mean_gain'))}。",
        f"- 实际执行报告：`{report['id']}`。",
        "- 若未执行独立确认分支，则不推断该分支效果；工程检查不计入正式训练。",
        "",
        "## 已封存与发布边界",
        "",
        f"- 独立发布终态：`{terminal['id']}`。",
        f"- 原完整材料 manifest：`{data['material_manifest']['id']}`；仅按清单复制已封存字节，",
        "  不重新扫描原 session/package 树，不重新秘密扫描或封装原材料。",
        f"- 新结果 manifest：`{data['results_manifest']['id']}`；"
        "由既有 publisher 对实际结果封存一次。",
        "- 不写造旧 completion_workflow terminal，也不依赖被暂停主进程的 exit 回执。",
        "- Git 只暂存精确清单中的归档、index 页面、少量权威报告及本页，",
        "  使用 --sparse --force 处理忽略规则；不直接加入钱包、.env、日志或基础模型权重。",
        f"- 目标 {REMOTE} main，单次普通非强制 push；本页不预先宣称远端成功。",
        "",
    ]
    return "\n".join(lines).encode()


def finalize(root, p, *, wait=False, sealer=None, runner=git, sleeper=time.sleep):
    root = Path(root).absolute()
    require(not any(part.is_symlink() for part in (root, *root.parents)), "regular_fast_root")
    require(
        root != p.PARENT_ROOT
        and runner(root, "branch", "--show-current").stdout.decode().strip() == p.BRANCH,
        "independent_fast_execution_branch",
    )
    require(
        not runner(root, "diff", "--cached", "--name-only", "-z").stdout,
        "preexisting_staged_changes_refused",
    )
    runtime = root / p.RUNTIME
    runtime.mkdir(parents=True, exist_ok=True)
    require(not any(part.is_symlink() for part in (runtime, *runtime.parents)), "regular_runtime")
    with (runtime / "fast_publication_operator.lock").open("xb") as lock:
        lock.write(str(os.getpid()).encode())
    source = capture_sources(root, p, runner)
    workflow = p.OUTPUT + "_publication_workflow"
    started = p.record(
        "fast_publication_operator_started",
        pid=os.getpid(),
        started_at=p.now(),
        source_capture=source,
        wait=wait,
        poll_seconds=10,
        maximum_seal_attempts=1,
        maximum_push_attempts=1,
        old_waiter_or_old_CPU_modified=False,
        actual_result_execution_origin="independent_fast_execution_revision",
    )
    p.write_once(root / workflow / "started.json", started)
    phase, sealed = "waiting_for_real_closures", False
    try:
        wait_for_closure(root, p, wait=wait, sleeper=sleeper)
        phase = "real_authority_and_receipt_binding"
        data = inputs(root, p)
        for member in source["sources"]:
            require(
                descriptor(root, member["path"]) == member, "committed_operator_source_unchanged"
            )
        if sealer is None:
            sealer = importlib.import_module(
                "trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value.publish"
            ).seal_stage
        namespace, leaf = str(PurePosixPath(p.OUTPUT).parent), PurePosixPath(p.OUTPUT).name
        phase = "new_actual_results_seal_once"
        result = sealer(
            root,
            p.DATA_ROOT,
            "results",
            source_output=namespace,
            allowlist=[leaf],
            report_path=leaf + "/report.json",
            approved_adapter_paths=data["approved_adapter_paths"],
        )
        p.checked(result, "publication_manifest")
        sealed = True
        phase = "copy_existing_complete_material_archive"
        old_members, old_signatures = copy_materials(root, p, data["material_manifest"])
        result_members, result_signatures = collect_results(root, p, result, data["report"])
        data["results_manifest"] = result
        terminal = p.record(
            "fast_execution_publication_lineage",
            status="COMPLETE_ACTUAL_FAST_EXECUTION_AND_SEALS",
            started_id=started["id"],
            source_capture_id=source["id"],
            execution_authority_id=data["authority"]["id"],
            execution_freeze_id=data["frozen"]["id"],
            material_validation_receipt=data["material_receipt"],
            original_material_gate_id=data["gate"]["id"],
            original_kernel_id=data["gate"]["kernel_id"],
            completion_freeze_id=data["completion"]["id"],
            budget_authorization_id=data["authorization"]["id"],
            actual_execution_report_id=data["report"]["id"],
            actual_execution_complete=True,
            materials_publication_manifest_id=data["material_manifest"]["id"],
            results_publication_manifest_id=result["id"],
            original_material_reseals=0,
            new_results_seal_attempts=1,
            old_completion_workflow_terminal_fabricated=False,
            numerical_or_scientific_conditions_changed=False,
            ended_at=p.now(),
        )
        p.write_once(root / workflow / "terminal.json", terminal)
        summary_path = root / SUMMARY
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        require(
            not any(part.is_symlink() for part in summary_path.parents), "regular_summary_parent"
        )
        with summary_path.open("xb") as stream:
            stream.write(summary(data, terminal))
        members, signatures = old_members + result_members, {**old_signatures, **result_signatures}
        small_names = [workflow + "/started.json", workflow + "/terminal.json", SUMMARY]
        small_names += [
            p.OUTPUT + "/" + name
            for name in (
                "report.json",
                "decision.json",
                "preparation/execution_freeze.json",
                "preparation/fast_execution_authority.json",
            )
        ]
        small_names += [
            p.MATERIALS + "/" + name
            for name in (
                "generation_report.json",
                "material_gate.json",
                "completion_freeze.json",
                "authorization.json",
            )
        ]
        for name in small_names:
            members.append(descriptor(root, name))
            signatures[name] = signature(root / name)
        require(len({row["path"] for row in members}) == len(members), "unique_final_git_allowlist")
        phase = "exact_git_publication"
        parent = runner(root, "rev-parse", "HEAD").stdout.decode().strip()
        runner(root, "merge-base", "--is-ancestor", source["head_commit"], "HEAD")
        inventory = p.record(
            "fast_execution_git_publication_inventory",
            parent_commit=parent,
            lineage_terminal_id=terminal["id"],
            members=members,
            exact_sparse_force_allowlist=True,
            force_push=False,
            remote=REMOTE,
            refspec=REFSPEC,
            archive_copy_or_seal_completed=True,
        )
        inventory_name = workflow + "/final_publication_inventory.json"
        p.write_once(root / inventory_name, inventory)
        members.append(descriptor(root, inventory_name))
        signatures[inventory_name] = signature(root / inventory_name)
        names = sorted(row["path"] for row in members)
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
            require(
                signature(path) == signatures[row["path"]], "selected_bytes_changed_after_binding"
            )
        runner(root, "diff", "--quiet", "--", *sorted(staged))
        require(
            runner(root, "rev-parse", "HEAD").stdout.decode().strip() == parent,
            "parent_unchanged_before_commit",
        )
        runner(
            root,
            "commit",
            "-m",
            "Publish complete kernel materials and independent fast execution results",
        )
        commit = runner(root, "rev-parse", "HEAD").stdout.decode().strip()
        try:
            runner(root, "push", REMOTE, REFSPEC)
        except Exception as error:
            p.write_once(
                runtime / "fast_publication_git_receipt.json",
                p.record(
                    "fast_execution_git_publication_receipt",
                    status="COMMITTED_PUSH_FAILED",
                    commit=commit,
                    parent_commit=parent,
                    inventory_id=inventory["id"],
                    remote=REMOTE,
                    refspec=REFSPEC,
                    force_push=False,
                    automatic_retry=False,
                    error_type=type(error).__name__,
                ),
            )
            raise
        receipt = p.record(
            "fast_execution_git_publication_receipt",
            status="COMMITTED_AND_PUSHED",
            commit=commit,
            parent_commit=parent,
            inventory_id=inventory["id"],
            remote=REMOTE,
            refspec=REFSPEC,
            force_push=False,
            automatic_retry=False,
        )
        p.write_once(runtime / "fast_publication_git_receipt.json", receipt)
        return receipt
    except BaseException as error:
        p.write_once(
            runtime / "fast_publication_operator_failure.json",
            p.record(
                "fast_publication_operator_failure",
                phase=phase,
                error_type=type(error).__name__,
                reason=str(error)[:2000],
                results_seal_completed=sealed,
                started_id=started["id"],
                partial_artifacts_retained=True,
                automatic_retry=False,
                ended_at=p.now(),
            ),
        )
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--wait", action="store_true")
    args = parser.parse_args()
    root = args.code_root.absolute()
    sys.path[:0] = [str(root / "trusted_data_synthesis/src"), str(root / "raw_financial_data_lake")]
    package = "trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value."
    protocol, study = (
        importlib.import_module(package + "protocol"),
        importlib.import_module(package + "fast_study"),
    )
    require(Path(study.__file__).resolve().is_relative_to(root), "correct_fast_execution_module")
    p = SimpleNamespace(
        **{
            name: getattr(study, name)
            for name in (
                "OUTPUT",
                "MATERIALS",
                "RUNTIME",
                "PARENT_ROOT",
                "DATA_ROOT",
                "BRANCH",
                "EXPECTED_GATE",
                "EXPECTED_KERNEL",
            )
        },
        **{
            name: getattr(protocol, name)
            for name in (
                "record",
                "checked",
                "read_json",
                "write_once",
                "encode",
                "now",
                "ARMS",
                "SEEDS",
            )
        },
    )
    print(p.encode(finalize(root, p, wait=args.wait)).decode(), flush=True)


if __name__ == "__main__":
    main()
