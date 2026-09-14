"""One-shot publication of eight original Students plus the new parallel tail.

Only actual new report/manifest closure and the existing material archive are
awaited. Old report bytes/configuration IDs stay unchanged. Nothing here starts
training, repeats material verification, rebuilds a kernel, or retries a push.
"""

import argparse
import hashlib
import importlib
import importlib.util
import json
import os
import signal
import sys
import time
from pathlib import Path, PurePosixPath
from types import SimpleNamespace

_SPEC = importlib.util.spec_from_file_location(
    "parallel_publication_primitives",
    Path(__file__).with_name("finalize_fixed_kernel_trajectory_execution_20260914.py"),
)
_PRIOR = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_PRIOR)
regular, descriptor, read_record, git = (
    _PRIOR.regular,
    _PRIOR.descriptor,
    _PRIOR.read_record,
    _PRIOR.git,
)
signature, validate_manifest = _PRIOR.signature, _PRIOR.validate_manifest
copy_materials, collect_results = _PRIOR.copy_materials, _PRIOR.collect_results
REMOTE, REFSPEC = _PRIOR.REMOTE, _PRIOR.REFSPEC
SMALL_LIMIT, SHARD_LIMIT = _PRIOR.SMALL_LIMIT, _PRIOR.SHARD_LIMIT
PRODUCER_MANIFEST_LIMIT = _PRIOR.PRODUCER_MANIFEST_LIMIT
EXPECTED_MATERIAL_MANIFEST = _PRIOR.EXPECTED_MATERIAL_MANIFEST
SCRIPT = "trusted_data_synthesis/scripts/finalize_fixed_kernel_parallel_tail_20260914.py"
SOURCES = (SCRIPT, *_PRIOR.SOURCES)
SUMMARY = "trusted_data_synthesis/docs/fixed_kernel_parallel_tail_actual_results_20260914.md"


def require(value, code):
    if not value:
        raise ValueError("parallel_publication." + code)


def capture_sources(root, p, runner):
    head = runner(root, "rev-parse", "HEAD").stdout.decode().strip()
    members = []
    for name in SOURCES:
        value = descriptor(root, name)
        committed = runner(root, "show", head + ":" + name).stdout
        require(
            hashlib.sha256(committed).hexdigest() == value["sha256"],
            "operator_and_imported_helpers_committed_before_start",
        )
        members.append(value)
    return p.record(
        "parallel_publication_source_capture",
        head_commit=head,
        sources=members,
        automatic_retry=False,
        old_workflow_not_impersonated=True,
    )


def retirement_process(pid):
    directory = Path("/proc") / str(pid)
    try:
        raw = (directory / "stat").read_text()
    except FileNotFoundError:
        return {
            "pid": pid,
            "state": "gone",
            "start_ticks": None,
            "cmdline_sha256": None,
            "argv": [],
        }
    fields = raw[raw.rfind(")") + 2 :].split()
    command = (directory / "cmdline").read_bytes() if fields[0] not in ("Z", "X") else b""
    return dict(
        pid=pid,
        state=fields[0],
        start_ticks=int(fields[19]),
        cmdline_sha256=hashlib.sha256(command).hexdigest() if command else None,
        argv=[part.decode() for part in command.split(b"\0") if part],
    )


