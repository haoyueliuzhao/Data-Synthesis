"""Freeze, wait for and report the fixed sealed cross-market calibration.

Only completed evaluation artifacts may supply outcomes. The original issuer-
cluster statistical kernel is called unchanged; no model, score, source, budget
extension or task-selection operation is implemented by this runner.
"""

# ruff: noqa: E501 -- literal audit tables and fixed registered artifact paths

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import cross_market_statistics_20260926 as statistics
import run_fixed_kernel_cross_market_evaluation_20260926 as controller

p, prior, legacy = controller.p, controller.prior, controller.legacy
SCRIPT = "trusted_data_synthesis/scripts/run_cross_market_calibration_report_20260927.py"
RAW = controller.BASE / "cross_market_calibration_cache_20260926/statistics_01"
PROTOCOL = "cross_market_calibration_report_protocol"
RESULT = "cross_market_calibration_analysis_result"
COMPLETED = "cross_market_calibration_report_completed"
PUBLIC = "trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/cross_market_calibration_20260926/public/calibration_final_report_20260927.json"
DOCUMENT = "trusted_data_synthesis/docs/cross_market_calibration_report_20260927.md"
SOURCES = [
    SCRIPT,
    controller.SCRIPT,
    controller.evaluation.SCRIPT,
    prior.SCRIPT,
    "trusted_data_synthesis/scripts/cross_market_statistics_20260926.py",
    "trusted_data_synthesis/scripts/fixed_kernel_direction_calibration_statistics_20260926.py",
]


def require(condition, reason):
    p.require(condition, "cross_market_report." + reason)


def read(path):
    return p.read_json(path) if Path(path).exists() else None


def write(output, name, value, immutable=True):
    output, path = Path(output).resolve(), Path(output) / name
    require(output == RAW.resolve() and path.resolve().is_relative_to(output), "confined_output")
    legacy.durable.write(path, value, immutable=immutable)
    return value


def reference(path):
    return controller.reference(path)


def committed_sources(root):
    root = Path(root)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    sources = {}
    for name in SOURCES:
        data = (root / name).read_bytes()
        require(
            data == subprocess.check_output(["git", "show", head + ":" + name], cwd=root),
            "committed_code_before_registration",
        )
        sources[name] = p.sha(data)
    return head, sources


def register(root, evaluation_root=controller.RAW, output=RAW):
    root, evaluation_root, output = (
        Path(root).resolve(),
        Path(evaluation_root).resolve(),
        Path(output).resolve(),
    )
    require(
        evaluation_root == controller.RAW.resolve() and output == RAW.resolve(),
        "fixed_mainline_roots",
    )
    if (output / "protocol.json").exists():
        return protocol(root, output)
    context = controller.evaluation.Context(evaluation_root)
    evaluation_plan = context.read_protocol(root)
    manifest = prior.public_manifest(evaluation_plan)
    admission = prior._reference(evaluation_plan["panel"]["admission"])
    compilation_path = (
        Path(evaluation_plan["panel"]["admission"]["path"]).parent.parent / "protocol.json"
    )
    compilation = p.read_json(compilation_path)
    require(
        compilation["id"] == admission["compilation_protocol_id"]
        and compilation["full_original_PDF_visual_exhaustion_claimed"] is False,
        "same_limited_text_table_panel_preparation",
    )
    issuer_ref = admission["issuer_admission"]
    issuer = prior._reference(issuer_ref)
    statistics.admission_mapping(issuer)
    head, sources = committed_sources(root)
    watched = read(output / "watch_binding.json")
    if watched is not None:
        require(watched["sources"] == sources, "same_running_watch_code_before_registration")
    for name in SOURCES:
        if name in evaluation_plan["scientific_sources"]:
            require(
                sources[name] == evaluation_plan["scientific_sources"][name],
                "unchanged_evaluation_frozen_statistics",
            )
    value = p.record(
        PROTOCOL,
        frozen=True,
        code_commit=head,
        sources=sources,
        evaluation_root=str(evaluation_root),
        evaluation_protocol=reference(evaluation_root / "protocol.json"),
        source_manifest=evaluation_plan["panel"]["manifest"],
        panel_admission=evaluation_plan["panel"]["admission"],
        issuer_admission=issuer_ref,
        panel_preparation=dict(
            compilation_protocol=reference(compilation_path),
            source_text_table_review_bundle_id=compilation["source_text_table_review_bundle_id"],
            source_text_table_reviews=compilation["source_text_table_reviews"],
            review_scope=compilation["source_text_table_review_scope"],
            user_requested_return_to_nonvisual_mainline=True,
            source_review_API_usage_not_Student_evaluation_usage=True,
            original_visual_branch_GPU_inference_performed=False,
        ),
        source_manifest_id=manifest["id"],
        task_count=180,
        scoring_cohorts=18,
        outcome_count=4860,
        seeds=[11, 29, 47],
        arms=["static", "positive", "negative"],
        decoding_repeats=dict(stochastic=[1, 2], greedy=[0]),
        statistical_function="cross_market_statistics_20260926.analyze",
        bootstrap=dict(seed=20260926, valid_replicates=20000, maximum_draws=200000),
        maximum_analysis_attempts=2,
        only_resource_interruption_may_repeat_identical_analysis=True,
        no_outcomes_opened_during_registration=True,
        private_results_require_completed_evaluation_and_full_generation_seal=True,
        new_model_calls=0,
        new_scoring_cases=0,
        original_B_training_value_not_confirmed_by_cross_market_calibration=True,
        publication_paths=[PUBLIC, DOCUMENT],
        maximum_publication_attempts=8,
        at=p.now(),
    )
    write(output, "protocol.json", value)
    return value


