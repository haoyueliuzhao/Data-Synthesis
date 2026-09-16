"""One bounded closure: existing paired Q, source-cluster intervals and behavior.

No new scoring, callback scan, model invocation, Final repair or failed-method
relabeling. The nine fine-tuned models'1620 saved sessions are each read once.
"""

# ruff: noqa: E501 -- fixed evidence definitions and generated report text
import argparse
import csv
import json
import subprocess
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction
from pathlib import Path

import numpy as np

from trusted_synthesis.experiments.finance_qa_vnext_catalog_bridge.worker import (
    UNITS,
    convert,
    number,
)
from trusted_synthesis.experiments.finance_qa_vnext_eval_readiness.assessment import _rounded
from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p
from trusted_synthesis.experiments.finance_qa_vnext_task_build.protocol import METRIC_TAGS

BASE = "trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value"
PARENT = BASE + "/given_sources_value_20260915"
OUTPUT = BASE + "/given_sources_closure_20260916"
SCRIPT = "trusted_data_synthesis/scripts/fixed_kernel_given_sources_closure_20260916.py"
DOCUMENT = "trusted_data_synthesis/docs/fixed_kernel_given_sources_closure_20260916.md"
GROUPS = ("dual_sufficient", "composition_required", "other_financial")
ARMS = ("alpha0", "plus", "minus")
SEEDS = (11, 29, 47)
AUDIT_SHA = "075cd030361983a78f5f5fa85d7c39a42aa945ea7ca76f1ee3ccbccfdf7ebe74"


def paired_analysis(report, plan, draws=10000, seed=20260916):
    outcomes = {m["model_key"]: {r["task_id"]: r for r in m["outcomes"]} for m in report["models"]}
    tasks = plan["tasks"]
    clusters = sorted({r["source_cluster"] for r in tasks})
    ci, gi = {x: i for i, x in enumerate(clusters)}, {x: i for i, x in enumerate(GROUPS)}
    denominators = np.zeros((len(clusters), 3), dtype=np.int64)
    numerators = np.zeros((len(clusters), 3, 4), dtype=np.float64)
    pairs, sources, task_signs = [], defaultdict(Counter), defaultdict(lambda: defaultdict(list))
    identities = {r["key"]: r["original_model_identity"] for r in plan["models"]}
    for task in tasks:
        tid, cluster, group = task["task_id"], task["source_cluster"], task["group"]
        c, g = ci[cluster], gi[group]
        denominators[c, g] += 1
        numerators[c, g, 3] += int(outcomes["unfinetuned_base"][tid]["financial_valid"])
        for training_seed in SEEDS:
            keys = {arm: f"A_{arm}_{training_seed}" for arm in ARMS}
            selected = {arm: outcomes[key][tid] for arm, key in keys.items()}
            q = {arm: int(item["financial_valid"]) for arm, item in selected.items()}
            entry = dict(
                task_id=tid,
                CIK=cluster,
                group=group,
                seed=training_seed,
                **{f"Q_{arm}": q[arm] for arm in ARMS},
                plus_minus_alpha0=q["plus"] - q["alpha0"],
                minus_minus_alpha0=q["minus"] - q["alpha0"],
            )
            for arm in ARMS:
                entry[arm + "_terminal"] = selected[arm]["terminal"]
                entry[arm + "_reason"] = selected[arm]["reason"] or "PASS"
                entry[arm + "_training_configuration_id"] = identities[keys[arm]][
                    "training_configuration_id"
                ]
                entry[arm + "_training_backend"] = (
                    "8GPU_global_SUM" if keys[arm] == "A_minus_47" else "single_GPU"
                )
                numerators[c, g, ARMS.index(arm)] += q[arm] / 3
            pairs.append(entry)
            sources[cluster]["paired_task_seed_rows"] += 1
            for arm in ("plus", "minus"):
                delta = q[arm] - q["alpha0"]
                sources[cluster][arm + "_gain"] += int(delta == 1)
                sources[cluster][arm + "_loss"] += int(delta == -1)
                sources[cluster][arm + "_net"] += delta
                task_signs[tid][arm].append(delta)
    p.require(
        len(pairs) == 540 and len({(r["task_id"], r["seed"]) for r in pairs}) == 540,
        "closure.exact540_pairs",
    )
    transitions = {
        arm: {
            name: sum(r[arm + "_minus_alpha0"] == value for r in pairs)
            for name, value in (("gain", 1), ("loss", -1), ("unchanged", 0))
        }
        for arm in ("plus", "minus")
    }
    consistency = {}
    for arm in ("plus", "minus"):
        counts = Counter()
        for value in task_signs.values():
            signs = set(value[arm])
            counts[
                "mixed_positive_and_negative"
                if 1 in signs and -1 in signs
                else "nonnegative_with_gain"
                if 1 in signs
                else "nonpositive_with_loss"
                if -1 in signs
                else "all_three_zero"
            ] += 1
        consistency[arm] = dict(counts)
    rng = np.random.default_rng(seed)
    weights = rng.multinomial(len(clusters), np.full(len(clusters), 1 / len(clusters)), size=draws)
    d = weights @ denominators
    valid = (d > 0).all(axis=1)
    p.require(bool(valid.any()), "closure.bootstrap_nonempty_groups")
    utility = (np.einsum("bc,cgm->bgm", weights[valid], numerators) / d[valid, :, None]).mean(
        axis=1
    )
    point = (numerators.sum(axis=0) / denominators.sum(axis=0)[:, None]).mean(axis=0)
    effects = {}
    for name, left, right in (
        ("plus_minus_alpha0", 1, 0),
        ("minus_minus_alpha0", 2, 0),
        ("alpha0_minus_base", 0, 3),
    ):
        effects[name] = dict(
            point=float(point[left] - point[right]),
            percentile95=[
                float(x) for x in np.quantile(utility[:, left] - utility[:, right], [0.025, 0.975])
            ],
        )
    return dict(
        pairs=pairs,
        transitions=transitions,
        by_source=[dict(CIK=k, **v) for k, v in sorted(sources.items())],
        task_seed_sign_consistency=consistency,
        source_cluster_bootstrap=dict(
            seed=seed,
            draws=draws,
            valid_draws=int(valid.sum()),
            empty_group_draws_retained_not_redrawn=int((~valid).sum()),
            clusters=len(clusters),
            numpy_version=np.__version__,
            resampling_unit="CIK",
            same_weights_all_arms_and_seeds=True,
            group_equal_weighting_preserved=True,
            training_seeds_not_resampled=True,
            effects=effects,
            scope="development source-sampling uncertainty conditional on fixed models; not confirmation or all training randomness",
        ),
    )