def capture_parent_coordinators(root, p, *, observe=retirement_process):
    frozen = read_record(
        root, p.OUTPUT + "/preparation/execution_freeze.json", "execution_freeze", p
    )
    pause = _bound_record(
        p.PARENT_ROOT, frozen["scheduler_handoff"], "parallel_tail_handoff_pause", p
    )
    require(
        pause["id"] == frozen["scheduler_handoff_id"]
        and pause["active_training_workers_signaled"] is False,
        "retirement_scheduler_only_authority",
    )
    by_pid = {row["pid"]: row for row in pause["paused_processes"]}
    require(
        set(by_pid) == {3169168, 3171733} and frozen["parent_controller"]["pid"] == 3169168,
        "retirement_exact_two_old_coordinators",
    )
    forbidden = {row["process"]["pid"] for row in frozen["parent_workers"]} | {os.getpid()}
    marker = str(
        p.PARENT_ROOT
        / "trusted_data_synthesis/scripts/finalize_fixed_kernel_trajectory_execution_20260914.py"
    )
    captured = []
    for pid in (3169168, 3171733):
        require(pid not in forbidden, "retirement_never_training_workers_or_self")
        actual = observe(pid)
        require(
            actual["state"] in ("T", "t", "Z", "gone"), "retirement_old_coordinator_must_be_stopped"
        )
        if actual["state"] in ("T", "t"):
            require(
                actual["cmdline_sha256"] == by_pid[pid]["cmdline_sha256"],
                "retirement_same_original_command",
            )
            if pid == 3169168:
                require(
                    actual["start_ticks"] == frozen["parent_controller"]["start_ticks"]
                    and actual["cmdline_sha256"] == frozen["parent_controller"]["cmdline_sha256"],
                    "retirement_same_frozen_controller_process",
                )
            else:
                require(marker in actual["argv"], "retirement_exact_old_publisher_marker")
        captured.append(
            {key: actual[key] for key in ("pid", "state", "start_ticks", "cmdline_sha256")}
        )
    return p.record(
        "parent_coordinator_retirement_capture",
        execution_freeze_id=frozen["id"],
        scheduler_handoff_id=pause["id"],
        targets=captured,
        parent_worker_jobs=[row["job"] for row in frozen["parent_workers"]],
        parent_execution_freeze_id=frozen["parent_execution_freeze_id"],
        parent_execution_output=frozen["parent_execution_output"],
        captured_at=p.now(),
    )