def protocol(root, output=RAW):
    output = Path(output).resolve()
    require(output == RAW.resolve(), "fixed_report_root")
    value = p.checked(p.read_json(output / "protocol.json"), PROTOCOL)
    require(
        value["frozen"] is True
        and value["evaluation_root"] == str(controller.RAW.resolve())
        and value["task_count"] == 180
        and value["scoring_cohorts"] == 18
        and value["outcome_count"] == 4860
        and value["maximum_analysis_attempts"] == 2
        and value["bootstrap"] == dict(seed=20260926, valid_replicates=20000, maximum_draws=200000),
        "fixed_registered_analysis",
    )
    for name, digest in value["sources"].items():
        require(p.sha(Path(root) / name) == digest, "frozen_source:" + name)
    require(
        reference(Path(value["evaluation_root"]) / "protocol.json") == value["evaluation_protocol"],
        "same_evaluation_protocol",
    )
    return value


def require_workers_exited(evaluation_root):
    for directory in (Path(evaluation_root) / "control/attempts").glob("*/*"):
        row = read(directory / "started.json") or read(directory / "launched.json")
        if row is None:
            continue  # The completed evaluation controller already settled this reservation.
        current = controller.process_identity(row["pid"])
        if row["process_identity"] is None:
            require(current is None, "unknown_live_worker_birth_identity_requires_review")
        else:
            require(
                current != row["process_identity"],
                "all_evaluation_workers_exited_before_analysis",
            )