def numeric_result(tool):
    return (
        tool.get("status") == "ok"
        and isinstance(tool.get("result"), dict)
        and "exact_value" in tool["result"]
    )


def peak_chain(public, tools, final):
    contract = public["period_contract"]
    primary, secondary = contract["metric_ids"]
    expected = {r["period_id"] for r in contract["periods"]}
    primary_ids, secondary_ids, selections, lookups = {}, {}, {}, {}
    for step, tool in tools:
        if not numeric_result(tool):
            continue
        result = tool["result"]
        if tool["tool"] == "read_source":
            period = result.get("actual_period", {}).get("period_id")
            concept = result.get("concept", "").split(":", 1)[-1]
            if period in expected and concept in METRIC_TAGS.get(primary, []):
                primary_ids[tool["call_id"]] = (period, step)
            if period in expected and concept in METRIC_TAGS.get(secondary, []):
                secondary_ids[tool["call_id"]] = (period, step)
        if tool["tool"] in {"select_max", "compare"}:
            candidates = result.get("selection_candidates", [])
            selections[tool["call_id"]] = dict(
                step=step,
                period=result.get("actual_period", {}).get("period_id"),
                full_periods={r.get("actual_period", {}).get("period_id") for r in candidates}
                == expected,
                primary_references=bool(candidates)
                and all(r.get("result_id") in primary_ids for r in candidates),
            )
        if tool["tool"] == "lookup_selected":
            lookups[tool["call_id"]] = result
    complete = {
        k: v for k, v in selections.items() if v["full_periods"] and v["primary_references"]
    }
    same = any(
        period == selection["period"]
        for period, _ in secondary_ids.values()
        for selection in complete.values()
    )
    after = any(
        period == selection["period"] and step > selection["step"]
        for period, step in secondary_ids.values()
        for selection in complete.values()
    )
    linked = {
        k: v
        for k, v in lookups.items()
        if v.get("selection_result_id") in complete
        and v.get("source_result_id") in secondary_ids
        and secondary_ids[v["source_result_id"]][0] == complete[v["selection_result_id"]]["period"]
    }
    return dict(
        all_three_primary_periods_read={v[0] for v in primary_ids.values()} == expected,
        any_successful_selection=bool(selections),
        full_primary_selection_observed=bool(complete),
        secondary_in_selected_period_read=same,
        secondary_read_after_selection=after,
        successful_linked_lookup=bool(linked),
        final_names_complete_selection=isinstance(final, dict)
        and final.get("selection_result_id") in complete,
        final_names_linked_lookup=isinstance(final, dict) and final.get("result_id") in linked,
        Final_object_observed=isinstance(final, dict),
    )