def maybe_retire_parent_coordinators(
    root, p, captured, *, observe=retirement_process, send=os.kill, sleeper=time.sleep
):
    p.checked(captured, "parent_coordinator_retirement_capture")
    require(
        {item["pid"] for item in captured["targets"]} == {3169168, 3171733}
        and len(captured["targets"]) == 2,
        "retirement_exact_captured_signal_targets",
    )
    output = root / p.OUTPUT
    result_path = output / "parent_coordinators_retired.json"
    if result_path.exists():
        old = p.checked(p.read_json(result_path), "parent_coordinators_retired")
        require(
            old["capture_id"] == captured["id"] and old["status"] == "RETIRED_OR_ALREADY_EXITED",
            "retirement_existing_result_must_be_successful",
        )
        return True
    manifest_path = output / "completed_parent_imports.json"
    if not manifest_path.exists():
        return False
    require(
        not any(
            (output / name).exists()
            for name in ("parallel_handoff_failure.json", "execution_failure.json")
        ),
        "retirement_no_new_handoff_failure",
    )
    imported = read_record(
        root, p.OUTPUT + "/completed_parent_imports.json", "completed_parent_training_imports", p
    )
    require(
        imported["execution_freeze_id"] == captured["execution_freeze_id"]
        and imported["completed_parent_runs"] == len(imported["imports"]) == 8
        and imported["original_report_IDs_preserved"] is True,
        "retirement_all_eight_actual_imports_required",
    )
    wanted = {
        tuple(job[key] for key in ("pool", "arm", "seed")) for job in captured["parent_worker_jobs"]
    }
    require(
        len(wanted) == 8 and ("A", "minus", 47) not in wanted,
        "retirement_exact_original_eight_jobs",
    )
    seen = set()
    for item in imported["imports"]:
        p.checked(item, "completed_parent_training_import")
        key = tuple(item["job"][name] for name in ("pool", "arm", "seed"))
        require(
            key in wanted
            and key not in seen
            and item["source_root"] == str(p.PARENT_ROOT)
            and item["source_execution_freeze_id"] == captured["parent_execution_freeze_id"]
            and item["report_ID_or_historical_paths_rewritten"] is False
            and item["source_worker_exit_observation"]["state"] in ("Z", "X", "gone"),
            "retirement_complete_native_parent_import",
        )
        seen.add(key)
        relative = p.OUTPUT + "/training/" + "_".join(map(str, key)) + "/report.json"
        raw = regular(root, relative, SMALL_LIMIT).read_bytes()
        report = p.checked(json.loads(raw), "training_report")
        member = next(row for row in item["members"] if row["path"] == "report.json")
        require(
            report["id"] == item["training_report_id"]
            and report["actual_complete"] is True
            and report["status"] == "COMPLETE_FINAL_CHECKPOINT"
            and report["optimizer_updates"] == 400
            and report["epochs_completed"] == 10
            and tuple(report[name] for name in ("pool", "arm", "seed")) == key
            and len(raw) == member["bytes"]
            and hashlib.sha256(raw).hexdigest() == member["sha256"],
            "retirement_actual_copied_complete_report_bytes",
        )
    parent = p.PARENT_ROOT / captured["parent_execution_output"]
    require(
        not (parent / "training/A_minus_47").exists()
        and not (parent / "jobs/A_train/train_A_minus_47_job.json").exists(),
        "retirement_parent_ninth_never_launched",
    )
    observations = []
    for target in captured["targets"]:
        actual = observe(target["pid"])
        require(
            actual["state"] in ("T", "t", "Z", "gone"),
            "retirement_refuse_unexpected_running_process",
        )
        if actual["state"] != "gone":
            require(actual["start_ticks"] == target["start_ticks"], "retirement_no_PID_reuse")
        if actual["state"] in ("T", "t"):
            require(
                target["state"] in ("T", "t")
                and actual["cmdline_sha256"] == target["cmdline_sha256"],
                "retirement_same_captured_command",
            )
        observations.append(actual)
    actions = []
    try:
        for actual in observations:
            if actual["state"] in ("T", "t"):
                pid = actual["pid"]
                latest = observe(pid)
                require(
                    latest["state"] in ("T", "t")
                    and latest["start_ticks"] == actual["start_ticks"]
                    and latest["cmdline_sha256"] == actual["cmdline_sha256"],
                    "retirement_exact_identity_immediately_before_signal",
                )
                send(pid, signal.SIGTERM)
                actions.append({"pid": pid, "signal": "SIGTERM"})
                try:
                    send(pid, signal.SIGCONT)
                    actions.append({"pid": pid, "signal": "SIGCONT"})
                except ProcessLookupError:
                    pass
        final = []
        for attempt in range(11):
            final = [observe(item["pid"]) for item in captured["targets"]]
            if all(item["state"] in ("Z", "gone") for item in final):
                break
            if attempt < 10:
                sleeper(1)
        require(
            all(item["state"] in ("Z", "gone") for item in final),
            "retirement_exit_not_confirmed_within_10s",
        )
        ticks = {item["pid"]: item["start_ticks"] for item in captured["targets"]}
        require(
            all(
                item["state"] == "gone" or item["start_ticks"] == ticks[item["pid"]]
                for item in final
            ),
            "retirement_same_PID_identity_at_exit",
        )
        result = p.record(
            "parent_coordinators_retired",
            status="RETIRED_OR_ALREADY_EXITED",
            capture_id=captured["id"],
            execution_freeze_id=captured["execution_freeze_id"],
            completed_parent_imports_id=imported["id"],
            actions=actions,
            final_observations=[
                {key: item[key] for key in ("pid", "state", "start_ticks")} for item in final
            ],
            training_workers_or_new_processes_signaled=False,
            old_terminal_fabricated=False,
            files_deleted=False,
            retired_at=p.now(),
        )
        p.write_once(result_path, result)
        return True
    except BaseException as error:
        p.write_once(
            result_path,
            p.record(
                "parent_coordinators_retired",
                status="RETIREMENT_REFUSED_OR_PARTIAL",
                capture_id=captured["id"],
                actions=actions,
                error_type=type(error).__name__,
                reason=str(error)[:1000],
                training_workers_or_new_processes_signaled=False,
                old_terminal_fabricated=False,
                files_deleted=False,
                retired_at=p.now(),
            ),
        )
        raise


def wait_for_closure(root, p, *, wait, sleeper=time.sleep, retirement=None):
    paths = (
        root / p.OUTPUT / "report.json",
        root / p.OUTPUT / "manifest.json",
        p.MATERIALS_ROOT / (p.MATERIALS + "_publication/materials/publication_manifest.json"),
    )
    failures = [
        root / p.OUTPUT / name
        for name in ("execution_failure.json", "parallel_handoff_failure.json")
    ]
    while True:
        if retirement is not None:
            maybe_retire_parent_coordinators(root, p, retirement, sleeper=sleeper)
        if all(path.exists() for path in paths):
            break
        require(
            not any(path.exists() for path in failures), "actual_execution_failed_no_publication"
        )
        require(wait, "actual_report_manifest_and_original_material_archive_not_ready")
        sleeper(10)
    require(not any(path.exists() for path in failures), "failure_not_relabelled_complete")
    return paths


def _bound_record(root, reference, kind, p):
    require(descriptor(root, reference["path"]) == reference, "exact_metadata_descriptor")
    return read_record(root, reference["path"], kind, p)