def collect_outcomes(evaluation_plan, manifest, seal, reports, generations):
    """Pure strict cohort/session join. Call only after the global seal barrier."""
    require(
        seal["complete"] is True
        and seal["all_generation_workers_exited"] is True
        and seal["total_trajectories"] == 4860
        and seal["protocol_id"] == evaluation_plan["id"]
        and seal["source_manifest_id"] == manifest["id"],
        "complete_generation_seal_before_collecting_outcomes",
    )
    expected_keys = {
        (arm, seed, mode) for arm in prior.ARMS for seed in prior.SEEDS for mode in prior.MODES
    }
    require(
        len(reports) == len(generations) == len(seal["cohorts"]) == 18,
        "exact_eighteen_complete_cohorts",
    )
    cohorts = {(row["condition"], row["seed"], row["phase"]): row for row in seal["cohorts"]}
    require(set(cohorts) == expected_keys, "all_registered_arms_seeds_decodings")
    seen, outcomes = set(), []
    for report in reports:
        p.checked(report, "cross_market_independent_scoring")
        key = report["condition"], report["seed"], report["phase"]
        require(key in cohorts and key not in seen, "one_report_per_registered_cohort")
        seen.add(key)
        row = cohorts[key]
        frozen = generations[key]
        p.checked(frozen, "anchored_generation_manifest")
        expected_count = 360 if key[2] == "stochastic" else 180
        expected_order = [
            (task["task_id"], repeat)
            for task in manifest["tasks"]
            for repeat in ((1, 2) if key[2] == "stochastic" else (0,))
        ]
        require(
            report["complete"] is True
            and report["protocol_id"] == evaluation_plan["id"]
            and report["generation_seal_id"] == seal["id"]
            and report["generation_manifest_id"] == frozen["id"]
            and report["point_id"] == frozen["point_id"] == row["point_id"]
            and report["source_manifest_id"] == frozen["source_manifest_id"] == manifest["id"]
            and report["runtime_binding_id"]
            == evaluation_plan["materials"]["runtime_binding"]["id"]
            and report["denominator"]
            == len(report["scores"])
            == len(frozen["trajectories"])
            == expected_count
            and report["qualified"] == sum(item["Q"] for item in report["scores"])
            and report["scoring_after_all_generation_complete"] is True
            and report["private_references_never_sent_to_generator"] is True
            and report["financial_support_principle_unchanged"] is True
            and report["calibration_tasks_opened"] == 180
            and report["confirm_tasks_opened"] == 0,
            "sealed_scoring_report_exact_identity_and_dose",
        )
        require(
            [(row["task_id"], row["repeat"]) for row in report["scores"]] == expected_order,
            "original_public_task_repeat_order",
        )
        for score, item in zip(report["scores"], frozen["trajectories"], strict=True):
            prior.legacy_scoring._validate_score(score, item, assessment=False)
            outcomes.append(
                dict(
                    task_id=score["task_id"],
                    group=score["group"],
                    seed=key[1],
                    arm=key[0],
                    decoding=key[2],
                    repeat=score["repeat"],
                    Q=score["Q"],
                )
            )
    require(seen == expected_keys and len(outcomes) == 4860, "all4860_outcomes_no_imputation")
    return outcomes


def load_sealed_inputs(root, plan):
    evaluation_root = Path(plan["evaluation_root"])
    completion = p.checked(
        p.read_json(evaluation_root / "complete.json"), "cross_market_evaluation_completed"
    )
    require(
        completion["complete"] is True
        and completion["protocol_id"] == plan["evaluation_protocol"]["id"]
        and completion["source_manifest_id"] == plan["source_manifest_id"]
        and completion["scored_sessions"] == 4860
        and len(completion["scoring_reports"]) == 18,
        "completed_evaluation_before_outcomes",
    )
    require_workers_exited(evaluation_root)
    context = controller.evaluation.Context(evaluation_root)
    evaluation_plan = context.read_protocol(root)
    manifest = prior.public_manifest(evaluation_plan)
    seal_path = evaluation_root / "generation_seal.json"
    require(reference(seal_path) == completion["generation_seal"], "same_completed_generation_seal")
    # This validates every sealed cohort and original trajectory ordering, before
    # any scoring report is opened. It does not load sessions or private bundles.
    seal = prior.require_generation_seal(context, evaluation_plan, manifest, str(seal_path))
    expected_paths = {
        str(Path(row["generation_manifest_path"]).parent / "scoring_report.json")
        for row in seal["cohorts"]
    }
    report_refs = completion["scoring_reports"]
    require(
        len({row["path"] for row in report_refs}) == 18
        and {row["path"] for row in report_refs} == expected_paths,
        "exact_score_report_paths_from_sealed_cohorts",
    )
    reports = [prior._reference(ref) for ref in report_refs]
    generations = {
        (row["condition"], row["seed"], row["phase"]): p.read_json(row["generation_manifest_path"])
        for row in seal["cohorts"]
    }
    outcomes = collect_outcomes(evaluation_plan, manifest, seal, reports, generations)
    issuer = prior._reference(plan["issuer_admission"])
    # Strict input validation is performed before consuming the finite bootstrap
    # attempt. Incomplete/duplicate outcomes are errors, never padded with Q=0.
    statistics.validate(
        manifest["tasks"],
        outcomes,
        dict.fromkeys(statistics.GROUPS, 60),
        statistics.admission_mapping(issuer),
    )
    inputs = dict(
        evaluation_protocol=plan["evaluation_protocol"],
        evaluation_completion=reference(evaluation_root / "complete.json"),
        generation_seal=completion["generation_seal"],
        scoring_reports=report_refs,
        source_manifest=plan["source_manifest"],
        panel_admission=plan["panel_admission"],
        panel_preparation=plan["panel_preparation"],
        issuer_admission=plan["issuer_admission"],
        model_endpoints=evaluation_plan["models"],
        training_reuse_admission=evaluation_plan["parent_reuse_admission"],
        negative_training_completion=evaluation_plan["negative_training_completion"],
        evaluation_physical_counts=completion["physical_budget"]["counts"],
    )
    return manifest["tasks"], outcomes, issuer, inputs


