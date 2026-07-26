# Finance Pilot v0.4 优化与压力测试报告

## 1. 目标与结论

本轮针对 v0.3 评审指出的评测盲点加固金融主链：

```text
Pinned KG Fact
-> 分层流式抽样
-> Raw Object 解引用与数值复核
-> Gold + 同 Scope 困难干扰 + 普通干扰
-> Public Task / Hidden Oracle
-> Program-bound Candidate Trajectory
-> 独立重放与严格答案、Claim、Citation 门控
-> 多粒度变异定位
-> Accepted-only Release
```

最终结论仍然是：

```text
architecture_feasible = true
production_ready = false
```

框架已经能可靠验证受控、结构化、Resolved Retrieval 金融任务；它还没有证明
真实 LLM Agent、开放检索、大中华区覆盖或跨领域复杂推理达到生产标准。

## 2. 核心修订

### 2.1 真正的困难干扰证据

任务 Corpus 现在同时包含两类干扰：

```text
每题 10 条同实体、同指标、同期间的困难干扰：
错误 SourceDefinition、旧 Build、Forecast、低权威来源、
错误单位、错误币种、错误 Financial Scope

每题 8 条普通干扰：
错误实体、错误期间、错误指标和其他非匹配事实
```

公开检索只使用粗粒度实体、指标和期间，因此困难干扰会真实进入 SEARCH 结果。
Candidate 必须执行隐藏 ID 之外的公开 Selection Contract，才能选择正确版本。

### 2.2 Step 与 Task Program 强绑定

`TrajectoryStep` 新增：

```text
program_node_id
operator_id
input_refs
output_ref
```

Verifier 独立检查：每个 Program Node 恰好执行一次、Operator 与 Input Ref 完全
匹配、依赖顺序满足 DAG、所有计算输出正确、额外未绑定计算不存在，以及 VERIFY
绑定实际 output node。一个正确计算不再能掩盖另一个矛盾计算。

### 2.3 严格 Answer 与 Claim Contract

Answer Validator 对顶层、`result`、payload 和 citation 全部执行
`additionalProperties = false` 语义。诸如正确数值旁附加投资建议的答案会被拒绝。

Finance Claim 只接受结构化的 `observed_metric`、`derived_result` 和
`comparison_result`。Observed Claim 必须精确匹配实体、指标、期间、值、单位、
币种和 Evidence；派生 Claim 必须绑定 Program Node 的实际输出。因果、预测和
投资建议继续 fail-closed。

### 2.4 原始来源真实性复核

Finance Adapter 不再构造不可解引用的伪 JSON Pointer。`SourceLocator` 绑定
`raw_object_id`、真实 `storage_uri`、表/Concept 和行键。Source Grounding
Verifier 会检查：

```text
Raw Object 已登记且 Source 一致
路径被限制在只读归档根目录
文件存在且 SHA-256 一致
SEC/FRED/World Bank 原始响应中存在对应期间与数值
标准化 scale 后的值等于 Evidence value
```

未被原始对象支持的事实会在 Task Binding 之前被隔离。

### 2.5 分层抽样与金融语义

原先的 JSONL 前 20,000 行抽样已替换为全流式或有界流式扫描，并按 region、
metric category、frequency、source 和 verification status 维护确定性 hash
reservoir。`evidence_scan_limit = 0` 表示完整扫描。

相对增长只允许严格正基期，并排除百分比、百分点等不适合普通增长率的指标。
时间窗口要求频率一致和期间连续；财政季度、自然年、月、周和日分别使用明确的
相邻期规则。

### 2.6 泄漏边界与故障定位

Oracle Leakage 只把 SEARCH 之前的 Evidence ID 视为泄漏。SEARCH 返回之后，
Candidate 合法引用已检索 Evidence 不再被误判；Oracle Key 在任何工具请求中仍然
禁止。

Quality Assessment 现在同时保存：

```text
fatal Hard Gate
failed Check ID
Check details
Program Node / Trajectory Step 定位信息
```

## 3. v0.4 压力测试配置

运行配置为 `config/finance_pilot_v04.json`：