def read_producer_manifest(root, relative, p):
    # Preserve the separate large-manifest limit; it is archived, not raw-staged.
    raw = regular(root, relative, PRODUCER_MANIFEST_LIMIT).read_bytes()
    value = p.checked(json.loads(raw), "evaluation_manifest")
    require(p.encode(value) == raw, "canonical_bounded_producer_manifest")
    return value


def validate_training_report(trained, key, frozen, cache, p):
    pool, arm, seed = key
    binding = {
        "study_freeze_id": frozen["study_freeze_id"],
        "surface_manifest_id": p.SURFACE_MANIFEST_ID,
        "kernel_id": frozen["kernel_id"],
        "training_configuration_id": frozen["training_configuration"]["id"],
    }
    p.validate_binding(trained, binding, pool=pool, arm=arm, seed=seed)
    require(
        trained["actual_complete"] is True
        and trained["status"] == "COMPLETE_FINAL_CHECKPOINT"
        and trained["trajectory_cache_id"] == cache["id"]
        and trained["material_verification_id"] == cache["material_verification_id"]
        and trained["actual_budget"] == cache["pool_budgets"][pool]
        and trained["source_material_budget"] == cache["source_material_budgets"][pool]
        and trained["optimizer_updates"] == 400
        and trained["epochs_completed"] == 10
        and trained["final_adapter_restored_identity_verified"] is True,
        "actual_original_or_parallel_Student_and_exact_budget",
    )
    return trained