def render_report(result):
    analysis = result["analysis"]
    lines = [
        "# 跨市场正向／静态／反向短程校准实验报告",
        "",
        "## 审计结论",
        "",
        "本报告来自九个固定step240保存点、180题和4,860条封存评价。原美股B确认的正向训练价值仍未确认；本轮只检验固定中港来源上的短程跨市场响应，不能替代400步独立确认。",
        "",
        f"统计状态：`{analysis['status']}`。随机效用双比较支持：`{analysis['cross_market_stochastic_support']}`；greedy双比较支持：`{analysis['cross_market_greedy_support']}`。未获支持不代表等效或证明没有作用。",
        "",
        "## 设计与执行",
        "",
        "固定seed11/29/47、Static／C正向／等TV反向三臂，真实step200→240共40步。六个旧step240点获核验信用，仅新增三个反向尾段120步。每模型每题T=1随机repeat1/2、greedy repeat0；三组各60题。随机和greedy分别报告。",
        "",
        "本统计与报告阶段不追加训练、Student推理或财务评分；这不等于整轮没有新生成。整轮Student评价为4,860会话；面板准备的文本语义审阅API调用属于独立来源准备预算，不与Student会话、生成调用或评分次数合并。来源准备调用/token计量按其独立执行记录审计，本报告不重新估算。",
        "",
        "2026-09-27按用户回归无视觉主线的指令，以独立修订合同使用限定完整text/table域的语义审核；旧视觉环境／模型获取支线不再作为本轮准入先决条件，且未开展真实GPU视觉推理。先前失败与未完成获取记录保留，不将这些工程尝试记成视觉审阅信用。",
        "",
        "来源是已准入CNInfo/HKEX官方报告的固定公开数值视图。若面板采用文本／表格审阅，其结论仅覆盖完整保存提取文本及其表格文字；未读图像与空文本原页语义仍未评估，不宣称全PDF视觉穷尽或完美金标准。",
        "",
        f"评价完成ID：`{result['inputs']['evaluation_completion']['id']}`。全局generation seal：`{result['inputs']['generation_seal']['id']}`。全量生成及所有worker退出后才消费评分；未补Q=0。",
        "",
        "## 整体配对比较",
        "",
        "差值与区间单位均为百分点；正向减反向为随机主比较，正向减Static必须同时考虑。",
        "",
        "| 解码 | 比较 | 差值 | 95%发行人簇区间 | 改善／退化配对 | 严格正下界 |",
        "| --- | --- | ---: | --- | --- | --- |",
    ]
    accounting = result["inputs"].get("evaluation_physical_counts")
    if accounting is not None:
        lines[lines.index("## 整体配对比较") : lines.index("## 整体配对比较")] = [
            "实际物理计量（失败尝试不退款，不能当成已提交会话数）：`"
            + json.dumps(accounting, ensure_ascii=False, sort_keys=True)
            + "`。九个保存点的模型身份、SHA与原训练准入引用见末尾审计JSON。",
            "",
        ]
    preparation = result["inputs"].get("panel_preparation")
    if preparation is not None:
        location = lines.index("## 整体配对比较")
        lines[location:location] = [
            f"面板编译协议：`{preparation['compilation_protocol']['id']}`；来源文本／表格审核bundle：`{preparation['source_text_table_review_bundle_id']}`；限定域：`{preparation['review_scope']}`。所有引用路径及SHA保留在审计JSON。",
            "",
        ]
    for name, row in analysis["comparisons"].items():
        ci, paired = row["ci95"], row["paired_counts"]
        interval = "未完成" if ci is None else f"[{100 * ci['lower']:.6f}, {100 * ci['upper']:.6f}]"
        lines.append(
            f"| {row['decoding']} | {name} | {100 * row['point_estimate']:.6f} | {interval} | {paired['improved']}／{paired['degraded']}（{paired['pair_count']}对） | {row['lower_bound_strictly_positive']} |"
        )
    lines.extend(
        [
            "",
            "## 分组与分种子",
            "",
            "这些是固定样本描述，不把每个组或单seed的偶然正值当作新的确认终点。",
            "",
            "| 解码／比较 | 组 | Static | 正向 | 反向 | 配对差值(pp) | 任务／发行人簇 |",
            "| --- | --- | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for name, row in analysis["comparisons"].items():
        for group in row["group_estimates"]:
            means = group["arm_means"]
            lines.append(
                f"| {name} | {group['group']} | {100 * means['static']['value']:.4f}% | {100 * means['positive']['value']:.4f}% | {100 * means['negative']['value']:.4f}% | {100 * group['difference']['value']:.6f} | {group['task_count']}／{group['issuer_cluster_count']} |"
            )
    lines.extend(["", "| 比较 | seed | 配对差值(pp) | 改善／退化 |", "| --- | ---: | ---: | --- |"])
    for name, row in analysis["comparisons"].items():
        for seed in row["seed_estimates"]:
            pairs = seed["paired_counts"]
            lines.append(
                f"| {name} | {seed['seed']} | {100 * seed['difference']['value']:.6f} | {pairs['improved']}／{pairs['degraded']} |"
            )
    bootstrap = analysis["bootstrap"]
    lines.extend(
        [
            "",
            "## 不确定性与解释边界",
            "",
            f"发行人整簇bootstrap固定随机种子20260926，目标20,000个有效样本、最多200,000次抽样；实际有效{bootstrap['valid_replicates']}，尝试{bootstrap['attempted_draws']}。四项比较共享同一组重抽样权重，采用原Fraction精确估计和95%分位区间，不按结果扩额。",
            "",
            "先对每题固定三seed及重复计算配对差，再组内平均、三组等权。区间条件于当前三个训练种子，不覆盖所有训练随机性；法律发行人也未必经济独立，相关母子公司可能仍相关。来源新颖性仅相对冻结项目来源清单，不证明预训练从未曝光。",
            "",
            "随机支持与greedy支持都要求正向减反向、正向减Static的两个精确区间下界同时严格大于0；区间为各自边际区间，不宣称联合置信覆盖。没有据结果增题、删组、换seed或修改训练方向。",
            "",
            "## 完整审计数据",
            "",
            "下列JSON保留全部四项比较、分seed×组×repeat配对计数、精确分数、bootstrap权重摘要与封存输入引用。",
            "",
            "```json",
            json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def run(root, output=RAW):
    output = Path(output).resolve()
    plan = protocol(root, output)
    with legacy.locked(output / "analysis.lock", blocking=False):
        completed = read(output / "complete.json")
        if completed is not None:
            p.checked(completed, COMPLETED)
            require(
                completed["protocol_id"] == plan["id"]
                and reference(output / "analysis_result.json") == completed["analysis_result"],
                "same_completed_analysis",
            )
            return completed
        tasks, outcomes, issuer, inputs = load_sealed_inputs(root, plan)
        path = output / "analysis_result.json"
        saved = read(path)
        if saved is None:
            state = read(output / "analysis_budget.json") or dict(attempts=0)
            require(
                state["attempts"] < plan["maximum_analysis_attempts"], "finite_analysis_attempt_cap"
            )
            if state["attempts"]:
                failure = read(output / "analysis_failure.json")
                require(
                    failure is not None and failure["resource_retry_allowed"] is True,
                    "no_unknown_or_numeric_analysis_retry",
                )
            attempt = state["attempts"] + 1
            write(
                output, "analysis_budget.json", dict(attempts=attempt, at=p.now()), immutable=False
            )
            try:
                analysis = statistics.analyze(tasks, outcomes, issuer)
            except BaseException as error:
                write(
                    output,
                    "analysis_failure.json",
                    dict(
                        attempt=attempt,
                        resource_retry_allowed=isinstance(error, MemoryError),
                        error=repr(error),
                        at=p.now(),
                    ),
                    immutable=False,
                )
                raise
            saved = p.record(
                RESULT,
                protocol_id=plan["id"],
                inputs=inputs,
                analysis=analysis,
                no_new_training_generation_or_scoring=True,
                at=p.now(),
            )
            write(output, "analysis_result.json", saved)
        else:
            p.checked(saved, RESULT)
            require(
                saved["protocol_id"] == plan["id"] and saved["inputs"] == inputs,
                "same_sealed_analysis_inputs",
            )
        body = render_report(saved).encode()
        legacy.durable.atomic_bytes(output / "report.md", body, immutable=True)
        complete = p.record(
            COMPLETED,
            protocol_id=plan["id"],
            complete=saved["analysis"]["status"] == "COMPLETE",
            status=saved["analysis"]["status"],
            analysis_result=reference(path),
            markdown=dict(path=str(output / "report.md"), sha256=p.sha(body), bytes=len(body)),
            original_B_training_value_confirmed=False,
            new_training_generation_or_scoring=0,
            at=p.now(),
        )
        write(output, "complete.json", complete)
        return complete


def _publish_locked(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    completion = p.checked(p.read_json(output / "complete.json"), COMPLETED)
    previous = read(output / "publication.json")
    if previous and previous["status"] == "PUBLISHED":
        require(previous["completion_id"] == completion["id"], "same_published_completion")
        return True
    if previous and time.time() < previous["not_before"]:
        return False
    attempt = 1 if previous is None else previous["attempt"] + 1
    require(attempt <= 8, "finite_publication_cap_no_reanalysis")
    # Charge before any report writes or git operation. A killed publisher never
    # refunds an attempt and never spends another statistical analysis attempt.
    write(
        output,
        "publication.json",
        dict(
            status="PUBLICATION_IN_PROGRESS_NO_REANALYSIS",
            completion_id=completion["id"],
            attempt=attempt,
            not_before=time.time() + 300,
            at=p.now(),
        ),
        immutable=False,
    )
    try:
        require(
            reference(output / "analysis_result.json") == completion["analysis_result"]
            and p.sha(output / "report.md") == completion["markdown"]["sha256"],
            "completed_publication_bytes",
        )
        result = p.read_json(output / "analysis_result.json")
        summary = p.record(
            "cross_market_calibration_public_report",
            completion=completion,
            **{
                key: result[key]
                for key in (
                    "protocol_id",
                    "inputs",
                    "analysis",
                    "no_new_training_generation_or_scoring",
                )
            },
        )
        if (root / PUBLIC).exists():
            require(p.read_json(root / PUBLIC) == summary, "same_public_summary")
        else:
            p.write_once(root / PUBLIC, summary)
        legacy.durable.atomic_bytes(
            root / DOCUMENT, (output / "report.md").read_bytes(), immutable=True
        )
        paths = [PUBLIC, DOCUMENT]
        subprocess.run(["git", "add", "--sparse", "-f", "--", *paths], cwd=root, check=True)
        changed = subprocess.run(["git", "diff", "--cached", "--quiet", "--", *paths], cwd=root)
        require(changed.returncode in (0, 1), "publication_diff")
        if changed.returncode:
            subprocess.run(
                [
                    "git",
                    "commit",
                    "--only",
                    "-m",
                    "Publish sealed cross-market calibration statistics and audit report",
                    "--",
                    *paths,
                ],
                cwd=root,
                check=True,
            )
        subprocess.run(
            ["git", "-c", "http.proxy=", "push", "origin", "HEAD:main"],
            cwd=root,
            check=True,
            timeout=180,
        )
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
        write(
            output,
            "publication.json",
            dict(
                status="PUBLISHED",
                completion_id=completion["id"],
                attempt=attempt,
                commit=head,
                at=p.now(),
            ),
            immutable=False,
        )
        return True
    except Exception as error:
        write(
            output,
            "publication.json",
            dict(
                status="PUBLICATION_PENDING_NO_REANALYSIS",
                completion_id=completion["id"],
                attempt=attempt,
                not_before=time.time() + 300,
                error=repr(error),
                at=p.now(),
            ),
            immutable=False,
        )
        return False


def publish(root, output=RAW):
    try:
        with legacy.locked(Path(output) / "publication.lock", blocking=False):
            return _publish_locked(root, output)
    except BlockingIOError:
        return False


def watch(root, output=RAW):
    root, output = Path(root).resolve(), Path(output).resolve()
    with legacy.locked(output / "watch.lock", blocking=False):
        head, sources = committed_sources(root)
        binding_path = output / "watch_binding.json"
        binding = read(binding_path)
        if binding:
            require(binding["sources"] == sources, "same_watch_frozen_sources")
        else:
            write(output, "watch_binding.json", dict(code_commit=head, sources=sources, at=p.now()))
        write(
            output,
            "watch_identity.json",
            dict(
                pid=os.getpid(),
                process_identity=controller.process_identity(os.getpid()),
                at=p.now(),
            ),
            immutable=False,
        )
        while True:
            status = "WAITING_EVALUATION_PROTOCOL"
            if (controller.RAW / "protocol.json").exists():
                register(root, controller.RAW, output)
                status = "WAITING_COMPLETE4860_AND_GENERATION_SEAL"
                if (controller.RAW / "complete.json").exists():
                    if not (output / "complete.json").exists():
                        try:
                            run(root, output)
                        except MemoryError:
                            write(
                                output,
                                "status.json",
                                dict(status="RESOURCE_ANALYSIS_RETRY_WITHIN_FIXED_CAP", at=p.now()),
                                immutable=False,
                            )
                            time.sleep(30)
                            continue
                    status = "PUBLICATION_PENDING_NO_REANALYSIS"
                    if publish(root, output):
                        write(
                            output,
                            "status.json",
                            dict(status="PUBLISHED", at=p.now()),
                            immutable=False,
                        )
                        return
            write(output, "status.json", dict(status=status, at=p.now()), immutable=False)
            time.sleep(30)


def start(root, output=RAW):
    root, output = Path(root).resolve(), Path(output).resolve()
    require(output == RAW.resolve(), "fixed_report_root")
    committed_sources(root)
    current = read(output / "watch_identity.json")
    if (
        current
        and current["process_identity"] is not None
        and controller.process_identity(current["pid"]) == current["process_identity"]
    ):
        return current
    output.mkdir(parents=True, exist_ok=True)
    with (output / "watch.log").open("ab") as log:
        process = subprocess.Popen(
            [sys.executable, str(root / SCRIPT), "watch", "--root", str(root)],
            cwd=root,
            env={
                **os.environ,
                "CUDA_VISIBLE_DEVICES": "",
                "OMP_NUM_THREADS": "2",
                "OPENBLAS_NUM_THREADS": "2",
                "MKL_NUM_THREADS": "2",
            },
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    value = dict(
        pid=process.pid, process_identity=controller.process_identity(process.pid), at=p.now()
    )
    write(output, "watch_identity.json", value, immutable=False)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("register", "run", "status", "start", "watch", "publish")
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    try:
        if args.action == "register":
            value = register(args.root)
        elif args.action == "run":
            value = run(args.root)
        elif args.action == "start":
            value = start(args.root)
        elif args.action == "watch":
            value = watch(args.root)
        elif args.action == "publish":
            value = dict(published=publish(args.root))
        else:
            value = read(RAW / "complete.json") or read(RAW / "status.json")
        print(json.dumps(value, ensure_ascii=False, sort_keys=True))
    except Exception as error:
        if args.action in {"watch", "run"}:
            write(RAW, "needs_attention.json", dict(error=repr(error), at=p.now()), immutable=False)
        raise


if __name__ == "__main__":
    main()
