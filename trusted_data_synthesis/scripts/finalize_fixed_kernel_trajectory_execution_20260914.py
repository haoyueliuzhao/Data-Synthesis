"""One-shot publisher for actual fresh trajectory-execution results.

Wait only for the new execution's real report/manifest and the already closed
original material archive. Never wait for or fabricate an old workflow terminal,
resume a Student, rebuild a kernel, re-encode tokens, or repack old materials.
"""

import argparse
import hashlib
import importlib
import importlib.util
import json
import os
import sys
import time
from pathlib import Path, PurePosixPath
from types import SimpleNamespace

_SPEC = importlib.util.spec_from_file_location(
    "trajectory_publication_primitives",
    Path(__file__).with_name("finalize_fixed_kernel_fast_execution_20260914.py"),
)
_FAST = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_FAST)
regular, descriptor, read_record, git = (
    _FAST.regular,
    _FAST.descriptor,
    _FAST.read_record,
    _FAST.git,
)
signature, publication_names = _FAST.signature, _FAST.publication_names
validate_manifest, collect_results = _FAST.validate_manifest, _FAST.collect_results
REMOTE, REFSPEC = _FAST.REMOTE, _FAST.REFSPEC
SMALL_LIMIT, SHARD_LIMIT = _FAST.SMALL_LIMIT, _FAST.SHARD_LIMIT
PRODUCER_MANIFEST_LIMIT = 128 * 1024 * 1024
SCRIPT = "trusted_data_synthesis/scripts/finalize_fixed_kernel_trajectory_execution_20260914.py"
SOURCES = (SCRIPT, _FAST.SCRIPT, _FAST.DEPENDENCY)
SUMMARY = "trusted_data_synthesis/docs/fixed_kernel_trajectory_execution_actual_results_20260914.md"
EXPECTED_MATERIAL_MANIFEST = (
    "publication_manifest:457d6009f338c172a665ef177ce1ebb2fd7f528e508b1918cc18bc50212a4ae0"
)


def require(condition, code):
    if not condition:
        raise ValueError("trajectory_publication." + code)


def capture_sources(root, p, runner):
    head = runner(root, "rev-parse", "HEAD").stdout.decode().strip()
    sources = []
    for name in SOURCES:
        item = descriptor(root, name)
        committed = runner(root, "show", head + ":" + name).stdout
        require(
            hashlib.sha256(committed).hexdigest() == item["sha256"],
            "operator_and_imported_helpers_committed_before_start",
        )
        sources.append(item)
    return p.record(
        "trajectory_publication_source_capture",
        head_commit=head,
        sources=sources,
        automatic_retry=False,
        old_workflow_not_impersonated=True,
    )


def wait_for_closure(root, p, *, wait, sleeper=time.sleep):
    paths = (
        root / p.OUTPUT / "report.json",
        root / p.OUTPUT / "manifest.json",
        p.MATERIALS_ROOT / (p.MATERIALS + "_publication/materials/publication_manifest.json"),
    )
    failure = root / p.OUTPUT / "execution_failure.json"
    while not all(path.exists() for path in paths):
        require(not failure.exists(), "actual_execution_failed_no_publication")
        require(wait, "actual_result_and_closed_material_manifest_not_ready")
        sleeper(10)
    require(not failure.exists(), "actual_execution_failure_not_relabelled_complete")
    return paths


def _bound_record(root, reference, kind, p):
    require(descriptor(root, reference["path"]) == reference, "exact_small_metadata_descriptor")
    return read_record(root, reference["path"], kind, p)


def read_producer_manifest(root, relative, p):
    """The unpaged producer inventory may be larger than a 4 MiB index page."""
    raw = regular(root, relative, PRODUCER_MANIFEST_LIMIT).read_bytes()
    value = p.checked(json.loads(raw), "evaluation_manifest")
    require(p.encode(value) == raw, "canonical_bounded_producer_manifest")
    return value