def inputs(root, p):
    output = p.OUTPUT

    def read(name, kind):
        return read_record(root, output + "/" + name, kind, p)

    def material(name, kind):
        return read_record(p.MATERIALS_ROOT, p.MATERIALS + "/" + name, kind, p)

    report = read("report.json", "execution_report")
    closed = read_producer_manifest(root, output + "/manifest.json", p)
    frozen = read("preparation/execution_freeze.json", "execution_freeze")
    authority = read(
        "preparation/parallel_execution_authority.json", "parallel_tail_execution_authority"
    )
    decision = read("decision.json", "actual_direction_decision")
    handoff = read("A_training_handoff.json", "parallel_tail_A_handoff")
    imports = read("completed_parent_imports.json", "completed_parent_training_imports")
    generation = material("generation_report.json", "material_generation_report")
    gate = material("material_gate.json", "material_gate")
    original = material("freeze.json", "study_freeze")
    completion = material("completion_freeze.json", "kernel_completion_freeze")
    authorization = material("authorization.json", "kernel_completion_authorization")
    require(
        report["actual_complete"] is True
        and report["status"] in ("COMPLETE_NO_POSITIVE_DIRECTION", "COMPLETE_FIXED_CONFIRMATION")
        and closed["report_id"] == report["id"]
        and closed["phase"] == "fixed_kernel_value_execution"
        and decision["actual_complete"] is True
        and decision["id"] == report["decision_id"]
        and report["heterogeneous_execution"] is True,
        "actual_complete_new_execution_and_producer_closure",
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
        "unchanged_closed_original_materials_and_kernel",
    )
    require(
        authority["execution_freeze_id"] == frozen["id"]
        and authority["completion_freeze_id"] == completion["id"]
        and authority["original_registry_freeze_id"]
        == original["id"]
        == frozen["study_freeze_id"]
        == report["study_freeze_id"]
        and frozen["output_directory"] == output
        and authority["parent_source_root"] == str(p.PARENT_ROOT)
        and authority["original_material_source_root"] == str(p.MATERIALS_ROOT)
        and authority["training_configuration_id"]
        == frozen["training_configuration"]["id"]
        == report["training_configuration_id"]
        and authority["per_run_training_configuration_ids"]
        == frozen["per_run_training_configuration_ids"]
        == report["per_run_training_configuration_ids"]
        == p.configuration_ids()
        and authority["heterogeneous_execution"] is True
        and authority["original_report_IDs_and_bytes_preserved"] is True
        and authority["optimizer_partial_state_reused"] is False
        and authority["bitwise_equivalence_claimed"] is False
        and completion["authorization_id"] == authorization["id"]
        and authorization["amended_combined_token_cap"] == 350000000,
        "separate_parallel_authority_true_configurations_and_budget_amendment",
    )
    parent = _bound_record(p.PARENT_ROOT, frozen["parent_execution_freeze"], "execution_freeze", p)
    parent_authority = _bound_record(
        p.PARENT_ROOT, frozen["parent_execution_authority"], "trajectory_execution_authority", p
    )
    require(
        parent["id"]
        == frozen["parent_execution_freeze_id"]
        == authority["parent_execution_freeze_id"]
        and parent_authority["id"] == authority["parent_execution_authority_id"]
        and parent_authority["execution_freeze_id"] == parent["id"]
        and parent["kernel_id"] == p.EXPECTED_KERNEL
        and parent["input_root"] == frozen["input_root"]
        and parent["material_verification"] == frozen["material_verification"]
        and parent["material_input_receipt"] == frozen["material_input_receipt"],
        "actual_parent_trajectory_and_unchanged_material_authority",
    )
    cached = frozen["trajectory_cache"]
    cache = _bound_record(root, cached["manifest"], "trajectory_material_cache", p)
    require(
        cached == authority["trajectory_cache"]
        and cached["cache_root"] == output + "/preparation/trajectory_cache"
        and cached["manifest"]["path"] == cached["cache_root"] + "/manifest.json"
        and cache["id"]
        == cached["manifest_id"]
        == authority["trajectory_cache_id"]
        == parent["trajectory_cache"]["manifest_id"]
        and cache["kernel_id"] == p.EXPECTED_KERNEL
        and cache["material_verification_id"] == frozen["material_verification"]["id"]
        and cache["pool_budgets"] == frozen["trajectory_pool_budgets"]
        and cache["source_material_budgets"]
        == frozen["source_material_budgets"]
        == frozen["material_verification"]["pool_budgets"],
        "copied_cache_identity_and_actual_forward_budget",
    )
    a_keys = [("A", arm, seed) for seed in p.SEEDS for arm in p.ARMS]
    approved = list(a_keys)
    if report["status"] == "COMPLETE_FIXED_CONFIRMATION":
        require(decision["selected_arm"] in ("plus", "minus"), "one_actual_confirmation_direction")
        approved += [
            ("B", arm, seed) for seed in p.SEEDS for arm in ("alpha0", decision["selected_arm"])
        ]
    else:
        require(decision["selected_arm"] == "alpha0", "actual_no_move_selection")
    require(report["actual_training_runs"] == len(approved), "actual_training_run_denominator")
    trained, adapter_paths = {}, []
    leaf = PurePosixPath(output).name
    for key in approved:
        relative = "training/" + "_".join(map(str, key))
        value = read(relative + "/report.json", "training_report")
        trained[key] = validate_training_report(value, key, frozen, cache, p)
        adapter_paths.append(f"{leaf}/{relative}/final_adapter.safetensors")
    require(
        imports["execution_freeze_id"] == handoff["execution_freeze_id"] == frozen["id"]
        and imports["completed_parent_runs"] == len(imports["imports"]) == 8
        and imports["original_report_IDs_preserved"] is True
        and handoff["parent_import_manifest_id"] == imports["id"]
        and handoff["imported_parent_runs"] == 8
        and handoff["new_parallel_runs"] == 1
        and handoff["tail_report_id"] == trained[("A", "minus", 47)]["id"]
        and handoff["training_report_ids"] == [trained[key]["id"] for key in a_keys]
        and report["parallel_tail_A_handoff_id"] == handoff["id"],
        "actual_eight_originals_and_one_parallel_tail_handoff",
    )
    imported_keys = set()
    for item in imports["imports"]:
        key = tuple(item["job"][name] for name in ("pool", "arm", "seed"))
        require(
            key in trained
            and key != ("A", "minus", 47)
            and key[0] == "A"
            and key not in imported_keys,
            "exact_unique_eight_parent_imports",
        )
        value = trained[key]
        require(
            item["source_root"] == str(p.PARENT_ROOT)
            and item["source_execution_freeze_id"] == parent["id"]
            and item["training_report_id"] == value["id"]
            and item["training_configuration_id"] == value["training_configuration_id"]
            and item["original_adapter_directory"] == value["adapter_directory"]
            and item["checkpoint_id"] == value["checkpoint_id"]
            and item["report_ID_or_historical_paths_rewritten"] is False,
            "imported_original_report_ID_configuration_and_historical_path_preserved",
        )
        imported_keys.add(key)
    actual_lineage = p.execution_lineage([trained[key] for key in approved])
    require(
        report["execution_lineage"] == actual_lineage,
        "final_report_exact_heterogeneous_execution_lineage",
    )
    tail = trained[("A", "minus", 47)]
    require(
        tail["parent_trajectory_training_configuration_id"]
        == frozen["training_configuration"]["id"]
        and tail["world_size"] == 8
        and tail["parallel_backend"] == "nccl"
        and tail["gradient_reduction"] == "SUM"
        and tail["world_size_divisor"] is False
        and tail["all_rank_processes_exited_before_publication"] is True
        and len(tail["rank_process_exits"]) == 8
        and {item["rank"] for item in tail["rank_process_exits"]} == set(range(8))
        and all(item["exit_code"] == 0 for item in tail["rank_process_exits"])
        and tail["floating_point_reduction_order_changed"] is True
        and tail["bitwise_optimizer_equivalence_claimed"] is False,
        "actual_closed_parallel_rank_processes_and_nonbitwise_SUM_backend",
    )
    old_manifest = read_record(
        p.MATERIALS_ROOT,
        p.MATERIALS + "_publication/materials/publication_manifest.json",
        "publication_manifest",
        p,
    )
    require(
        old_manifest["id"] == p.EXPECTED_MATERIAL_MANIFEST, "exact_closed_original_material_archive"
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
        handoff=handoff,
        imports=imports,
        generation=generation,
        gate=gate,
        original=original,
        completion=completion,
        authorization=authorization,
        material_manifest=old_manifest,
        trajectory_manifest=cache,
        material_receipt=frozen["material_input_receipt"],
        approved_adapter_paths=adapter_paths,
        actual_training_report_ids=[trained[key]["id"] for key in approved],
        tail_training_report=trained[("A", "minus", 47)],
        execution_lineage=actual_lineage,
    )


