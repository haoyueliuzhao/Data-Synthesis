"""Sealed structured-action report; API usage is not Student supervision tokens."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path

import report_finqa_conditional_probe_20260928 as base


def content_counts(episode):
    """Inspect original public raw_text only; never strip it from an episode."""
    turns = episode["turns"]
    base.require(all(isinstance(turn["raw_text"], str) for turn in turns), "invalid raw_text")
    nonempty = sum(turn["raw_text"] != "" for turn in turns)
    nonwhitespace = sum(bool(turn["raw_text"].strip()) for turn in turns)
    single = sum(len(turn["tool_calls"]) == 1 for turn in turns)
    compliant = sum(turn["raw_text"] == "" and len(turn["tool_calls"]) == 1 for turn in turns)
    return Counter(
        episodes=1,
        responses=len(turns),
        zero_response_episodes=int(not turns),
        empty_public_content_responses=len(turns) - nonempty,
        nonempty_public_content_responses=nonempty,
        nonwhitespace_public_content_responses=nonwhitespace,
        single_native_tool_call_responses=single,
        structured_compliant_responses=compliant,
        episodes_with_nonempty_public_content=int(nonempty > 0),
        episodes_with_nonwhitespace_public_content=int(nonwhitespace > 0),
        all_responses_structured_episodes=int(bool(turns) and compliant == len(turns)),
    )


def analyze(run_root):
    root = Path(run_root).resolve()
    # The base refuses to read qualification until both completion barriers exist
    # and verifies the protocol, scope, whole fixed roster and settlement ledger.
    summary = base.analyze(root)
    base.require(
        summary["slot_denominator"] == 1320 and summary["active_task_denominator"] == 165,
        "structured batch requires the complete fixed 165 x 8 cohort",
    )
    bound_files = {row["path"]: row["sha256"] for row in summary["source_evidence"]}

    def read_bound(relative):
        raw = (root / relative).read_bytes()
        base.require(
            hashlib.sha256(raw).hexdigest() == bound_files[relative],
            "completed input changed during reporting",
        )
        return json.loads(raw)

    plan = read_bound("protocol.json")
    seal = read_bound("generation_seal/record.json")
    frozen = read_bound("inventory_complete/record.json")
    config = plan["inventory"]["slot_config"]
    base.require(
        config["harness_id"] == "bigfinance-derived-vtdo-v4"
        and config["submission_profile"] == "finqa_program_v3_structured",
        "old public-output protocol cannot be relabelled as structured",
    )
    counts, total, manifest = defaultdict(Counter), Counter(), []
    for member in seal["slots"]:
        path = Path(member["episode_path"]).resolve()
        base.require(path.is_relative_to(root / "slots"), "sealed episode path outside run")
        raw = path.read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        base.require(sha == member["episode_file_sha256"], "sealed original episode bytes changed")
        episode = json.loads(raw)
        base.require(
            episode["config"] == config and base.digest(episode) == member["episode_sha256"],
            "sealed episode content/configuration identity differs",
        )
        base.require(
            len(episode["turns"]) == episode["actual_model_calls"] == member["actual_model_calls"],
            "original response/actual call accounting mismatch",
        )
        row = content_counts(episode)
        counts[member["slot"]["purpose"]].update(row)
        total.update(row)
        manifest.append({"path": str(path.relative_to(root)), "sha256": sha})
    base.require(
        total["episodes"] == 1320 and total["responses"] == summary["actual_API_requests"],
        "public-content compliance denominator changed",
    )
    states = frozen["train_state_counts"]
    observed = sum(max(0, len(value) - 1) for value in states.values())
    expected_D = observed if frozen["admitted"] else None
    mass = Fraction(sum(len(value) > 1 for value in states.values()), 165)
    base.require(
        frozen["observed_D_pi"] == observed
        and frozen["D_pi"] == expected_D
        and Fraction(frozen["M_flex"]) == mass,
        "stored state-support diagnostics differ",
    )
    base.require(
        frozen["API_tokens_are_not_Student_supervised_tokens"] is True
        and frozen["Student_supervised_token_counts"] is None,
        "token domains conflated",
    )
    state_tokens = frozen["qualified_state_sample_and_API_token_counts"]
    for purpose in ("train", "sealed_diagnostic"):
        packages = sum(
            state["packages"] for task in state_tokens[purpose].values() for state in task.values()
        )
        base.require(
            packages == summary["verdict_counts"][purpose]["CompletePass"],
            "per-state packages differ from original qualified inventory",
        )
    summary["base_report_id"] = summary.pop("id")
    summary["base_report_script_sha256"] = summary.pop("report_script_sha256")
    base.require(
        hashlib.sha256(Path(base.__file__).read_bytes()).hexdigest()
        == summary["base_report_script_sha256"],
        "base report script changed",
    )
    summary.update(
        schema="finqa_structured_probe_descriptive_report.v1",
        report_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        assessed_slots=1320,
        assessed_slots_means_qualification_processed_not_qualified=True,
        public_content_compliance={
            "all": dict(total),
            **{key: dict(value) for key, value in counts.items()},
        },
        content_compliance_definition="empty raw_text + one native call; whitespace separate",
        content_compliance_is_financial_qualification=False,
        observed_D_pi=observed,
        D_pi=expected_D,
        M_flex=str(mass),
        D_pi_null_means_full_registered_task_support_missing=True,
        qualified_state_sample_and_API_token_counts=state_tokens,
        API_tokens_are_not_Student_supervised_tokens=True,
        Student_supervised_token_counts=None,
        Student_encoding_admission_performed=False,
        training_ready_claimed=False,
        canonical_author_DAG_scope_not_all_algebraically_equivalent_solutions=True,
        nontrivial_support_does_not_establish_statistical_power=True,
        new_old_difference_is_joint_protocol_development_observation_not_isolated_cause=True,
        episode_file_hashes_checked=len(manifest),
        episode_file_manifest_digest=base.digest(manifest),
    )
    summary["id"] = base.digest(summary)
    return summary


def markdown(summary):
    result = base.markdown(summary).replace(
        "# FinQA 条件性 Probe 材料库存报告", "# FinQA 结构化公开动作 Probe 库存报告", 1
    )
    counts = summary["public_content_compliance"]["all"]
    value = "null（固定总体支持尚未齐全）" if summary["D_pi"] is None else str(summary["D_pi"])
    return result + (
        "\n## 本轮结构化输出与分布支持\n\n"
        f"`assessed_slots=1320` 表示全部槽已完成资格处理，不表示1320个合格槽。"
        f"全部 {counts['responses']} 次响应中，严格空公开正文 "
        f"{counts['empty_public_content_responses']} 次，非空正文 "
        f"{counts['nonempty_public_content_responses']} 次；其中非空白正文 "
        f"{counts['nonwhitespace_public_content_responses']} 次。"
        f"空正文且恰好一个原生工具调用 {counts['structured_compliant_responses']} 次；"
        "这只是输出合同合规，不等于完整金融资格。\n\n"
        f"`observed_D_pi={summary['observed_D_pi']}`；完整总体 `D_pi={value}`；"
        f"`M_flex={summary['M_flex']}`。存在状态差异也不自动代表充分统计功效。\n\n"
        "逐状态原包数和 API 输入／输出 Token 已保留于 summary.json；"
        "API Token 不是 Student 监督 Token。尚未执行 Student 编码准入，不能宣称训练 ready。\n\n"
        "资格限于冻结的作者锚定规范 DAG，不覆盖全部代数等价解法。新旧差异仅能作为"
        "联合协议修订的开发观察；本报告没有改标签、删正文、合并旧包、重新评分或启动训练。\n"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report-md", type=Path)
    args = parser.parse_args()
    summary = analyze(args.run_root)
    base.write_once(
        args.output / "summary.json",
        (
            json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
            + "\n"
        ).encode(),
    )
    base.write_once(args.report_md or args.output / "report.md", markdown(summary).encode())
    print(
        json.dumps(
            {key: summary[key] for key in ("id", "assessed_slots", "D_pi", "M_flex")},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