def final_mismatch(public, tools, final):
    p.require(isinstance(final, dict), "closure.saved_final_object")
    by_id = {tool["call_id"]: tool for _, tool in tools}
    reference = by_id.get(final.get("result_id"))
    flags = {"referenced_numeric_result_exists": bool(reference and numeric_result(reference))}
    detail = dict(
        final_result_id=final.get("result_id"),
        final_value=final.get("value"),
        final_unit=final.get("unit"),
        flags=flags,
    )
    if not flags["referenced_numeric_result_exists"]:
        return detail
    result = reference["result"]
    target, places = (
        public["quantity_contract"]["unit"],
        public["quantity_contract"]["decimal_places"],
    )
    try:
        fv, tv = number(final["value"]), number(result["exact_value"])
        submitted, _ = convert(fv, final["unit"], target)
        supported, _ = convert(tv, result["unit"], target)
        flags.update(
            requested_rounding_mismatch=_rounded(submitted, places) != _rounded(supported, places),
            raw_number_equal_but_unit_labels_differ=fv == tv and final["unit"] != result["unit"],
            difference_within_one_requested_rounding_quantum=abs(submitted - supported)
            <= Fraction(1, 10**places),
        )
        alternatives = []
        for key, tool in by_id.items():
            if key == final.get("result_id") or not numeric_result(tool):
                continue
            candidate = tool["result"]
            if candidate["unit"] not in UNITS or UNITS[candidate["unit"]][0] != UNITS[target][0]:
                continue
            value, _ = convert(number(candidate["exact_value"]), candidate["unit"], target)
            if _rounded(value, places) == _rounded(submitted, places):
                alternatives.append(key)
        flags["another_numeric_tool_matches_submitted_amount"] = bool(alternatives)
        ratio = submitted / supported if supported else None
        flags["exact_factor_100_or_inverse"] = ratio in {Fraction(100), Fraction(1, 100)}
        flags["exact_factor_million_or_inverse"] = ratio in {
            Fraction(1000000),
            Fraction(1, 1000000),
        }
        flags["unresolved_other_numeric_mismatch"] = not any(
            flags[k]
            for k in (
                "raw_number_equal_but_unit_labels_differ",
                "difference_within_one_requested_rounding_quantum",
                "another_numeric_tool_matches_submitted_amount",
                "exact_factor_100_or_inverse",
                "exact_factor_million_or_inverse",
            )
        )
        detail.update(
            tool_value=result["exact_value"],
            tool_unit=result["unit"],
            requested_unit=target,
            converted_final=str(submitted),
            converted_tool=str(supported),
            numeric_ratio=str(ratio) if ratio is not None else None,
            matching_other_result_ids=alternatives,
            interpretation="overlapping patterns, not causal roots; another matching amount does not prove a financially valid replacement",
        )
    except (ValueError, KeyError, TypeError, ZeroDivisionError) as error:
        detail["parse_or_conversion_error"] = str(error)
    return detail


def scan_session(job):
    root, model, outcome = job
    root = Path(root)
    path = (
        root
        / PARENT
        / "generation"
        / model
        / "sessions"
        / outcome["task_id"]
        / "runtime_session.json"
    )
    before = path.stat()
    p.require(
        0 < before.st_size <= 64 * 1024 * 1024 and not path.is_symlink(), "closure.bounded_session"
    )
    raw = path.read_bytes()
    p.require(path.stat().st_mtime_ns == before.st_mtime_ns, "closure.stable_session")
    session = json.loads(raw)
    p.require(
        session["identity"]["task_id"] == outcome["task_id"]
        and session["terminal"] == outcome["terminal"],
        "closure.existing_outcome_session_join",
    )
    public = json.loads(session["public_messages"][0]["content"])
    tools = [
        (i + 1, event["tool_call"])
        for i, event in enumerate(session["events"])
        if event["tool_call"]
    ]
    tags = {
        tag
        for metric in public["period_contract"]["metric_ids"]
        for tag in METRIC_TAGS.get(metric, [])
    }
    reads = [tool for _, tool in tools if tool["tool"] == "read_source" and numeric_result(tool)]
    flags = dict(
        read_non_target_concept=any(
            tool["result"].get("concept", "").split(":", 1)[-1] not in tags for tool in reads
        ),
        successful_calculate=any(
            tool["tool"] == "calculate" and numeric_result(tool) for _, tool in tools
        ),
    )
    peak = (
        peak_chain(public, tools, session["raw_final"])
        if outcome["group"] == "other_financial"
        else None
    )
    if peak is not None:
        peak["runtime_recognized_Final"] = session["first_final_index"] is not None
    return p.record(
        "given_sources_behavior_observation",
        model=model,
        task_id=outcome["task_id"],
        group=outcome["group"],
        source_cluster=outcome["source_cluster"],
        financial_valid_inherited=outcome["financial_valid"],
        actual_method_inherited=outcome["actual_method"],
        first_failure_reason_inherited=outcome["reason"],
        terminal=session["terminal"],
        source=dict(path=str(path.relative_to(root)), bytes=len(raw), sha256=p.sha(raw)),
        flags=flags,
        peak=peak,
        final_mismatch=final_mismatch(public, tools, session["raw_final"])
        if outcome["reason"] == "assessment.final_not_supported_by_result"
        else None,
        failed_method_not_relabelled=True,
        new_financial_assessment=False,
    )