def summary(data, terminal):
    report, tail = data["report"], data["tail_training_report"]

    def display(value):
        return "未提供／未测量" if value is None else json.dumps(value, ensure_ascii=False)

    lines = [
        "# Fixed-kernel：保留八个原 Student 与并行尾任务的实际结果",
        "",
        "本页仅汇总实际闭合报告；训练或归档完成不等于发现正科学效应。",
        "八个已有 A Student 在原进程完成后按原字节导入，历史报告 ID、训练配置与路径字段不重写。",
        "只有 A/minus/47 使用登记的八卡并行 SUM 后端；B 分支仍采用原单卡轨迹训练配置。",
        "公开评测身份指向实际复制的最终 adapter，仍引用原训练报告 ID。",
        "",
        "## 材料与执行来源",
        "",
        f"- 原始采集：{data['generation']['finished_sessions']}/10,240；"
        f"kernel `{data['gate']['kernel_id']}`。",
        "- 采集预算曾由 250M 修订至 350M tokens；不将其描述为原始未修订预注册方案。",
        f"- 原轨迹 cache `{data['trajectory_manifest']['id']}` 原样复用；"
        "无重采样、重分词或 kernel 重建。",
        f"- 新执行 authority `{data['authority']['id']}`；"
        f"原八个完成运行导入清单 `{data['imports']['id']}`。",
        f"- 混合配置 lineage `{data['execution_lineage']['id']}`；原报告配置不被改称统一配置。",
        "",
        "## 尾任务实际报告",
        "",
        f"- 训练报告 `{tail['id']}`；真实配置 `{tail['training_configuration_id']}`。",
        f"- 后端／world size／归约：{display(tail.get('parallel_backend'))} / "
        f"{display(tail.get('world_size'))} / {display(tail.get('gradient_reduction'))}。",
        f"- 实际进程退出：{display(tail.get('rank_process_exits'))}。",
        f"- 报告中的 dropout stream：{display(tail.get('dropout_stream'))}。",
        "- 报告中的原串行掩码重放声明："
        f"{display(tail.get('dropout_masks_replayed_from_parent_serial_stream'))}。",
        "- 以上随机流描述仅来自实际运行记录，不等于另做了掩码逐位审计。",
        "  FP32 归约顺序变化明确保留；没有声称梯度、optimizer 或最终参数逐位相同。",
        "",
        "## 正式结果",
        "",
    ]
    for name in (
        "status",
        "actual_training_runs",
        "actual_evaluation_sessions",
        "confirmation_sessions",
        "independent_positive_effect_confirmed",
    ):
        lines.append(f"- `{name}`：{display(report.get(name))}。")
    lines.extend(
        [
            f"- A 开发选择：{display(data['decision'].get('selected_arm'))}；"
            f"配对均值增益：{display(data['decision'].get('paired_mean_gain'))}。",
            "- 未执行的确认分支不推断效果；统计结果仍条件于这些已固定训练检查点。",
            "",
            "## 单次发布",
            "",
            f"- 实际执行报告 `{report['id']}`；发布 lineage `{terminal['id']}`。",
            f"- 原材料 archive `{data['material_manifest']['id']}` 只复制，不重封。",
            f"- 本执行结果 archive `{data['results_manifest']['id']}` 仅封存一次。",
            "- 仅精确暂存密封归档、分页索引、权威小报告及本文；大型 producer manifest 不直接暂存。",
            f"- 目标 {REMOTE} main；普通非强制 push，失败留证且不自动重试。",
            "- 本文不预先宣称 push 成功；远端结果以独立 Git receipt 为准。",
            "",
        ]
    )
    return "\n".join(lines).encode()