| 项目 | 数量 |
| --- | ---: |
| KG Fact 扫描 | 100,000 |
| Domain-valid Fact | 99,203 |
| Reservoir 中执行 Source Grounding | 7,236 |
| Source-grounded Sample | 6,174 |
| Gold Tasks | 48 |
| Task Families | 4 |
| 每题困难干扰 | 10 |
| 每题普通干扰 | 8 |
| 理论变异尝试 | 816 |
| 实际适用变异 | 773 |

任务在 `fact_retrieval`、`comparison`、`temporal_growth` 和
`temporal_average` 间各 12 条。程序深度覆盖 1、3 和 4 个 Operation Node。

## 4. 实际结果

| 指标 | 结果 |
| --- | ---: |
| Task compilation | 48 / 48 |
| Reference accepted | 48 / 48 |
| Clean Candidate accepted | 48 / 48 |
| Mutated Candidate rejected | 773 / 773 |
| Observed critical FAR | 0% |
| 单侧 95% FAR 上界 | 0.387% |
| Clean false rejection | 0 / 48 |
| Hard Gate localization | 100% |
| Check localization | 100% |
| Node/Step localization | 168 / 168 |
| 困难干扰进入检索 | 48 / 48 tasks |
| 困难干扰被误选 | 0 |
| Semantic split leakage | 0 |
| 独立复跑稳定性检查 | 全部通过 |

测试用时约 1 分 13 秒。Release 包含 37 条 train、5 条 dev 和 6 条 test
Candidate，且只包含通过全部硬门控的 clean Candidate。

43 个未生成的理论变异均属于“不适用”，不是漏测：12 条 lookup-only 任务没有
Arithmetic Step，另 12 条没有可注入的冲突计算，12 条没有 VERIFY Step，4 条
缺少适合的时间错位干扰，3 条缺少适合的指标错位干扰。报告显式保留完整分母和
shortfall。

## 5. 原始数据质量发现

7,236 条 reservoir Evidence 中有 1,062 条未通过 Source Entailment：

| 来源 | 拒绝数 |
| --- | ---: |
| FRED observations | 1,061 |
| World Bank indicators | 1 |

典型案例是 FRED `DGS2` 原始值 `0.16` 被旧标准化事实记录为 `16.00`。这表明旧
事实层的部分 `ratio_to_percent` 规则把本身已经以百分比表示的 FRED 序列再次放大。
v0.4 不会让这类事实进入任务，但归档事实构建链仍需修复 scale policy 后重建。

## 6. 验证状态

本地门控：

```text
Ruff check                 passed
Ruff format --check        passed
Mypy                       67 source files, 0 issues
Pytest                     39 passed
Python compileall          passed
```

GitHub Actions 已改为 Python 3.10 与 3.12 双版本矩阵。远端 Workflow 是否成功仍需
由实际 CI Run 证明，不能用本地结果替代。

## 7. 仍未解决的问题

1. 当前 48 条任务全部为 Global；固定 KG 没有可供此 Adapter 使用的大中华区
   graph-ready 数值事实。
2. Source 只有 SEC、FRED 和 World Bank，少于四类来源。
3. 任务仍由确定性 Candidate 执行，尚未测量真实 LLM 的 Critical FAR、FRR 与
   人工一致率。
4. 当前只覆盖 Resolved Retrieval，不覆盖 Web/API 开放搜索、实体消歧和工具故障。
5. 尚未加入 ratio、difference、多公司增长比较、多分支聚合、定义冲突消解等
   中等复杂度任务。
6. FRED scale 错误应在旧事实层修复并重建，而不能长期依赖下游隔离。

## 8. 复现

```bash
cd "/workspace/Data Synthesis/trusted_data_synthesis"
PYTHONPATH=src python -m trusted_synthesis.cli finance-pilot \
  --config config/finance_archive.json \
  --pilot-config config/finance_pilot_v04.json \
  --output-dir artifacts/finance_pilot/v04_100k_final
```

`artifacts/` 为本地实验产物，不写回只读的 `raw_financial_data_lake`。