def run(root):
    root = Path(root).resolve()
    output = root / OUTPUT
    p.require(not output.exists(), "closure.one_bounded_analysis")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    p.require(
        (root / SCRIPT).read_bytes()
        == subprocess.check_output(["git", "show", head + ":" + SCRIPT], cwd=root),
        "closure.code_committed_before_scan",
    )
    parent = p.checked(p.read_json(root / PARENT / "report.json"), "given_sources_final_report")
    plan = p.checked(p.read_json(root / PARENT / "plan.json"), "given_sources_value_plan")
    registration = p.record(
        "given_sources_closure_plan",
        audit_sha256=AUDIT_SHA,
        parent_report_id=parent["id"],
        code_commit=head,
        script_sha256=p.sha(root / SCRIPT),
        paired_rows=540,
        bootstrap_draws=10000,
        bootstrap_seed=20260916,
        bounded_session_reads=1620,
        max_session_bytes=64 * 1024 * 1024,
        read_workers=4,
        old_R0_R1_or_callback_scans=0,
        model_calls=0,
        new_scoring_calls=0,
        at=p.now(),
    )
    p.write_once(output / "plan.json", registration)
    started = time.monotonic()
    paired = paired_analysis(parent, plan)
    with (output / "paired_task_seed.csv").open("x", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(paired["pairs"][0]))
        writer.writeheader()
        writer.writerows(paired["pairs"])
    jobs = [
        (str(root), m["model_key"], row)
        for m in parent["models"]
        if m["model_kind"] == "finetuned"
        for row in m["outcomes"]
    ]
    p.require(len(jobs) == 1620, "closure.exact_ft_population")
    grouped, peaks, mismatches = defaultdict(Counter), Counter(), Counter()
    examples, refs = [], []
    with ThreadPoolExecutor(max_workers=4) as executor:
        for count, ledger in enumerate(executor.map(scan_session, jobs), 1):
            path = output / "sessions" / ledger["model"] / (ledger["task_id"] + ".json")
            p.write_once(path, ledger)
            refs.append(dict(id=ledger["id"], path=str(path.relative_to(root))))
            grouped[ledger["group"]].update({k: int(v) for k, v in ledger["flags"].items()})
            if ledger["peak"] is not None:
                peaks.update({k: int(v) for k, v in ledger["peak"].items()})
            if ledger["final_mismatch"] is not None:
                mismatches["sessions"] += 1
                mismatches.update({k: int(v) for k, v in ledger["final_mismatch"]["flags"].items()})
                if len(examples) < 5:
                    examples.append(
                        dict(
                            model=ledger["model"],
                            task_id=ledger["task_id"],
                            ledger_path=str(path.relative_to(root)),
                            details=ledger["final_mismatch"],
                        )
                    )
            if count % 180 == 0:
                print(json.dumps(dict(scanned=count, total=1620)), flush=True)
    report = p.record(
        "given_sources_closure_report",
        plan_id=registration["id"],
        parent_report_id=parent["id"],
        status="COMPLETE_BOUNDED_PAIRED_BEHAVIOR_CLOSURE",
        paired_rows=540,
        paired_table=dict(
            path=str((output / "paired_task_seed.csv").relative_to(root)),
            sha256=p.sha(output / "paired_task_seed.csv"),
        ),
        **{k: v for k, v in paired.items() if k != "pairs"},
        method_labels={
            m["model_key"]: dict(Counter(r["actual_method"] for r in m["outcomes"]))
            for m in parent["models"]
            if m["model_kind"] == "finetuned"
        },
        behavior_flags_by_group={k: dict(v) for k, v in grouped.items()},
        peak_chain_observations=dict(peaks),
        peak_sessions=540,
        Final_mismatch_patterns=dict(mismatches),
        Final_mismatch_examples=examples,
        exact_session_files_read=len(refs),
        session_ledgers=refs,
        flags_overlap_not_exclusive_root_causes=True,
        observed_chain_not_new_financial_qualification=True,
        no_new_method_labels_on_failed_sessions=True,
        callback_files_read=0,
        model_calls=0,
        scoring_calls=0,
        original_alpha0_decision_unchanged=True,
        no_B_or_confirmation_started=True,
        development_pairs_not_training_Contribution_labels=True,
        elapsed_seconds=time.monotonic() - started,
        finished_at=p.now(),
    )
    p.write_once(output / "report.json", report)
    lines = [
        "# 给定来源三臂：配对结果与行为机制收口",
        "",
        f"报告`{report['id']}`；原结果`{parent['id']}`。",
        "",
        "仅分析既有540行task×seed配对；微调模型1,620份会话各读一次。没有新模型调用、重评分、callback扫描或改写Final。",
        "",
        f"成功/失败转移：`{paired['transitions']}`。",
        "",
        f"每任务三种子差异符号：`{paired['task_seed_sign_consistency']}`。",
        "",
        "CSV保留三臂Q、差值、终态、首失败原因和训练配置/后端；A_minus_47仍为8GPU global SUM。",
        "",
        "| CIK | 配对行 | plus得/失/净 | minus得/失/净 |",
        "|---|---:|---:|---:|",
    ]
    for r in paired["by_source"]:
        lines.append(
            f"| {r['CIK']} | {r['paired_task_seed_rows']} | {r.get('plus_gain', 0)}/{r.get('plus_loss', 0)}/{r.get('plus_net', 0):+d} | {r.get('minus_gain', 0)}/{r.get('minus_loss', 0)}/{r.get('minus_net', 0):+d} |"
        )
    lines += [
        "",
        "## 来源簇配对区间（开发描述）",
        "",
        "固定seed20260916、10,000次CIK重采样；同一簇权重用于所有臂/种子，各次保留三组等权。",
        "",
        "| 比较 | 点估计/百分点 | 95%百分位区间/百分点 |",
        "|---|---:|---:|",
    ]
    for name, item in paired["source_cluster_bootstrap"]["effects"].items():
        lo, hi = item["percentile95"]
        lines.append(
            f"| {name} | {100 * item['point']:+.3f} | [{100 * lo:+.3f}, {100 * hi:+.3f}] |"
        )
    lines += [
        "",
        "这只描述固定这些模型的开发来源抽样不确定性，不是确认，不覆盖全部训练随机性；跨零不证明等效。",
        "",
        "## 峰值选择链",
        "",
        f"540会话的重叠观测：`{dict(peaks)}`。",
        "",
        "完整primary选择观测要求三期公开主指标读数及实际选择返回覆盖全部期间；先读后选与选后读另列。不以calculate数量替代选择链，也不新增财务判分。",
        "",
        "## Final失配",
        "",
        f"既有final_not_supported_by_result的模式：`{dict(mismatches)}`。",
        "",
        "结果存在、单位标签、100/百万倍数、接近舍入量子、另一个工具金额匹配和未解数值差异可以重叠，不是已证因果根因；换引用不保证通过完整资格。",
        "",
        f"非目标概念读取/计算：`{report['behavior_flags_by_group']}`。非目标读取不是movement标签；三期聚合不是披露组件重建；失败轨迹未补标movement。",
        "",
        "## 收口",
        "",
        "继续保留alpha0，不启动原三臂B或确认。不改来源、提示、预算、困难组或主指标来救结果。",
        "开发180题与训练200题不同，本配对表不能直接成为训练任务/状态Contribution标签。新C须在真实模型与优化器点、用J_sources反馈计算。",
        "每会话小账留本地；发布配对CSV、汇总与本文，不上传callback原文。",
        "",
    ]
    with (root / DOCUMENT).open("x") as stream:
        stream.write("\n".join(lines))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    result = run(parser.parse_args().root)
    print(json.dumps({k: result[k] for k in ("id", "status", "elapsed_seconds")}))
