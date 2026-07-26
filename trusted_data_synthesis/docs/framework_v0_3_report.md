# Trusted Synthesis v0.3 修复与验证报告

## 1. 本轮目标

本轮将 v0.2 的“可验证 Reference Compiler”推进为候选中心质量闭环：

```text
Public Task + Evidence Corpus
        -> Candidate Trajectory
        -> 候选行为重建
        -> 隐藏 Oracle 独立复算
        -> Evidence / Program / Answer / Citation / Leakage 门控
        -> Accepted / Quarantined / Rejected
        -> Candidate-aware Release
```

旧金融工程及数据仍位于 `raw_financial_data_lake`，本轮没有修改其代码、
数据库或导出物。

## 2. 已修复的关键问题

### 2.1 Candidate 质量闭环

新增 `CandidateWorkflowVerifier`、`CandidateQualityEvaluator`、
`CandidateAnswerNormalizer`、`CitationVerifier` 和 `OracleLeakageChecker`。
Candidate 不需要携带 Oracle `program_execution`；Verifier 从工具调用、检索
结果、选择记录、计算 observation、最终答案和引用中重建可验证状态。

必需检查覆盖：

```text
public-only boundary              allowed tools
retrieved Evidence validity       selection recall / precision
operation correctness             answer schema / semantic value
Proof Graph ID + content hash     source + locator citation binding
domain claim verification         unsupported status / oracle leakage
```

Reference 与 Candidate 使用不同 required-check manifest。任一检查缺失都会返回
`REJECTED`，不会再因直接字典索引产生 `KeyError`。

### 2.2 Proof Graph v3

`SourceLocator` 成为图节点，并扩展了 document version、字符区间、quoted text
hash、table cell 和 bounding box。`ProofGraphValidator` 验证 Evidence payload、
版本、必需边、定位内容和派生父事实的一致性。Oracle 同时绑定 graph ID 与
graph content hash。

递归闭包会沿 `DERIVED_FROM`、`SUPPORTED_BY`、`QUALIFIED_BY` 和
`CONTRADICTED_BY` 扩展，再恢复每个 Evidence 的 Source、Locator、Time、Scope
和 Definition 边，避免只保留父节点而丢失父证据来源。

### 2.3 Operation Contract 强制执行

Task Program 升级到 v2。跨节点输入使用显式 selector，例如：

```text
lookup.payload.value -> growth
```

Registry 在 Executor 与 Oracle Replay 两侧均校验 verifier ID、输入 schema、
Evidence lineage compatibility、输出 schema 和不变量。Manifest 新增执行器与
Verifier 版本、语义版本、公式、舍入、容差和实现代码 hash。节点失败会形成
带 `node_id` 与错误类别的结构化 `ProgramExecutionError`。

### 2.4 Finance Policy 进入运行时

`FinanceSemanticPolicy` 已同时接入 Evidence Validator、任务构造和质量评测，
检查单位/币种、时间基础、频率、Scope、SourceDefinition、forecast 状态和
跨事实可比性。`FinanceClaimVerifier` 验证结构化 Claim 的证据绑定，并拒绝
因果、预测和投资建议扩展。

这证明 Domain Plugin 已进入主执行链。Legal/Science 仍只验证统一 IR 和
lookup 契约，当前不宣称已具备复杂法律或科学推理。

### 2.5 Corpus、Split 与 Release

`EvidenceCorpus` 可包含 distractor；`TaskPublicSpec.retrieval_track` 显式区分
resolved 与 open。当前内置 Candidate 支持 fact lookup、pair comparison 和
temporal growth，开放检索仍留给后续 Agent。

Split 现在真正执行 `cluster_fields`，未知字段 fail-closed。程序语义 hash 会
移除具体 Evidence ID，因此同一任务结构的不同事实版本不会跨 split。

`CandidateReleaseSelection` 只发布 `accepted` 候选，同时冻结 trajectory、
assessment、failure distribution、domain/task distribution 和 split counts。

## 3. 错误注入覆盖

自动测试明确覆盖：

```text
正确 Candidate 接受
错误或缺失 Evidence 拒绝
错误计算与错误答案拒绝
错误 source locator 拒绝
未知 Claim 拒绝
Oracle ID 预检索泄漏拒绝
越权工具拒绝
缺失 required check 正常拒绝
错误 verifier_id / output_schema 拒绝
Proof Graph locator / content hash 篡改拒绝
Derived Evidence 递归闭包验证
带 distractor Corpus 的 resolved retrieval
Split 配置执行与 Evidence 版本隔离
Candidate Release 仅选择 accepted 数据
全链路确定性复跑
```

## 4. 实际验证结果

本地验证结果：

```text
Ruff lint:                  passed
Ruff format check:          passed
Mypy:                       66 source files, 0 issues
Pytest:                     36 passed
Python compileall:          passed
```

真实冻结金融 KG 只读冒烟：

```text
KG build:                   kg_20260711_062123_bc4b4394
Compatibility:              passed
Fact nodes:                 658,535
All nodes:                  913,475
Edges:                      5,734,348
Demo tasks:                 3
Reference assessments:      3 / 3 accepted, score 100
Candidate assessments:      3 / 3 accepted, score 100
```

GitHub Actions 已增加 Ruff、format、Mypy、Pytest 和 compileall 门控。

## 5. 当前边界

仍未完成且不应过度声明的能力：

```text
Finance Domain Graph pattern mining
复杂过滤、排名与多分支 Candidate Agent
Open-track 搜索与真实外部工具运行时
Legal 规则适用与 Science 多研究综合
持久化 Release Catalog 和大规模生产调度
```

因此 v0.3 的准确定位是：

> 已具备候选中心的、跨证据与程序契约的自动质量闭环，并在真实金融 KG 上
> 完成小规模双工作流验证；跨领域复杂推理与开放检索仍是下一阶段任务。
