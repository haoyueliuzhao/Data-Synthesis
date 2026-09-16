"""Publish only the bounded same-token control when its one queued run finishes.

No retry, model call, training release, B or confirmation. The user authorized
normal commits/pushes to main; publication failures remain explicit local records.
"""

import argparse
import fcntl
import os
import subprocess
import time
from pathlib import Path

from trusted_synthesis.experiments.finance_qa_vnext_fixed_kernel_value import protocol as p

OUTPUT = (
    "trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/"
    "anchored_sources_20260916/gpu_cached_replay_r2"
)
DOC = "trusted_data_synthesis/docs/fixed_kernel_anchored_sources_cached_replay_20260916.md"


def document(report, plan):
    lines = [
        "# 同一虚拟点、同一已采样token的缓存回放修复",
        "",
        f"状态：`{report['status']}`。完成：`{report['finished_at']}`（UTC）。",
        f"报告：`{report['id']}`；冻结代码：`{plan['code_commit']}`。",
        "",
        "## 执行范围",
        "",
        "只使用原GPU检查保存的两段输出，2+8个token。未新增model.generate、随机回答、",
        "金融评分或optimizer.step。旧整段回放的长上下文失配报告保留，没有改写为通过。",
        "修复重建原诊断梯度和虚拟参数并要求摘要完全一致，随后采用同样的prefill/逐token",
        "KV路径；缓存不detach，反传保存张量移至CPU，不替换概率、不放宽容差。",
        "",
        "| 上下文 | 输入token | 已有输出token | 最大logP差 | 容差通过 | 梯度有限 |",
        "|---|---:|---:|---:|---|---|",
    ]
    for case in report["cases"]:
        lines.append(
            f"| {case['context']} | {case['prompt_tokens']} | "
            f"{len(case['generated_token_ids'])} | {case['maximum_absolute_difference']:.12g} | "
            f"{case['passed']} | {case['finite_gradient']} |"
        )
    lines += [
        "",
        f"实际耗时{report['elapsed_seconds']:.2f}秒；CUDA reserved峰值"
        f"{report['peak_reserved_bytes'] / 2**30:.3f}GiB；真实参数、optimizer、grad、mode及RNG"
        f"保持不变：`{report['real_state_unchanged']}`。",
        "原atol=1e-6、rtol=1e-5不变；这是所列token的检查，不是误差上界证明。",
        "",
        "## 证据边界与后续",
        "",
        "通过时只说明该反例在同点同token的缓存路径得到修复；不证明所有长序列或所有",
        "360条反馈均已具备生产条件。失败时保留实际错误，不自动重跑或改阈值。",
        "CPU offload短输出结果不可直接外推到24,576上下文×2,048输出，后者的缓存图",
        "内存与调度仍需生产适配。完整反馈生成/封存后独立评分、全总体G与pullback接线、",
        "最终训练日程尚未完成整体生产准入。自适应A、B及确认均未由本控制放行。",
        "",
        "当前分布实验仍保留原alpha0；没有新的anchored训练收益结论。",
        "新增必要CPU控制累计8项通过，未重复旧157项测试或既有1,620会话扫描。",
    ]
    if report["error"]:
        lines += ["", "实际错误：`" + str(report["error"]) + "`。"]
    return "\n".join(lines) + "\n"


def run(root):
    root = Path(root).resolve()
    out = root / OUTPUT
    with (out / "publication.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        p.require(not (out / "publication.json").exists(), "cached_publish.one_publication")
        started = p.read_json(out / "queue_started.json")
        while not (
            (out / "report.json").exists()
            and '"worker_returncode"' in (out / "queue.log").read_text()
        ):
            os.kill(started["pid"], 0)  # a dead queue is a failure, not endless silent waiting
            time.sleep(30)
        try:
            report = p.checked(
                p.read_json(out / "report.json"), "anchored_sources_cached_replay_report"
            )
            plan = p.checked(p.read_json(out / "plan.json"), "anchored_sources_cached_replay_plan")
            p.require(report["plan_id"] == plan["id"], "cached_publish.plan_report_binding")
            with (root / DOC).open("x") as stream:
                stream.write(document(report, plan))
            paths = [OUTPUT + "/plan.json", OUTPUT + "/report.json", DOC]
            paths += [OUTPUT + f"/cases/{index}.json" for index in range(len(report["cases"]))]
            subprocess.run(["git", "add", "--sparse", "-f", "--", *paths], cwd=root, check=True)
            subprocess.run(
                [
                    "git",
                    "commit",
                    "--only",
                    "-m",
                    "Record bounded same-token cached replay result without releasing training",
                    "--",
                    *paths,
                ],
                cwd=root,
                check=True,
            )
            commit = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=root, text=True
            ).strip()
            subprocess.run(
                [
                    "git",
                    "-c",
                    "http.proxy=",
                    "push",
                    "https://github.com/haoyueliuzhao/Data-Synthesis.git",
                    "HEAD:main",
                ],
                cwd=root,
                check=True,
            )
            p.write_once(
                out / "publication.json",
                p.record(
                    "anchored_cached_replay_publication",
                    commit=commit,
                    paths=paths,
                    at=p.now(),
                    full_A_released=False,
                ),
            )
        except BaseException as failure:
            p.write_once(
                out / "publication_failure.json",
                p.record(
                    "anchored_cached_replay_publication_failure",
                    type=type(failure).__name__,
                    error=str(failure),
                    at=p.now(),
                    automatic_retry=False,
                ),
            )
            raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    run(parser.parse_args().root)