def inputs(root, p):
    """Join new terminal evidence to original authority, without raw-data scans."""
    output = p.OUTPUT
    read = lambda name, kind: read_record(root, output + "/" + name, kind, p)
    report = read("report.json", "execution_report")
    closed = read_producer_manifest(root, output + "/manifest.json", p)
    frozen = read("preparation/execution_freeze.json", "execution_freeze")
    authority = read(
        "preparation/trajectory_execution_authority.json", "trajectory_execution_authority"
    )
    decision = read("decision.json", "actual_direction_decision")
    material = lambda name, kind: read_record(p.MATERIALS_ROOT, p.MATERIALS + "/" + name, kind, p)
    generation = material("generation_report.json", "material_generation_report")
    gate = material("material_gate.json", "material_gate")
    original = material("freeze.json", "study_freeze")
    completion = material("completion_freeze.json", "kernel_completion_freeze")
    authorization = material("authorization.json", "kernel_completion_authorization")
    require(
        report["actual_complete"] is True
        and report["status"] in {"COMPLETE_NO_POSITIVE_DIRECTION", "COMPLETE_FIXED_CONFIRMATION"}
        and closed["report_id"] == report["id"]
        and closed["phase"] == "fixed_kernel_value_execution"
        and decision["actual_complete"] is True
        and decision["id"] == report["decision_id"],
        "actual_complete_trajectory_execution_and_producer_manifest",
    )
    require(
        gate["id"]
        == authority["original_material_gate_id"]
        == frozen["original_material_gate_id"]
        == p.EXPECTED_GATE
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
        "closed_original_material_gate_and_kernel_lineage",
    )
    require(
        authority["execution_freeze_id"] == frozen["id"]
        and authority["completion_freeze_id"] == completion["id"]
        and authority["original_registry_freeze_id"]
        == original["id"]
        == frozen["study_freeze_id"]
        == report["study_freeze_id"]
        and frozen["output_directory"] == output
        and frozen["input_root"] == str(p.PARENT_ROOT)
        and authority["parent_source_root"] == str(p.PARENT_ROOT)
        and authority["original_material_source_root"] == str(p.MATERIALS_ROOT)
        and authority["training_configuration_id"]
        == frozen["training_configuration"]["id"]
        == report["training_configuration_id"]
        and completion["authorization_id"] == authorization["id"]
        and authorization["amended_combined_token_cap"] == 350000000
        and authorization["amendment_after_parent_budget_stop"] is True
        and authorization["unamended_preregistration_claimed"] is False,
        "separate_successor_and_original_budget_amendment",
    )
    require(
        authority["source_material_validation_reused"] is True
        and authority["original_kernel_ID_recomputed"] is False
        and authority["dropout_correlation_changed"] is True
        and authority["bitwise_equivalence_claimed"] is False
        and authority["fresh_Students_from_original_base_and_seed"] is True
        and authority["parent_partial_Students_or_optimizers_resumed"] is False
        and authority["parent_incomplete_run_claimed_complete"] is False
        and authority["original_parent_reports_relabelled"] is False
        and frozen["dropout_correlation_changed"] is True
        and frozen["bitwise_equivalence_claimed"] is False
        and frozen["parent_partial_Students_resumed"] is False,
        "fresh_restart_shared_prefix_dropout_not_bitwise_replay",
    )
    parent = _bound_record(p.PARENT_ROOT, frozen["parent_execution_freeze"], "execution_freeze", p)
    require(
        parent["id"]
        == frozen["parent_execution_freeze_id"]
        == authority["parent_execution_freeze_id"]
        and parent["kernel_id"] == p.EXPECTED_KERNEL
        and parent["material_verification"] == frozen["material_verification"]
        and parent["material_input_receipt"] == frozen["material_input_receipt"]
        and authority["parent_training_configuration_id"]
        == frozen["parent_training_configuration_id"]
        == parent["training_configuration"]["id"],
        "exact_parent_freeze_and_reused_material_receipt",
    )
    cached = frozen["trajectory_cache"]
    require(
        authority["trajectory_cache"] == cached
        and cached["cache_root"] == output + "/preparation/trajectory_cache"
        and cached["manifest"]["path"] == cached["cache_root"] + "/manifest.json",
        "exact_new_trajectory_cache_location",
    )
    cache = _bound_record(root, cached["manifest"], "trajectory_material_cache", p)
    require(
        cache["id"] == cached["manifest_id"] == authority["trajectory_cache_id"]
        and cache["kernel_id"] == p.EXPECTED_KERNEL
        and cache["parent_execution_freeze_id"] == parent["id"]
        and cache["material_verification_id"]
        == frozen["material_verification"]["id"]
        == authority["source_material_verification_id"]
        and cache["pool_budgets"] == frozen["trajectory_pool_budgets"]
        and cache["source_material_budgets"]
        == frozen["source_material_budgets"]
        == frozen["material_verification"]["pool_budgets"]
        and cache["dropout_random_trajectory_changed"] is True
        and cache["stochastic_or_bitwise_training_equivalence_claimed"] is False,
        "actual_cache_manifest_original_authority_and_new_execution_budget",
    )
    for pool in ("A", "B"):
        actual, source = cache["pool_budgets"][pool], cache["source_material_budgets"][pool]
        require(
            all(
                actual[field + suffix] == source[field + suffix]
                for field in ("packages", "target_tokens")
                for suffix in ("_per_epoch", "_all_epochs")
            )
            and all(
                actual[field + "_all_epochs"] == 10 * actual[field + "_per_epoch"]
                for field in ("packages", "rows", "target_tokens", "sequence_tokens")
            )
            and actual["rows_per_epoch"] <= source["rows_per_epoch"]
            and actual["sequence_tokens_per_epoch"] <= source["sequence_tokens_per_epoch"],
            "original_targets_packages_ten_passes_and_actual_reduced_forward_budget",
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
    adapters, training = [], []
    for pool, arm, seed in approved:
        relative = "training/" + f"{pool}_{arm}_{seed}"
        trained = read(relative + "/report.json", "training_report")
        require(
            trained["actual_complete"] is True
            and trained["status"] == "COMPLETE_FINAL_CHECKPOINT"
            and (trained["pool"], trained["arm"], trained["seed"]) == (pool, arm, seed)
            and trained["kernel_id"] == p.EXPECTED_KERNEL
            and trained["training_configuration_id"] == report["training_configuration_id"]
            and trained["trajectory_cache_id"] == cache["id"]
            and trained["material_verification_id"] == cache["material_verification_id"]
            and trained["actual_budget"] == cache["pool_budgets"][pool]
            and trained["source_material_budget"] == cache["source_material_budgets"][pool]
            and trained["optimizer_updates"] == 400
            and trained["epochs_completed"] == 10
            and trained["final_adapter_restored_identity_verified"] is True,
            "actual_new_final_Student_and_exact_executed_cache_budget",
        )
        training.append(trained["id"])
        adapters.append(f"{leaf}/{relative}/final_adapter.safetensors")
    old_manifest = read_record(
        p.MATERIALS_ROOT,
        p.MATERIALS + "_publication/materials/publication_manifest.json",
        "publication_manifest",
        p,
    )
    require(
        old_manifest["id"] == p.EXPECTED_MATERIAL_MANIFEST, "exact_already_closed_material_archive"
    )
    validate_manifest(
        old_manifest, stage="materials", source_root=p.MATERIALS, report_id=generation["id"]
    )
    return dict(
        report=report,
        producer_manifest=closed,
        frozen=frozen,
        authority=authority,
        decision=decision,
        generation=generation,
        gate=gate,
        original=original,
        completion=completion,
        authorization=authorization,
        material_manifest=old_manifest,
        trajectory_manifest=cache,
        material_receipt=frozen["material_input_receipt"],
        approved_adapter_paths=adapters,
        actual_training_report_ids=training,
    )


def copy_materials(root, p, manifest):
    # The material archive belongs to completion, not to the paused fast process.
    scope = SimpleNamespace(**{**vars(p), "PARENT_ROOT": p.MATERIALS_ROOT})
    return _FAST.copy_materials(root, scope, manifest)


def summary(data, terminal):
    report, cache = data["report"], data["trajectory_manifest"]
    value = lambda item: "未提供／未测量" if item is None else json.dumps(item, ensure_ascii=False)
    lines = [
        "# Fixed-kernel：轨迹合并新执行的实际结果",
        "",
        "以下仅汇总实际报告；训练完成或归档成功不等于存在正科学效应。",
        "旧响应行训练经用户授权暂停。新执行从相同基座与配对种子重新初始化 LoRA/AdamW，",
        "未恢复旧部分 Student 或 optimizer，也未将旧未完成运行标记为完成。",
        "共享精确因果前缀保留监督 token、原包权重、任务与 400 次全局更新；",
        "dropout 概率仍为 0.05，但共享前缀改变随机掩码关联，因此不是逐位等价重放。",
        "确定性无 dropout 的损失／梯度控制不构成随机训练结果等价的证明。",
        "",
        "## 材料来源与实际计算量",
        "",
        f"- 原始完整槽位：{value(data['generation'].get('finished_sessions'))}/10,240；"
        f"原 kernel：`{data['gate']['kernel_id']}`。",
        "- 原材料预算曾由 250,000,000 修订至 350,000,000 tokens；不是原始未修订预注册方案。",
        "- 复用已关闭材料与验证收据，不重采样、不重编码、不重新构造 kernel。",
        f"- 新轨迹 cache：`{cache['id']}`；新 authority：`{data['authority']['id']}`。",
    ]
    for pool in ("A", "B"):
        source, actual = cache["source_material_budgets"][pool], cache["pool_budgets"][pool]
        lines.append(
            f"- {pool} 池每轮原响应行／实际 forward：{source['rows_per_epoch']} / {actual['rows_per_epoch']}；"
            f"原序列／实际序列 token：{source['sequence_tokens_per_epoch']} / {actual['sequence_tokens_per_epoch']}；"
            f"监督 token 保持 {actual['target_tokens_per_epoch']}。"
        )
    lines += [
        "- 上述计算量减少不直接等于相同倍率的墙钟提速；未实测的收益不作承诺。",
        "",
        "## 正式结果",
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
    lines += [
        f"- 开发选择：{value(data['decision'].get('selected_arm'))}；"
        f"配对均值增益：{value(data['decision'].get('paired_mean_gain'))}。",
        "- 未执行的独立确认分支不推断效果；工程控制不计入正式 Student。",
        "",
        "## 单次封存与发布",
        "",
        f"- 实际执行报告：`{report['id']}`；独立发布终态：`{terminal['id']}`。",
        f"- 原材料 manifest：`{data['material_manifest']['id']}`；仅复制其已封存容器和索引，未重封材料。",
        f"- 新结果 manifest：`{data['results_manifest']['id']}`；新执行叶目录由现有 publisher 封存一次。",
        "- 只 Git 暂存精确清单中的密封归档、索引、权威小报告和本文；",
        "  不直接暂存 runtime、钱包、环境文件、原始材料树、基础模型或未授权 adapter。",
        f"- 目标 {REMOTE} main；单次普通非强制 push，失败保留且不自动重试。",
        "- 本文不预先宣称远端成功；成功或失败以单独 Git receipt 为准。",
        "",
    ]
    return "\n".join(lines).encode()


def finalize(root, p, *, wait=False, sealer=None, runner=git, sleeper=time.sleep):
    root = Path(root).absolute()
    require(not any(part.is_symlink() for part in (root, *root.parents)), "regular_trajectory_root")
    require(
        root not in (p.PARENT_ROOT, p.MATERIALS_ROOT)
        and runner(root, "branch", "--show-current").stdout.decode().strip() == p.BRANCH,
        "independent_trajectory_execution_branch",
    )
    require(
        not runner(root, "diff", "--cached", "--name-only", "-z").stdout,
        "preexisting_staged_changes_refused",
    )
    runtime = root / p.RUNTIME
    runtime.mkdir(parents=True, exist_ok=True)
    require(not any(part.is_symlink() for part in (runtime, *runtime.parents)), "regular_runtime")
    with (runtime / "trajectory_publication_operator.lock").open("xb") as lock:
        lock.write(str(os.getpid()).encode())
    source = capture_sources(root, p, runner)
    workflow = p.OUTPUT + "_publication_workflow"
    started = p.record(
        "trajectory_publication_operator_started",
        pid=os.getpid(),
        started_at=p.now(),
        source_capture=source,
        wait=wait,
        poll_seconds=10,
        maximum_seal_attempts=1,
        maximum_push_attempts=1,
        old_workflow_terminal_required=False,
        actual_result_execution_origin="fresh_trajectory_prefix_union_execution",
    )
    p.write_once(root / workflow / "started.json", started)
    phase, sealed = "waiting_for_real_closures", False
    try:
        wait_for_closure(root, p, wait=wait, sleeper=sleeper)
        phase = "actual_successor_authority_and_cache_binding"
        data = inputs(root, p)
        for member in source["sources"]:
            require(
                descriptor(root, member["path"]) == member, "committed_operator_sources_unchanged"
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
        phase = "copy_already_closed_original_material_archive"
        old_members, old_signatures = copy_materials(root, p, data["material_manifest"])
        result_members, result_signatures = collect_results(root, p, result, data["report"])
        data["results_manifest"] = result
        terminal = p.record(
            "trajectory_execution_publication_lineage",
            status="COMPLETE_ACTUAL_TRAJECTORY_EXECUTION_AND_SEALS",
            started_id=started["id"],
            source_capture_id=source["id"],
            execution_authority_id=data["authority"]["id"],
            execution_freeze_id=data["frozen"]["id"],
            parent_execution_freeze_id=data["frozen"]["parent_execution_freeze_id"],
            material_validation_receipt=data["material_receipt"],
            original_material_gate_id=data["gate"]["id"],
            original_kernel_id=data["gate"]["kernel_id"],
            completion_freeze_id=data["completion"]["id"],
            budget_authorization_id=data["authorization"]["id"],
            trajectory_cache_id=data["trajectory_manifest"]["id"],
            source_material_budgets=data["trajectory_manifest"]["source_material_budgets"],
            actual_trajectory_budgets=data["trajectory_manifest"]["pool_budgets"],
            actual_training_report_ids=data["actual_training_report_ids"],
            actual_execution_report_id=data["report"]["id"],
            actual_execution_complete=True,
            materials_publication_manifest_id=data["material_manifest"]["id"],
            results_publication_manifest_id=result["id"],
            original_material_reseals=0,
            new_results_seal_attempts=1,
            old_workflow_terminal_fabricated=False,
            original_material_validation_reused=True,
            original_kernel_ID_recomputed=False,
            fresh_Students_from_original_base_and_seed=True,
            parent_partial_states_resumed=False,
            dropout_correlation_changed=True,
            bitwise_equivalence_claimed=False,
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
            stream.flush()
            os.fsync(stream.fileno())
        members = old_members + result_members
        signatures = {**old_signatures, **result_signatures}
        small_names = [workflow + "/started.json", workflow + "/terminal.json", SUMMARY]
        small_names += [
            p.OUTPUT + "/" + name
            for name in (
                "report.json",
                "decision.json",
                "preparation/execution_freeze.json",
                "preparation/trajectory_execution_authority.json",
                "preparation/trajectory_cache/manifest.json",
            )
        ]
        for name in small_names:
            members.append(descriptor(root, name))
            signatures[name] = signature(root / name)
        require(len({row["path"] for row in members}) == len(members), "unique_final_git_allowlist")
        phase = "exact_git_publication"
        parent = runner(root, "rev-parse", "HEAD").stdout.decode().strip()
        # Other separately committed source additions are allowed during training.
        runner(root, "merge-base", "--is-ancestor", source["head_commit"], "HEAD")
        inventory = p.record(
            "trajectory_execution_git_publication_inventory",
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
            "Publish original materials and fresh trajectory execution results",
        )
        commit = runner(root, "rev-parse", "HEAD").stdout.decode().strip()
        try:
            runner(root, "push", REMOTE, REFSPEC)
        except Exception as error:
            p.write_once(
                runtime / "trajectory_publication_git_receipt.json",
                p.record(
                    "trajectory_execution_git_publication_receipt",
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
            "trajectory_execution_git_publication_receipt",
            status="COMMITTED_AND_PUSHED",
            commit=commit,
            parent_commit=parent,
            inventory_id=inventory["id"],
            remote=REMOTE,
            refspec=REFSPEC,
            force_push=False,
            automatic_retry=False,
        )
        p.write_once(runtime / "trajectory_publication_git_receipt.json", receipt)
        return receipt
    except BaseException as error:
        p.write_once(
            runtime / "trajectory_publication_operator_failure.json",
            p.record(
                "trajectory_publication_operator_failure",
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
        importlib.import_module(package + "trajectory_study"),
    )
    require(
        Path(study.__file__).resolve().is_relative_to(root), "correct_trajectory_execution_module"
    )
    p = SimpleNamespace(
        **{
            name: getattr(study, name)
            for name in (
                "OUTPUT",
                "MATERIALS",
                "RUNTIME",
                "PARENT_ROOT",
                "MATERIALS_ROOT",
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
        EXPECTED_MATERIAL_MANIFEST=EXPECTED_MATERIAL_MANIFEST,
    )
    print(p.encode(finalize(root, p, wait=args.wait)).decode(), flush=True)


if __name__ == "__main__":
    main()