def _commit(root, p, source, terminal, members, signatures, workflow, runtime, runner):
    require(len({row["path"] for row in members}) == len(members), "unique_final_git_allowlist")
    parent = runner(root, "rev-parse", "HEAD").stdout.decode().strip()
    runner(root, "merge-base", "--is-ancestor", source["head_commit"], "HEAD")
    inventory = p.record(
        "parallel_execution_git_publication_inventory",
        parent_commit=parent,
        lineage_terminal_id=terminal["id"],
        members=members,
        exact_sparse_force_allowlist=True,
        force_push=False,
        remote=REMOTE,
        refspec=REFSPEC,
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
        require(signature(path) == signatures[row["path"]], "selected_bytes_changed_after_binding")
    runner(root, "diff", "--quiet", "--", *sorted(staged))
    require(
        runner(root, "rev-parse", "HEAD").stdout.decode().strip() == parent,
        "parent_unchanged_before_commit",
    )
    runner(root, "commit", "-m", "Publish original Students and registered parallel-tail results")
    commit = runner(root, "rev-parse", "HEAD").stdout.decode().strip()
    fields = dict(
        commit=commit,
        parent_commit=parent,
        inventory_id=inventory["id"],
        remote=REMOTE,
        refspec=REFSPEC,
        force_push=False,
        automatic_retry=False,
    )
    try:
        runner(root, "push", REMOTE, REFSPEC)
    except Exception as error:
        p.write_once(
            runtime / "parallel_publication_git_receipt.json",
            p.record(
                "parallel_execution_git_publication_receipt",
                status="COMMITTED_PUSH_FAILED",
                error_type=type(error).__name__,
                **fields,
            ),
        )
        raise
    receipt = p.record(
        "parallel_execution_git_publication_receipt", status="COMMITTED_AND_PUSHED", **fields
    )
    p.write_once(runtime / "parallel_publication_git_receipt.json", receipt)
    return receipt


def finalize(root, p, *, wait=False, sealer=None, runner=git, sleeper=time.sleep):
    root = Path(root).absolute()
    require(not any(part.is_symlink() for part in (root, *root.parents)), "regular_new_root")
    require(
        root not in (p.PARENT_ROOT, p.MATERIALS_ROOT)
        and runner(root, "branch", "--show-current").stdout.decode().strip() == p.BRANCH,
        "independent_parallel_execution_branch",
    )
    require(
        not runner(root, "diff", "--cached", "--name-only", "-z").stdout,
        "preexisting_staged_changes_refused",
    )
    runtime = root / p.RUNTIME
    runtime.mkdir(parents=True, exist_ok=True)
    require(not any(part.is_symlink() for part in (runtime, *runtime.parents)), "regular_runtime")
    with (runtime / "parallel_publication_operator.lock").open("xb") as stream:
        stream.write(str(os.getpid()).encode())
    source = capture_sources(root, p, runner)
    retirement = capture_parent_coordinators(root, p)
    workflow = p.OUTPUT + "_publication_workflow"
    started = p.record(
        "parallel_publication_operator_started",
        pid=os.getpid(),
        started_at=p.now(),
        source_capture=source,
        parent_coordinator_retirement_capture=retirement,
        wait=wait,
        poll_seconds=10,
        maximum_seal_attempts=1,
        maximum_push_attempts=1,
        old_workflow_terminal_required=False,
        imported_original_training_reports_rewritten=False,
    )
    p.write_once(root / workflow / "started.json", started)
    phase, sealed = "waiting_for_actual_new_closure", False
    try:
        wait_for_closure(root, p, wait=wait, sleeper=sleeper, retirement=retirement)
        phase = "actual_parallel_authority_and_native_report_lineage"
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
        phase = "seal_actual_new_results_once"
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
        phase = "copy_existing_material_archive_without_reseal"
        old_members, old_signatures = copy_materials(root, p, data["material_manifest"])
        new_members, new_signatures = collect_results(root, p, result, data["report"])
        data["results_manifest"] = result
        tail = data["tail_training_report"]
        terminal = p.record(
            "parallel_execution_publication_lineage",
            status="COMPLETE_ACTUAL_PARALLEL_EXECUTION_AND_SEALS",
            started_id=started["id"],
            source_capture_id=source["id"],
            execution_authority_id=data["authority"]["id"],
            execution_freeze_id=data["frozen"]["id"],
            parent_execution_freeze_id=data["frozen"]["parent_execution_freeze_id"],
            original_material_gate_id=data["gate"]["id"],
            original_kernel_id=data["gate"]["kernel_id"],
            completion_freeze_id=data["completion"]["id"],
            budget_authorization_id=data["authorization"]["id"],
            trajectory_cache_id=data["trajectory_manifest"]["id"],
            completed_parent_import_manifest_id=data["imports"]["id"],
            A_training_handoff_id=data["handoff"]["id"],
            execution_lineage=data["execution_lineage"],
            actual_training_report_ids=data["actual_training_report_ids"],
            actual_execution_report_id=data["report"]["id"],
            materials_publication_manifest_id=data["material_manifest"]["id"],
            results_publication_manifest_id=result["id"],
            imported_completed_parent_training_runs=8,
            new_parallel_tail_training_runs=1,
            actual_tail_dropout_stream=tail.get("dropout_stream"),
            actual_tail_reported_dropout_masks_replayed=tail.get(
                "dropout_masks_replayed_from_parent_serial_stream"
            ),
            actual_tail_rank_process_exits=tail["rank_process_exits"],
            original_report_IDs_or_configuration_IDs_rewritten=False,
            bitwise_gradient_or_optimizer_equivalence_claimed=False,
            original_material_reseals=0,
            new_results_seal_attempts=1,
            old_workflow_terminal_fabricated=False,
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
        members, signatures = old_members + new_members, {**old_signatures, **new_signatures}
        small = [workflow + "/started.json", workflow + "/terminal.json", SUMMARY]
        small += [
            p.OUTPUT + "/" + name
            for name in (
                "report.json",
                "decision.json",
                "A_training_handoff.json",
                "A_execution_lineage.json",
                "preparation/execution_freeze.json",
                "preparation/parallel_execution_authority.json",
                "preparation/trajectory_cache/manifest.json",
            )
        ]
        # The potentially large producer manifest and original arrays appear
        # only inside the sealed result containers, never in this raw allowlist.
        for name in small:
            members.append(descriptor(root, name))
            signatures[name] = signature(root / name)
        phase = "exact_single_git_commit_and_nonforce_push"
        return _commit(root, p, source, terminal, members, signatures, workflow, runtime, runner)
    except BaseException as error:
        p.write_once(
            runtime / "parallel_publication_operator_failure.json",
            p.record(
                "parallel_publication_operator_failure",
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
    namespace = "trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value."
    protocol, study, lineage, evaluation = [
        importlib.import_module(namespace + name)
        for name in ("protocol", "parallel_study", "parallel_lineage", "evaluation")
    ]
    require(
        Path(study.__file__).resolve().is_relative_to(root), "correct_parallel_execution_module"
    )
    p = SimpleNamespace(
        **{
            name: getattr(study, name)
            for name in (
                "OUTPUT",
                "MATERIALS",
                "RUNTIME",
                "PARENT_ROOT",
                "PARENT_OUTPUT",
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
        SURFACE_MANIFEST_ID=evaluation.SURFACE_MANIFEST_ID,
        configuration_ids=lineage.configuration_ids,
        validate_binding=lineage.validate_binding,
        execution_lineage=lineage.execution_lineage,
    )
    print(p.encode(finalize(root, p, wait=args.wait)).decode(), flush=True)


if __name__ == "__main__":
    main()
