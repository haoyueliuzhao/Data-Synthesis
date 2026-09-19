"""Close the registered A matrix using saved scores only; no runtime or model calls."""

# ruff: noqa: E501 -- explicit scientific scope and generated report text
import argparse
import csv
import hashlib
import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import numpy as np

BASE = Path("trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value")
STUDY = BASE / "anchored_sources_20260916/registered_A"
OUTPUT = STUDY / "closure_20260919"
DOCUMENT = Path("trusted_data_synthesis/docs/fixed_kernel_anchored_A_results_20260919.md")
SEEDS = (11, 29, 47)
ARMS = ("Static", "Full", "C_only")
GROUPS = ("dual_sufficient", "composition_required", "other_financial")
CONTRASTS = (("Full", "Static"), ("C_only", "Static"), ("Full", "C_only"))


def require(value, label):
    if not value:
        raise ValueError(label)


def read(path):
    return json.loads(Path(path).read_bytes())


def novelty_fields(update):
    potential = bool(update["novelty_active"])
    coefficient = float(update["numeric_core_update"]["effective_novelty_exponent"])
    return dict(
        novelty_potential_nonzero=potential,
        effective_novelty_coefficient=coefficient,
        novelty_term_active=potential and coefficient != 0,
    )


def identify(report):
    fields = {key: value for key, value in report.items() if key != "id"}
    encoded = json.dumps(
        fields, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    report["id"] = "anchored_A_saved_score_closure:" + hashlib.sha256(encoded).hexdigest()
    return report


def transitions(differences):
    return {
        key: int(np.count_nonzero(differences == value))
        for key, value in (("gain", 1), ("loss", -1), ("unchanged", 0))
    }


def paired_statistics(tasks, scores, *, draws=10000, seed=20260916):
    """CIK resampling scheme reused from the prior closure, with actual arm names.

    A descriptive fixed-checkpoint sensitivity interval, not a holdout confidence
    claim: these development questions were also used in meta learning.
    """
    task_ids = [row["task_id"] for row in tasks]
    require(len(set(task_ids)) == len(tasks), "unique task identities")
    values = np.empty((len(tasks), len(SEEDS), len(ARMS)), dtype=np.int64)
    for j, training_seed in enumerate(SEEDS):
        for k, arm in enumerate(ARMS):
            selected = scores[(arm, training_seed)]
            require(set(selected) == set(task_ids), "complete paired score coverage")
            require(all(value in (0, 1) for value in selected.values()), "binary Q only")
            values[:, j, k] = [selected[tid] for tid in task_ids]
    clusters = sorted({row["source_cluster"] for row in tasks})
    group_index = {group: i for i, group in enumerate(GROUPS)}
    cluster_index = {cluster: i for i, cluster in enumerate(clusters)}
    denominators = np.zeros((len(clusters), len(GROUPS)), dtype=np.int64)
    numerators = np.zeros((len(clusters), len(GROUPS), len(ARMS)), dtype=np.float64)
    pairs = []
    for i, task in enumerate(tasks):
        c, g = cluster_index[task["source_cluster"]], group_index[task["group"]]
        denominators[c, g] += 1
        numerators[c, g] += values[i].mean(axis=0)
        for j, training_seed in enumerate(SEEDS):
            pairs.append(
                dict(
                    task_id=task["task_id"],
                    CIK=task["source_cluster"],
                    group=task["group"],
                    seed=training_seed,
                    **{f"Q_{arm}": int(values[i, j, k]) for k, arm in enumerate(ARMS)},
                )
            )
    require(bool((denominators.sum(axis=0) > 0).all()), "all registered groups represented")
    rng = np.random.default_rng(seed)
    weights = rng.multinomial(len(clusters), np.full(len(clusters), 1 / len(clusters)), size=draws)
    sampled_denominators = weights @ denominators
    valid = (sampled_denominators > 0).all(axis=1)
    require(bool(valid.any()), "nonempty descriptive bootstrap")
    sampled = (
        np.einsum("bc,cgm->bgm", weights[valid], numerators) / sampled_denominators[valid, :, None]
    ).mean(axis=1)
    point = (numerators.sum(axis=0) / denominators.sum(axis=0)[:, None]).mean(axis=0)
    contrasts = {}
    for left, right in CONTRASTS:
        a, b = ARMS.index(left), ARMS.index(right)
        delta = values[:, :, a] - values[:, :, b]
        consistency = Counter()
        for row in delta:
            signs = set(row)
            consistency[
                "mixed_positive_and_negative"
                if 1 in signs and -1 in signs
                else "nonnegative_with_gain"
                if 1 in signs
                else "nonpositive_with_loss"
                if -1 in signs
                else "all_three_zero"
            ] += 1
        contrasts[f"{left}_minus_{right}"] = dict(
            **transitions(delta),
            net=int(delta.sum()),
            denominator=int(delta.size),
            point=float(point[a] - point[b]),
            descriptive_CIK_percentile95=[
                float(x) for x in np.quantile(sampled[:, a] - sampled[:, b], [0.025, 0.975])
            ],
            by_seed={
                str(s): dict(**transitions(delta[:, j]), net=int(delta[:, j].sum()))
                for j, s in enumerate(SEEDS)
            },
            task_seed_sign_consistency=dict(consistency),
        )
    return dict(
        pairs=pairs,
        totals={arm: int(values[:, :, k].sum()) for k, arm in enumerate(ARMS)},
        by_seed={
            str(s): {arm: int(values[:, j, k].sum()) for k, arm in enumerate(ARMS)}
            for j, s in enumerate(SEEDS)
        },
        by_group={
            group: dict(
                denominator=sum(t["group"] == group for t in tasks) * len(SEEDS),
                **{
                    arm: int(values[[t["group"] == group for t in tasks], :, k].sum())
                    for k, arm in enumerate(ARMS)
                },
            )
            for group in GROUPS
        },
        contrasts=contrasts,
        resampling=dict(
            draws=draws,
            seed=seed,
            clusters=len(clusters),
            valid_draws=int(valid.sum()),
            empty_group_draws_excluded_not_redrawn=int((~valid).sum()),
            numpy_version=np.__version__,
            same_weights_all_arms_and_seeds=True,
            training_seeds_resampled=False,
            equal_group_weighting=True,
            scope="descriptive source-reweighting of fixed learned development outcomes; not independent validation, confirmation, or all training randomness",
        ),
    )


def assessment_reason(job):
    root, directory, row = job
    result = read(root / directory / "assessments" / f"{row['index']:04d}.json")
    require(
        result["task_id"] == row["task_id"]
        and result["session_id"] == row["session_id"]
        and int(result["financial_valid"]) == row["Q"],
        "saved assessment score join",
    )
    return "PASS" if row["Q"] else (result["reason"] or "UNSPECIFIED"), result[
        "actual_method"
    ] or "UNDETERMINED"


def collect(root):
    plan, matrix = read(root / STUDY / "plan.json"), read(root / STUDY / "report.json")
    require(
        matrix["status"] == "COMPLETE_SIX_NEW_A_RUNS" and matrix["plan_id"] == plan["id"],
        "complete registered matrix",
    )
    baseline = read(root / BASE / "given_sources_value_20260915/report.json")
    tasks = plan["tasks"]
    require(
        len(tasks) == 180
        and Counter(t["group"] for t in tasks) == Counter({g: 60 for g in GROUPS}),
        "fixed 180 questions and groups",
    )
    scores, reasons, methods, lineage = (
        {},
        {},
        {},
        {"plan": plan["id"], "matrix": matrix["id"], "Static": baseline["id"]},
    )
    for training_seed in SEEDS:
        old = next(
            row for row in baseline["models"] if row["model_key"] == f"A_alpha0_{training_seed}"
        )
        scores[("Static", training_seed)] = {
            r["task_id"]: int(r["financial_valid"]) for r in old["outcomes"]
        }
        reasons[("Static", training_seed)] = Counter(
            "PASS" if r["financial_valid"] else r["reason"] or "UNSPECIFIED"
            for r in old["outcomes"]
        )
        methods[("Static", training_seed)] = Counter(
            r["actual_method"] or "UNDETERMINED" for r in old["outcomes"]
        )
    totals, replay = Counter(), Counter()
    round_rows, run_rows = [], []
    with ThreadPoolExecutor(max_workers=8) as executor:
        for run in plan["runs"]:
            key, training_seed = run["key"], run["seed"]
            arm = "Full" if run["condition"] == "full_anchored_vtdo" else "C_only"
            directory = STUDY / "runs" / key
            final, train = (
                read(root / directory / "report.json"),
                read(root / directory / "training_report.json"),
            )
            scored = read(root / directory / "final_greedy/scoring_report.json")
            selected = {r["task_id"]: r["Q"] for r in scored["scores"]}
            require(
                len(selected) == len(scored["scores"]) == 180
                and sum(selected.values()) == final["final_qualified"],
                "one final score per registered question",
            )
            require(
                final["status"] == "COMPLETE_FIXED_FINAL"
                and train["real_optimizer_updates"] == 400,
                "completed fixed final",
            )
            scores[(arm, training_seed)] = selected
            recorded = list(
                executor.map(
                    assessment_reason,
                    [(root, directory / "final_greedy", row) for row in scored["scores"]],
                )
            )
            reasons[(arm, training_seed)] = Counter(r[0] for r in recorded)
            methods[(arm, training_seed)] = Counter(r[1] for r in recorded)
            lineage[key] = dict(final=final["id"], scoring=scored["id"], training=train["id"])
            totals.update(train["totals"])
            totals["optimizer_updates"] += train["real_optimizer_updates"]
            totals["final_greedy_sessions"] += final["final_greedy_sessions"]
            totals["generate_calls"] += final["actual_generate_calls"]
            start = read(root / STUDY / "launches" / f"{key}.json")["at"]
            run_rows.append(
                dict(
                    run=key,
                    seed=training_seed,
                    condition=arm,
                    qualified=final["final_qualified"],
                    denominator=180,
                    started_at=start,
                    training_finished_at=train["at"],
                    final_finished_at=final["at"],
                    elapsed_seconds=final["elapsed_seconds"],
                )
            )
            for epoch in (0, 5):
                rd = directory / "rounds" / f"epoch{epoch}"
                outer, gradient = read(root / rd / "report.json"), read(root / rd / "gJ.json")
                generated = read(root / rd / "feedback/generation_manifest.json")
                cls = read(root / rd / "full_G.json")
                update = read(root / rd / "distribution_update.json")
                public = read(root / STUDY / "public" / f"{key}_epoch{epoch}.json")
                numeric = update["numeric_core_update"]
                require(
                    outer["actual_feedback_sessions"] == 360 and outer["step"] == epoch * 40,
                    "fixed feedback cohort and actual step",
                )
                require(
                    public["actual_Student_updates_completed_at_milestone"] == outer["step"] + 1,
                    "outer connected to actual next Student update",
                )
                totals["feedback_sessions"] += outer["actual_feedback_sessions"]
                totals["extra_G_sequence_tokens"] += cls["accounting"]["sequence_tokens"]
                replay.update(gradient["accounting"])
                round_rows.append(
                    dict(
                        run=key,
                        epoch=epoch,
                        step=outer["step"],
                        qualified=outer["qualified"],
                        denominator=360,
                        **novelty_fields(update),
                        max_abs_C=public["C_absolute_maximum"],
                        centering_residual=public["centering_residual_maximum"],
                        weighted_TV=numeric["weighted_TV"],
                        weighted_KL_to_current=numeric["weighted_KL_next_current"],
                        weighted_KL_to_prior=numeric["weighted_KL_next_prior"],
                        controls_preserved=numeric["controls_exactly_preserved"],
                        sampling_workers=generated["actual_sampling_GPU_workers"],
                        round_started_at=read(root / rd / "started.json")["at"],
                        generation_finished_at=generated["at"],
                        round_finished_at=outer["at"],
                        report_id=outer["id"],
                    )
                )
    require(
        totals["feedback_sessions"] == 4320
        and totals["final_greedy_sessions"] == 1080
        and totals["optimizer_updates"] == 2400,
        "frozen completed budget",
    )
    paired = paired_statistics(tasks, scores)
    require(
        paired["totals"]
        == {
            "Static": matrix["Static_qualified"],
            "Full": matrix["Full_qualified"],
            "C_only": matrix["C_only_qualified"],
        },
        "paired totals agree with completed matrix",
    )
    pairs = paired.pop("pairs")
    combined_reasons = {
        arm: dict(sum((reasons[(arm, s)] for s in SEEDS), Counter())) for arm in ARMS
    }
    combined_methods = {
        arm: dict(sum((methods[(arm, s)] for s in SEEDS), Counter())) for arm in ARMS
    }
    start = min(datetime.fromisoformat(r["started_at"]) for r in run_rows)
    end = datetime.fromisoformat(matrix["at"])
    result = dict(
        schema_version="anchored_A_saved_score_closure.v1",
        status="COMPLETE_AS_REGISTERED_NO_POSITIVE_FULL_DIRECTION",
        lineage=lineage,
        primary_candidate="Full",
        selected_direction=matrix["primary_direction"],
        B_or_confirmation_started=False,
        new_model_calls_in_closure=0,
        new_scoring_calls_in_closure=0,
        raw_sessions_read_in_closure=0,
        saved_assessments_read_once=1080,
        saved_score_pairs=len(pairs),
        actual_budget=dict(totals),
        feedback_replay_accounting=dict(replay),
        elapsed_wall_seconds=(end - start).total_seconds(),
        completed_at=matrix["at"],
        paired=paired,
        final_assessment_reasons=combined_reasons,
        observed_method_labels=combined_methods,
        runs=run_rows,
        rounds=round_rows,
        interpretation=dict(
            engineering_loop_completed=True,
            positive_training_effect_observed=False,
            effect_is_fixed_development_comparison=True,
            independent_confirmation=False,
            C_only_may_replace_primary=False,
            no_single_cause_claim=True,
            further_B_or_confirmation_requires_new_authorization=True,
        ),
    )
    return identify(result), pairs


def percentage(n, d):
    return f"{100 * n / d:.2f}%"


def markdown(r):
    paired = r["paired"]
    lines = [
        "# 固定材料核 anchored A：六项训练最终结果与限定收口（2026-09-19）",
        "",
        "## 结论",
        "",
        "正式实验已于2026-09-19 08:31（北京时间）完成。六项新训练、十二次外层反馈及六个唯一最终检查点评估均完成；协调器正常结束，不是故障中断。主候选Full没有在本轮固定开发集上取得正的平均收益，保留Static，不启动B池或确认实验，C-only不得替代主候选。",
        "",
        "这是已实现训练闭环的负向开发集结果，不是“训练没有执行”，也不是对VTDO理论或所有任务的一般否定。该180题开发集已参与随机反馈优化，不是独立验证或确认集。",
        "",
        "| 条件 | seed11 | seed29 | seed47 | 合计 / 540 | 合格率 | 相对Static |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for arm in ARMS:
        total = paired["totals"][arm]
        per_seed = " | ".join(str(paired["by_seed"][str(s)][arm]) for s in SEEDS)
        lines.append(
            f"| {arm} | {per_seed} | {total} | {percentage(total, 540)} | {100 * (total - paired['totals']['Static']) / 540:+.2f}个百分点 |"
        )
    lines += [
        "",
        "每个种子分母为180；540是180题在三个固定训练种子上的任务—种子评分次数，不是540道独立题。Static三训练及540次评分按原冻结绑定复用，未重训或重新评分。Full的种子差分别为−7、−18、+8题；C-only为−5、−21、+11题，不能只选seed47的正差报告收益。",
        "",
        "## 同题同种子配对统计",
        "",
        "沿用前轮CIK聚类重采样方案：固定seed=20260916、10000次，共享所有条件及种子的簇权重，保留三组等权，不重采训练种子。此处95%百分位范围仅描述固定已训练模型的开发来源重加权敏感性；因为dev参与过元学习、CIK簇有限且模型固定，不把它解释为独立验证置信区间或覆盖全部训练随机性，也不据此宣称统计显著性。",
        "",
        "| 对照 | 获益配对 | 受损配对 | 不变 | 净变化 | 描述性95%范围（百分点） |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for name, item in paired["contrasts"].items():
        lo, hi = item["descriptive_CIK_percentile95"]
        lines.append(
            f"| {name} | {item['gain']} | {item['loss']} | {item['unchanged']} | {item['net']:+d} | [{100 * lo:.2f}, {100 * hi:.2f}] |"
        )
    lines += [
        "",
        f"实际来源簇数：{paired['resampling']['clusters']}；有效重采样：{paired['resampling']['valid_draws']}/10000。空组样本不补抽。逐任务540行配对表留本地；公开报告只含汇总。",
        "",
        "### 按开发任务组",
        "",
        "| 组 | Static | Full | C-only | 每条件分母 |",
        "|---|---:|---:|---:|---:|",
    ]
    for group, values in paired["by_group"].items():
        lines.append(
            f"| {group} | {values['Static']} | {values['Full']} | {values['C_only']} | {values['denominator']} |"
        )
    lines += [
        "",
        "## 真实外层更新与反馈",
        "",
        "每项从配对原初始化及空Adam开始，不从Static最终模型加训。每次全类G使用3547个A原包、1681个当前Mapper状态及200个任务（含控制）；实际step0/200的360条随机轨迹全部生成封存后才独立评分。gJ通过真实Adam pullback、中心化C和分布更新接入下一次真实SFT；阶段报告在第1/201次optimizer更新完成后才发布。",
        "",
        "反馈使用虚拟一步参数点、T=1、每题两次；最终分数来自epoch10/400步唯一检查点的180次greedy。反馈Q与最终分数不可直接比较，更不是可互换的收益指标。",
        "",
        "| 任务 | 轮次 | 随机反馈 / 360 | Novelty项实际非零 | 加权TV | 对原先pi的KL | 对固定先验KL | 采样GPU数 |",
        "|---|---:|---:|---|---:|---:|---:|---:|",
    ]
    for row in r["rounds"]:
        lines.append(
            f"| {row['run']} | epoch{row['epoch']} | {row['qualified']} | {row['novelty_term_active']} | {row['weighted_TV']:.6g} | {row['weighted_KL_to_current']:.6g} | {row['weighted_KL_to_prior']:.6g} | {row['sampling_workers']} |"
        )
    active = sum(row["novelty_term_active"] for row in r["rounds"])
    potential = sum(row["novelty_potential_nonzero"] for row in r["rounds"])
    lines += [
        "",
        f"Novelty项实际非零{active}/12轮，仅Full的三个epoch5。原包装层novelty_active在{potential}/12轮为true，含C-only的epoch5，但其含义只是诊断潜势N非零，不表示该项进入更新：C-only的effective_novelty_exponent始终为0，Full为0.2。第一轮两臂pi与先验重合，N为0。未修改原始报告或训练，只在本收口明确区分潜势与实际系数。两臂均保留prior KL，不能把C-only说成无先验正则。控制任务分布保留标记均为{all(row['controls_preserved'] for row in r['rounds'])}；最大中心化残差{max(row['centering_residual'] for row in r['rounds']):.6g}。这证明本次有限工程路径被执行，不等于精确多步训练或greedy效用的全导数，也不保证实际最终效用单调。",
        "",
        "## 已消费预算与效率",
        "",
        "| 项目 | 实际 |",
        "|---|---:|",
    ]
    for key, value in r["actual_budget"].items():
        lines.append(f"| {key} | {value:,} |")
    lines += [
        "",
        f"新增金融会话共5400（4320随机反馈+1080最终greedy）；实际generate {r['actual_budget']['generate_calls']:,} 次，低于172800上限。SFT序列/监督token与额外全类G序列token分别计量，不能当成去重语料量或全部GPU计算量。",
        "",
        "| 反馈反传计量 | 实际 |",
        "|---|---:|",
    ]
    for key, value in r["feedback_replay_accounting"].items():
        lines.append(f"| {key} | {value:,} |")
    lines += [
        "",
        "Q=0项在原执行时完成真实性与必要记录检查后省去GPU反传，分母仍为360；缺失、资源故障或回放失败没有当作零奖励。Q=1包含其实际采样的错误、恢复与EOS token，不施加SFT正响应mask。回放计数不包括完整prefill/KV重算FLOPs，cached_forward_target_positions也不是新的generate调用。",
        "",
        f"从首项启动至矩阵收口，墙钟约{r['elapsed_wall_seconds'] / 3600:.2f}小时；不能把并行任务各自elapsed相加当作墙钟。单外层梯度槽包含生成、评分及反传，SFT与适格GPU采样可并行；GPU准入按剩余60GiB、正式主存阈值256GiB，不要求GPU利用率归零。其他任务会等待此槽，等待不等于重复校验。",
        "",
        "R3/R4资源、严格容差、完整前缀伴随与非空Adam控制沿用[既有资源及生产说明](fixed_kernel_anchored_runtime_20260916.md)。本收口未重跑这些控制或旧8/157项测试；只新增并通过三个轻量控制：配对计数/共享簇权重、缺失评分不作零分、非零Novelty潜势不等于C-only启用该项。",
        "",
        "## 保存评分的失败标签（不重新评分）",
        "",
        "聚合脚本单次读取新六项的1080份已保存assessment，Static使用旧已落盘结果；不打开任何原始会话、提示词、模型或梯度张量，不调用模型、工具环境或评分器。下表是评分理由计数，不等于经过轨迹因果分析的失败机制。",
        "",
        "| 保存的reason | Static | Full | C-only |",
        "|---|---:|---:|---:|",
    ]
    reason_keys = sorted(
        {reason for counts in r["final_assessment_reasons"].values() for reason in counts}
    )
    for reason in reason_keys:
        counts = [r["final_assessment_reasons"][arm].get(reason, 0) for arm in ARMS]
        lines.append(f"| {reason.replace('|', '/')} | {counts[0]} | {counts[1]} | {counts[2]} |")
    lines += [
        "",
        "`no_final`不能表述成财务计算答错；支持证明、方法或数量失败也不自动等同某个根因。没有把未确定方法补成目标方法、按答案相等重标方法或修补Final。方法标签汇总保存在JSON，非训练材料的精细类完备性证据。",
        "",
        "## 下一步与证据边界",
        "",
        "1. 本轮收口，保留Static。Full是唯一主候选，C-only即使局部种子更高也不替换候选；B及确认实验均未启动。",
        "2. 已测到本次工程闭环，但未测到本次两个分布干预的正平均收益。不能推广成VTDO在任何数据或超参数上都无效，也不能从负差直接断言实现错误。",
        "3. 如继续研究，建议先用已保存C/pi、任务配对和训练轨迹提出可证伪的偏差来源假设，再另行冻结一个有对照的修订实验。当前未启动新训练、增加反馈轮次/预算、修改任务或增加确认集；这些不冒充本轮自然续跑。",
        "4. 本轮可能的代理目标与最终greedy目标不匹配、跨任务干扰或种子交互均仍是假设，不作已证明因果解释。进一步实验需新的明确范围；原始会话深度审计也尚未执行。",
        "",
        "## 追溯",
        "",
        f"- 登记计划：`{r['lineage']['plan']}`",
        f"- 完成矩阵：`{r['lineage']['matrix']}`",
        f"- 本收口报告：`{r['id']}`",
        "- 数据：[公开汇总JSON](../artifacts/qa_vnext_fixed_kernel_value/anchored_sources_20260916/registered_A/closure_20260919/report.json)",
        "- 逐项实际开始/训练结束/最终结束UTC时间、报告ID、反馈计量和描述性统计均保存在该JSON。原始会话、模型、梯度及逐任务配对表不随本次公开汇总发布。",
        "",
    ]
    return "\n".join(lines)


def finalize_existing_summary(root):
    """Finish this local draft's metadata/rendering without rereading assessments."""
    root = Path(root).resolve()
    report_path = root / OUTPUT / "report.json"
    report = read(report_path)
    require(
        any("novelty_active" in row for row in report["rounds"]),
        "only finalize unannotated local draft",
    )
    for row in report["rounds"]:
        update = read(
            root
            / STUDY
            / "runs"
            / row["run"]
            / "rounds"
            / f"epoch{row['epoch']}"
            / "distribution_update.json"
        )
        row.pop("novelty_active", None)
        row.update(novelty_fields(update))
    identify(report)
    with report_path.open("w") as stream:
        json.dump(
            report,
            stream,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    with (root / DOCUMENT).open("w") as stream:
        stream.write(markdown(report))
    print(
        json.dumps(
            dict(id=report["id"], newly_read_assessments=0, new_model_calls=0, new_scoring_calls=0)
        )
    )


def main(root):
    root = Path(root).resolve()
    output = root / OUTPUT
    require(not output.exists(), "closure already exists; do not reread assessments")
    report, pairs = collect(root)
    output.mkdir(parents=True, exist_ok=False)
    with (output / "paired_rows.csv").open("x", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(pairs[0]))
        writer.writeheader()
        writer.writerows(pairs)
    with (output / "report.json").open("x") as stream:
        json.dump(
            report,
            stream,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    with (root / DOCUMENT).open("x") as stream:
        stream.write(markdown(report))
    print(
        json.dumps(
            dict(
                id=report["id"],
                status=report["status"],
                totals=report["paired"]["totals"],
                new_model_calls=0,
                new_scoring_calls=0,
            ),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--finalize-existing-summary", action="store_true")
    args = parser.parse_args()
    (finalize_existing_summary if args.finalize_existing_summary else main)(args.root)
