# 修订后 QA 链路轨迹抽取

抽取日期：2026-09-07。数据来自已完成的 QA vNext 八任务面板及最新 Share 支持探索，保留公开 Action → Observation → Update → Claim → Final 链路。此次仅对冻结工件进行抽取，不新增模型调用，不重新运行实验，不重新判定资格。

## 数据范围与实际数量

| cohort | 原实验 | 全部会话 | 合格会话 | 公开事件 | 正向监督行 |
| --- | --- | ---: | ---: | ---: | ---: |
| task_panel | fixed_eight_task_panel_v1_20260906 | 16 | 15 | 152 | 113 |
| support_exploration | share_four_neutral_four_guided_v1_20260907 | 8 | 3 | 202 | 21 |
| 文件记录合计 | 两个独立实验 | 24 | 18 | 354 | 134 |

六条不合格会话仍保留在全部轨迹文件中。合计只描述抽取文件大小及记录数，不构成合并实验成功率。Share 实验的 N/E 条件保留在 outcome.profile 中；与八任务面板的任务组成、提示条件存在差异。历史修订前试验、Update 校准、局部 Action 校准和离线 fixture 不纳入本数据集。18 个合格会话不是18个独立任务。

## 人工审阅

[打开合格轨迹审阅索引](review/README.md)。18条合格轨迹各有独立Markdown页面，展示题目、最终答案、证据和全部162次提交（134次准入、28次未准入），保留纠正历史，并提供可展开的完整提交与回执。

## 文件与字段

- `trajectories.all.jsonl.gz`：24 行，每行一个完整会话，保留失败、拒绝、纠正及终止状态。
- `trajectories.qualified.jsonl.gz`：18 行，每行一个合格会话；会话中的未准入历史仍保留。
- `supervision.jsonl.gz`：134 行，每行一个已有正向监督候选，仅来自合格会话的准入提交。
- `manifest.json`：来源文件身份、输出 SHA-256、字节数、记录数、各批统计及完成的检查。

轨迹行含 `cohort`、`label`、`source_run`、原始 `outcome`、`package`、`context`、`protocol`、`registry` 和 `session`。`context.public_task` 保存公开任务；`session.events` 保存有序请求、提交、回执和执行事件；`session.claims` 保存接受的命题；`session.final` 保存最终答案与既有验证结果。原对象不裁剪，不重写数值或来源引用。以 `(cohort, label)` 区分会话，避免跨实验 C01/S01 等标签冲突。

监督行含批次标识和原始 `candidate` 对象。`candidate.messages` 是已有导出中的实际 HTTP 输入消息，`candidate.target_text` 是原始公开响应字符串，保留空白和数字格式；同时保留 Request/Response/Submission/Receipt/Qualification ID、模型归属证据和原始字节哈希。训练输入可读取 messages，目标可读取 target_text。每行是一次独立请求的监督单元，不将不同轮次拼接成虚构对话。

JSONL 外层序列化经过规范化，但解析后的源对象保持一致；目标字符串另行与 runtime 原始响应 UTF-8 字节逐项比对。完整 HTTP envelope 与 tokenizer 数组仍在来源实验目录，本抽取包不复制这些额外工件。

## 验证结果与限制

此次检查通过：两个 analysis manifest 及24个 runtime manifest 的成员字节数/SHA-256；会话身份；监督提交和回执绑定；正向包与候选 ID 集合全覆盖；134条目标与原始响应字节、长度、哈希一致；三个 gzip JSONL 文件解压解析后对象完全一致。输出不覆盖源实验。

资格与模型来源结论沿用既有冻结分析，不声称此次独立重做财务答案审计或 Provider 归属验证。正向监督记录不含失败会话前缀及未准入目标，但输入中的实际纠正反馈仍保留。未赋类权重，不将 quotient 未定改写为已定，不声称 Student 训练效果，也不将公开轨迹称作模型隐藏推理。

## 读取与重建

```python
import gzip
import json

with gzip.open('trusted_data_synthesis/data/qa_vnext_revised_trajectories/trajectories.qualified.jsonl.gz', 'rt', encoding='utf-8') as stream:
    for line in stream:
        trajectory = json.loads(line)
        print(trajectory['cohort'], trajectory['label'], trajectory['session']['final'])
```

从仓库根目录重建到尚不存在的目录（需要本地保留两批原始 artifacts）：

```bash
python trusted_data_synthesis/scripts/extract_revised_qa_trajectories.py --output /tmp/qa_revised_export_new
```

导出器仅使用 Python 标准库；输出路径已存在时拒绝覆盖。源路径固定为本说明的两批实验，gzip 时间戳固定为0，方便重复抽取后核对字节。已提交压缩数据可直接读取，无需下载原始实验工件。

相关实验说明：[八任务面板](../../docs/finance_qa_vnext_fixed_task_panel_collection.md)、[Share 支持探索](../../docs/finance_qa_vnext_same_task_support_exploration.md)。
