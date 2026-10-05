"""Read-only, post-hoc Full/C-only submission diagnostics on saved dev883 results.

Selection is fixed from score metadata before any original episode text is read.
No generation, rescoring, private reference reads, API, GPU, or source writes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RUN = REPO / (
    "trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/"
    "v18_researcher_continuation_01"
)
OUTPUT = RUN / "v23_confirmation_shrink_01/submission_diagnostic"
SEEDS = (11, 29, 47)
ARMS = ("full", "c_only")
STATES = ("invalid", "executable_wrong", "executable_correct")
CATEGORIES = (
    "full_invalid_c_correct",
    "both_executable_c_correct_full_wrong",
    "both_executable_full_correct_c_wrong",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode()


def bound(value):
    return {**value, "id": hashlib.sha256(canonical(value)).hexdigest()}


def read_json(path, expected_sha=None):
    raw = Path(path).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    require(expected_sha is None or digest == expected_sha, "source SHA mismatch: " + str(path))
    return json.loads(raw), dict(path=str(Path(path).resolve()), sha256=digest, bytes=len(raw))


def persist(path, value):
    """Publish new analysis only; a subsequent run may verify but never replace it."""
    path = Path(path)
    if path.exists():
        require(
            json.loads(path.read_bytes()) == value, "immutable diagnostic changed: " + str(path)
        )
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        handle.write("\n")


def state(row):
    native = row["native"]
    outcome = native["native"]["execution_accuracy"]
    require(outcome in (0, 1), "unknown/nonbinary outcome")
    if native["status"] == "invalid_prediction":
        require(not native["program_executable"] and outcome == 0, "invalid outcome is not zero")
        return "invalid"
    require(
        native["status"] == "scored" and native["program_executable"], "unrecognized score status"
    )
    return "executable_correct" if outcome else "executable_wrong"


def category(full, c_only):
    return {
        ("invalid", "executable_correct"): CATEGORIES[0],
        ("executable_wrong", "executable_correct"): CATEGORIES[1],
        ("executable_correct", "executable_wrong"): CATEGORIES[2],
    }.get((full, c_only))


def algebra(full, c_only):
    """C-only-reference identity, NOT a causal or common-subset decomposition."""

    def parts(counts):
        total = sum(counts.values())
        valid = counts["executable_correct"] + counts["executable_wrong"]
        require(valid > 0, "conditional accuracy undefined without valid predictions")
        return dict(
            total=total,
            valid=valid,
            correct=counts["executable_correct"],
            v=valid / total,
            a=counts["executable_correct"] / valid,
            J=counts["executable_correct"] / total,
        )

    f, c = parts(full), parts(c_only)
    delta = f["J"] - c["J"]
    validity_term = (f["v"] - c["v"]) * c["a"]
    conditional_term = f["v"] * (f["a"] - c["a"])
    require(math.isclose(delta, validity_term + conditional_term, abs_tol=1e-12), "identity failed")
    return dict(
        full=f,
        c_only=c,
        delta_J=delta,
        validity_term=validity_term,
        conditional_accuracy_term=conditional_term,
        formula="J_F-J_C = (v_F-v_C)*a_C + v_F*(a_F-a_C)",
        causal=False,
        valid_subsets_identical=False,
        interpretation=(
            "descriptive algebra; valid subsets can differ; official denominator unchanged"
        ),
    )


def summarize_pair(full, c_only):
    require(set(full) == set(c_only), "unpaired roster")
    cells = {f: {c: 0 for c in STATES} for f in STATES}
    selected = {name: [] for name in CATEGORIES}
    arm_counts = {arm: Counter({s: 0 for s in STATES}) for arm in ARMS}
    paired_binary = {f: {c: 0 for c in STATES} for f in ("incorrect", "correct")}
    for key in sorted(full):
        f, c = state(full[key]), state(c_only[key])
        cells[f][c] += 1
        arm_counts["full"][f] += 1
        arm_counts["c_only"][c] += 1
        paired_binary["correct" if f == "executable_correct" else "incorrect"][c] += 1
        label = category(f, c)
        if label is not None and len(selected[label]) < 2:
            selected[label].append(key)
    return dict(
        denominator=len(full),
        full_rows_c_only_columns=cells,
        full_binary_rows_c_only_state_columns=paired_binary,
        arm_state_counts=arm_counts,
        algebra=algebra(**arm_counts),
        category_population_counts={
            CATEGORIES[0]: cells["invalid"]["executable_correct"],
            CATEGORIES[1]: cells["executable_wrong"]["executable_correct"],
            CATEGORIES[2]: cells["executable_correct"]["executable_wrong"],
        },
        selected=selected,
    )


def prepare_selection(run=RUN):
    """This phase reads score metadata only: never episode files or raw responses."""
    run = Path(run).resolve()
    paired, binding = read_json(run / "final_evaluation/paired_summary/record.json")
    require(paired["distinct_question_count"] == 883, "dev883 denominator changed")
    sources = [binding]
    by_seed, sample, roster = {}, [], None
    all_counts = {arm: Counter({s: 0 for s in STATES}) for arm in ARMS}
    for seed in SEEDS:
        models = {}
        for arm in ARMS:
            ref = paired["report_bindings"][f"seed{seed}/{arm}"]
            path = (run / f"final_evaluation/models/seed{seed}/{arm}/scores/record.json").resolve()
            require(
                path == Path(ref["path"]).resolve(), "score outside expected dev model directory"
            )
            score, source = read_json(path, ref["sha256"])
            sources.append(source)
            require(
                score["seed"] == seed and score["arm"] == {"full": "Full", "c_only": "C-only"}[arm],
                "model coordinate mismatch",
            )
            require(
                score["denominator"] == 883
                and score["metrics"]["execution_accuracy"]["unknown"] == 0,
                "dev score incomplete",
            )
            models[arm] = {row["task_key"]: row for row in score["results"]}
            require(len(models[arm]) == len(score["results"]) == 883, "duplicate/missing dev task")
            keys = sorted(models[arm])
            if roster is None:
                roster = keys
            require(keys == roster, "different dev rosters")
        summary = summarize_pair(**models)
        by_seed[str(seed)] = {k: v for k, v in summary.items() if k != "selected"}
        for arm in ARMS:
            all_counts[arm].update(summary["arm_state_counts"][arm])
        for name, keys in summary["selected"].items():
            for key in keys:
                sample.append(
                    dict(
                        seed=seed,
                        category=name,
                        task_key=key,
                        scores={
                            arm: dict(
                                state=state(models[arm][key]),
                                stop_reason=models[arm][key]["stop_reason"],
                                reason=models[arm][key]["native"].get("reason"),
                                execution_accuracy=models[arm][key]["native"]["native"][
                                    "execution_accuracy"
                                ],
                            )
                            for arm in ARMS
                        },
                    )
                )
    return bound(
        dict(
            schema="finqa_v23_submission_diagnostic_selection.v1",
            source_run=str(run),
            scope="existing development scores only; not public test",
            sources=sources,
            selection_rule={
                "categories": list(CATEGORIES),
                "per_seed_per_category": 2,
                "order": "task_key lexicographic ascending",
                "if_insufficient": "include all",
                "mutually_exclusive_categories": True,
                "maximum_pairs": 18,
                "post_hoc_error_diagnostic": True,
                "pre_original_text_selection": True,
                "blind_review": False,
                "random_or_representative_sample": False,
                "uses_response_text_for_selection": False,
            },
            by_seed=by_seed,
            pooled_algebra=algebra(**all_counts),
            sample_pair_count=len(sample),
            sample_episode_count=2 * len(sample),
            samples=sample,
            new_API_calls=0,
            new_generations=0,
            new_scores=0,
            original_files_mutated=False,
            private_references_opened=False,
        )
    )


def collect_evidence(selection_path):
    """Require a persisted selection before opening even one saved episode."""
    selection, selection_source = read_json(selection_path)
    require(
        selection["id"]
        == hashlib.sha256(canonical({k: v for k, v in selection.items() if k != "id"})).hexdigest(),
        "selection content ID changed",
    )
    run = Path(selection["source_run"])
    sources, maps, sample_evidence = [selection_source], {}, []
    for selected in selection["samples"]:
        row = {**selected, "episodes": {}}
        for arm in ARMS:
            coordinate = (selected["seed"], arm)
            root = (
                run / f"final_evaluation/models/seed{coordinate[0]}/{arm}/shards/dev883/generation"
            )
            if coordinate not in maps:
                manifest, source = read_json(root / "run.json")
                sources.append(source)
                require(manifest["config"]["role"] == "development", "non-development generation")
                seal, source = read_json(root / "generation_seal/seal.json")
                sources.append(source)
                require(
                    seal["complete"] and seal["registered_denominator"] == 883,
                    "incomplete generation seal",
                )
                maps[coordinate] = (
                    dict(zip(manifest["tasks"], manifest["episode_keys"], strict=True)),
                    {item["key"]: item for item in seal["episodes"]},
                )
            ids, sealed = maps[coordinate]
            eid = ids[selected["task_key"]]
            ref = sealed[eid]
            path = (root / ref["path"]).resolve()
            require(
                path == (root / "episodes" / eid / "episode.json").resolve(),
                "unexpected episode path",
            )
            # Full bytes and all turns, not a tail or snippet. Verify the existing seal.
            episode, source = read_json(path, ref["sha256"])
            require(
                episode["dataset"] + "/" + episode["task_id"] == selected["task_key"],
                "episode task mismatch",
            )
            require(
                episode["stop_reason"] == selected["scores"][arm]["stop_reason"],
                "stop reason mismatch",
            )
            turns = [
                dict(
                    index=i,
                    raw_text=turn["raw_text"],
                    raw_text_characters=len(turn["raw_text"]),
                    parsed_tool_calls=turn["tool_calls"],
                    finish_reason=turn["finish_reason"],
                    tool_call_open_markers=turn["raw_text"].count("<tool_call>"),
                    tool_call_close_markers=turn["raw_text"].count("</tool_call>"),
                )
                for i, turn in enumerate(episode["turns"])
            ]
            row["episodes"][arm] = dict(
                source=source,
                episode_key=eid,
                full_episode_bytes_read=True,
                all_model_turns_retained=True,
                stop_reason=episode["stop_reason"],
                error=episode["error"],
                turns=turns,
                tool_events=episode["tool_events"],
                final_program=episode["final_program"],
                interpretation=(
                    "Observed original output only; no repair, native re-score, "
                    "relabeling, or training reuse"
                ),
            )
        sample_evidence.append(row)
    episodes = [ep for row in sample_evidence for ep in row["episodes"].values()]
    return bound(
        dict(
            schema="finqa_v23_submission_diagnostic_evidence.v1",
            selection_id=selection["id"],
            sources=sources,
            sample_pair_count=len(sample_evidence),
            sample_episode_count=len(episodes),
            sample_stop_reason_counts=dict(Counter(ep["stop_reason"] for ep in episodes)),
            all_selected_original_episode_files_read_in_full=True,
            samples=sample_evidence,
            scope_limits={
                "post_hoc_nonrepresentative_diagnostic": True,
                "blind_review": False,
                "causal_attribution": False,
                "general_population_failure_explanation": False,
                "original_score_changes": False,
                "new_API_calls": 0,
                "new_generations": 0,
                "private_references_opened": False,
                "public_test_opened": False,
            },
        )
    )


def compact_evidence(selection, evidence):
    """Keep provenance and score-level analysis, never copy model/tool transcripts."""
    require(evidence["selection_id"] == selection["id"], "evidence selection binding changed")
    samples = [
        dict(
            seed=row["seed"],
            task_key=row["task_key"],
            category=row["category"],
            scores=row["scores"],
            episodes={
                arm: dict(
                    source=episode["source"],
                    episode_key=episode["episode_key"],
                    stop_reason=episode["stop_reason"],
                    original_full_file_read=episode["full_episode_bytes_read"],
                )
                for arm, episode in row["episodes"].items()
            },
        )
        for row in evidence["samples"]
    ]
    return dict(
        selection_id=selection["id"],
        evidence_id=evidence["id"],
        selection_rule=selection["selection_rule"],
        by_seed={
            seed: {
                name: value[name]
                for name in (
                    "denominator",
                    "full_rows_c_only_columns",
                    "arm_state_counts",
                    "algebra",
                    "category_population_counts",
                )
            }
            for seed, value in selection["by_seed"].items()
        },
        pooled_algebra=selection["pooled_algebra"],
        sample_pair_count=len(samples),
        sample_episode_count=sum(len(row["episodes"]) for row in samples),
        distinct_sample_task_count=len({row["task_key"] for row in samples}),
        sample_stop_reason_counts=evidence["sample_stop_reason_counts"],
        samples=samples,
        scope_limits=evidence["scope_limits"],
        raw_model_turns_and_tool_events_omitted=True,
        original_episodes_reopened_for_summary=False,
    )


def collect_summary(output):
    """Summarize already-saved attachments; do not re-open any original episode."""
    output = Path(output)
    selection, selection_source = read_json(output / "selection.json")
    evidence, evidence_source = read_json(output / "evidence.json")
    for value in (selection, evidence):
        require(
            value["id"]
            == hashlib.sha256(canonical({k: v for k, v in value.items() if k != "id"})).hexdigest(),
            "existing diagnostic content ID changed",
        )
    # These qualitative observations describe only the exact already-read evidence.
    require(
        evidence["id"] == "64a682580db8273a88526fd6e95e38a526ae1512b85f8997a7babc1500a62ffa",
        "qualitative observations cannot be transferred to different evidence",
    )
    return bound(
        dict(
            schema="finqa_v23_submission_diagnostic_summary.v1",
            sources=[
                {**selection_source, "id": selection["id"]},
                {**evidence_source, "id": evidence["id"]},
            ],
            **compact_evidence(selection, evidence),
            qualitative_review={
                "reviewer": (
                    "Codex AI qualitative full-text inspection; not independent human review"
                ),
                "reviewed_evidence_id": evidence["id"],
                "automated_financial_adjudication": False,
                "observations": [
                    {
                        "scope": "six selected Full no_tool_call episodes only",
                        "counts": {
                            "first_turn_plain_text_stop": 4,
                            "first_turn_plain_text_with_explicit_Program_DSL": 3,
                            "successful_run_program_then_plain_text_without_submit": 1,
                            "failed_run_program_then_repetitive_plain_text_to_length_limit": 1,
                        },
                        "description": (
                            "所选六份不是空白输出：四份首轮纯文本结束（三份含 Program DSL）；"
                            "一份成功执行后仅以纯文本给结果而未提交；一份工具报错后重复纯文本"
                            "直到长度上限。以上类别仅描述已读样本，不重判其金融推理正确性。"
                        ),
                    },
                    {
                        "examples": [
                            "seed11/finqa/AAL/2013/page_15.pdf-1",
                            "seed29/finqa/AAPL/2003/page_24.pdf-2",
                            "seed29/finqa/AAPL/2004/page_36.pdf-1",
                        ],
                        "description": (
                            "分别可见纯文本 Program: divide(24800, 15400). 而无调用；"
                            "table_max 成功后未 submit_program；带引号的表行参数运行失败后重复"
                            "声称将执行，但未再次调用工具。"
                            "完整原文保留于 evidence 及其绑定的 episode。"
                        ),
                    },
                    {
                        "scope": "selected pairs with both submissions executable",
                        "description": (
                            "提交程序还存在减法方向、数值选择、百分数尺度、步骤引用与聚合方式差异；"
                            "不能将所有差异概括为缺少提交包装。正确/错误完全沿用既有评分，"
                            "没有重新裁决题意、修复程序或评价推理全文是否正确。"
                        ),
                    },
                ],
                "limits": [
                    "事后错误诊断，选择先于原文阅读；不是盲审、随机样本或总体代表性估计。",
                    "18 对对应 16 个不同问题，跨 seed 重复不能视为独立新问题。",
                    "不得将六份样本外推为全部 no_tool_call 的原因，或推断 N 直接导致提交失败。",
                    "J=v*a 是不同有效子集上的描述性恒等式，不是因果分解；正式分母不变。",
                    "未修复、重评、改标签、生成新回答或将样本回流训练；未读取 public test。",
                ],
            },
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("selection", "evidence", "summary"), required=True)
    parser.add_argument("--run", type=Path, default=RUN)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    require(
        args.output.resolve().is_relative_to(args.run.resolve() / "v23_confirmation_shrink_01"),
        "diagnostic output must be in new V23 analysis subtree",
    )
    if args.phase == "selection":
        value = prepare_selection(args.run)
        path = args.output / "selection.json"
    elif args.phase == "evidence":
        value = collect_evidence(args.output / "selection.json")
        path = args.output / "evidence.json"
    else:
        value = collect_summary(args.output)
        path = args.output / "summary.json"
    persist(path, value)
    print(
        json.dumps(
            dict(
                path=str(path),
                id=value["id"],
                sample_pair_count=value["sample_pair_count"],
                sample_episode_count=value["sample_episode_count"],
            ),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
