# 固定检查点交付失败诊断：阶段 A/B 实测与工具修复分流

## 1. 结论与当前状态

本次按用户审计执行了阶段 A 的一次有界历史会话扫描，以及阶段 B 的三个训练包
局部合同/监督检查。发现可复现的查询工具实现缺陷，触发“先修复，不带缺陷继续
模型对照”的分支。原固定材料实验、高预算 pilot 的原始成绩和停止决策均不改写。

- 原 1,620 个会话均未获得非空 `query_source` 结果、数值来源读取或成功计算；
  不是已完成财务计算、只在最后一步漏写 Final 的证据。
- `query_source` 拼接显式 null 概念标签/说明时出现 TypeError，原评估有
  **462 / 1,620** 个会话受此错误影响，高预算有 **17 / 27** 个会话受影响。
  这是工具实现问题，但尚不能认定它单独造成了这些会话或全部会话的 no-Final。
- 原评估另有大量合法空查询与无新公开证据的重复查询。高预算 27 对会话前
  32 轮原始响应的 SHA 序列 **27 / 27 完全一致**；此结论来自真实字节比较，
  不再只是 token 总数接近的推断。
- 三个预选训练包的计算与 Final 监督目标均保留，标签及因果移位正确；已有
  九份实际模型恢复/模板收据均匹配。范围仅为三包局部检查与已有收据复用。
- **阶段 C 未启动**。33 个完整会话和 60 个单步续接是原条件性计划，不是
  已完成数量，不填写虚构成绩。本轮没有新增 GPU 模型生成或 API 调用。

## 2. 实验范围与来源

输入为用户粘贴的 325 行审计文本，SHA-256：
`c8c71aec91f6c2290e5300043ff3e36bc7669fa61048afca74f216fdff6bebef`。
审计文本中的另份长报告/ZIP 链接不记作本轮已取得的证据。
执行方案见 [冻结计划](fixed_kernel_delivery_diagnostic_plan_20260915.md)。

新产物统一放在：
`artifacts/qa_vnext_fixed_kernel_value/delivery_diagnostic_20260915/`。
下文路径以 `trusted_data_synthesis/` 为根，原始运行路径以收据为准。

| 来源 | 范围 | 保留的原结论 |
| --- | --- | --- |
| `parallel_tail_execution_20260914` | 180 开发题 × 9 个微调模型 = 1,620 会话 | 无可接受 Final，`STOP_RETAIN_BASELINE` |
| `budget_reevaluation_20260915` | 固定 3 题 × 同 9 模型 = 27 会话 | 64 轮全部耗尽，`STOP_ZERO_QUALIFIED` |
| 本次阶段 A | 分别扫描上述两批现有会话 | 只描述失败位置，不重新评分 |
| 本次阶段 B | 三个确定性选出的 train 原包 | 局部监督/接口检查，不是新训练 |

不继续增加响应预算、不扩评剩余 177 题、不新选方向、不恢复 B 或确认实验；
不生成新 Probe，不新增 HierLoss/anchored 训练，也不打开原确认集。

## 3. 训练模型已经接入什么 Agent 框架

**推理/评估时已接入项目自有的多轮工具 Agent runtime。**实际链为：

```text
公开题面和工具合同
  → 本地 Qwen 基座 + 对应 LoRA 调用 model.generate
  → 严格解析模型 JSON
  → 执行公开来源查询/读取/计算工具
  → 工具结果或错误回填历史
  → 模型下一轮生成
  → 首个顶层小写 final 或预算终止
  → 会话结束后独立财务评分
```

代码证据：

- `src/trusted_synthesis/experiments/finance_qa_vnext_fixed_kernel_value/evaluation.py`：
  实际 `model.generate` 调用及 `generate → runtime.generate(provider=decoder)`。
- `src/trusted_synthesis/experiments/finance_qa_vnext_eval_readiness/runtime.py`：
  `generate` 的多轮回调、工具执行、反馈历史和 first Final 停止逻辑。
- `stage_B/contract_ledger.json`：训练/评测接口及实际恢复证据的汇总。

这不是 LangChain/AutoGen 集成的声明，也不是将 Codex 协作 agent 当作 Student
运行时。模型不是只回答一次聊天消息；工具请求确实被执行并反馈。

**训练仍是固定公开 Probe 轨迹的离线 SFT，不是在线 Student Agent/RL。**
训练时的成功工具调度只有 `read_source / calculate`；评测则要求在完整公开
快照中先发现概念/记录，再读取与计算。接口差异如下：

| 环节 | 训练轨迹运行时 | 开发评测 Agent |
| --- | --- | --- |
| 来源条件 | 已选定的原生 record/pointer 或公开表格 | 完整公开 companyfacts 快照 |
| 读取参数 | `source_id, cells, unit` | `source_id, native_pointer, unit` |
| 发现工具 | 其他工具分派为 unknown_tool | `query_source, list_concepts, read_json` |
| 其他工具 | `calculate` | 另有 `select_max, compare, lookup_selected` |
| 学习/评分 | 离线监督公开响应目标 | 工具观测在线反馈，金融资格不在线反馈 |

因此，“有 Agent 接线”与“模型掌握该 Agent 的完整工具合同”是两件事。
接口迁移是有具体合同差异支持的待检验假设；目前还不能据此认定全部失败的因果来源。

## 4. 阶段 A：一次扫描的真实观测

阶段 A 于北京时间 **2026-09-15 18:56:42.974—18:56:55.478** 完成，
约 **12.5 秒**。执行代码提交为 `2c5e66c925e2bbb973e7f8a349da8162651a80dd`。
只读取两批共 1,647 份 runtime_session 各一次，单文件上限 64 MiB；
不扫描 callback 大请求、不重新计算财务成绩、不调用模型或 API。
后续修复使用一个已定位案例及其一份公开快照，属于定点反例，不是第二轮全量扫描。

### 4.1 会话级别：两批分母分别保留

| 观测 | 原评估 / 1,620 | 高预算 / 27 |
| --- | ---: | ---: |
| 有被 runtime 接受的 Final | 0 | 0 |
| 有疑似 Final 形式 | 0 | 0 |
| 规范 Final 与 runtime 不一致候选 | 0 | 0 |
| 有非空 query_source 结果 | 0 | 0 |
| 有数值来源读取 | 0 | 0 |
| 有成功计算 | 0 | 0 |
| 调用过 list_concepts | 42 | 0 |
| 无发现、无数值读取、无成功计算、无 Final 的联合路径 | 1,595 | 27 |
| 有相同查询且公开证据未变的重复 | 1,191 | 23 |
| 有 null 拼接查询错误 | 462 | 17 |
| 所有响应均为严格 JSON 对象 | 1,603 | 27 |

各行是可重叠观测，不能相减后称作互斥根因。原评估 25 个会话曾取得非空概念
发现返回，仍不等于成功查询到记录或读到金额；“非空查询为零”不能写成所有
来源发现工具都从未返回过任何内容。

### 4.2 响应/事件级别：不与会话分母混用

| 观测 | 原评估 | 高预算 |
| --- | ---: | ---: |
| 实际保存的模型响应 | 51,616 | 1,728 |
| 严格 JSON 对象 | 51,395 | 1,728 |
| 非法 JSON 响应 | 221 | 0 |
| 单次生成以实际 EOS 结束 | 51,544 | 1,728 |
| 单次生成触及新 token 限制 | 72 | 0 |
| query_source 调用 | 39,721 | 1,575 |
| query_source 成功但为空 | 25,257 | 487 |
| query_source 的 null 拼接异常 | 14,446 | 1,088 |
| 相同查询、公开证据未变的重复 | 31,635 | 1,431 |
| 非空 list_concepts 返回 | 439 | 0 |
| read_source 调用 | 10,151 | 121 |
| calculate 调用 | 349 | 0 |

`actual_EOS` 是每条响应的生成停止原因，不是任务完成标志；大部分响应自然
结束但会话持续重复工具请求，与“每条回答都太长写不完”不同。原会话终态仍为
1,601 次 response_budget_exhausted、19 次 provider_error；后者已在原报告中
识别为本地上下文准入拒绝，不改称远端服务故障。高预算为 27 次响应预算耗尽。

所有原 read_source 调用均未得到数值。10,105 次是 numeric_observation_pointer
错误，46 次是参数合同错误；“此前返回未观察到该指针”只是来源可追溯性观测，
不能直接判定模型故意伪造。原 349 次 calculate 均失败，包括表达式语法 180、
未知数值结果引用 136、未定义 revenue 28、单位维度冲突 4、数值字面量 1。
这不支持将 no-Final 解释成“已经正确算完，只是格式不合规”。

### 4.3 配对前缀：实际相同，而非推测

固定 27 对会话的前 32 个原始响应逐条 SHA 对比全部相同。
既有资源收据显示，同一 pilot 从 864 次模型调用增至 1,728 次，新增 token 从
72,024 增至 143,936，均仍无 Final。两项证据合起来说明这次提高预算延长了
既有路径；不能据此推断任何模型、任务或任意更大预算都必然没有帮助。

### 4.4 查询实现缺陷及因果边界

原 `SnapshotSources.query` 在标签过滤中使用：

```python
tag + " " + concept.get("label", "") + " " + concept.get("description", "")
```

字段缺失可使用默认空串，但字段存在且为 JSON null 时 `.get` 返回 None，
从而触发 `can only concatenate str (not "NoneType") to str`。
该异常是工具实现对公开元数据的处理缺陷，不应全部记成模型参数不合格。

原评估 462 个及高预算 17 个会话出现该异常，仍不能认定修复后这些会话必然
获得结果或 Final。查询还可能包含错误单位、概念或期间；其他会话也存在合法
空查询与工具迁移问题。

### 4.5 独立 R1 修复及真实请求反例

新增 `scripts/fixed_kernel_query_null_repair_20260915.py`，修复版本为
`public_query_nullable_metadata:v1:20260915`。通过独立 SnapshotSources 子类，
仅将标签搜索拼接处显式 None 当作缺省空串；不把其他错误类型强制变成字符串，
不改动原快照、返回元数据、单位/概念/日期精确过滤、分页和其他工具。
不全局 monkeypatch，不修改原运行时，不将修复偷偷接入原 C 适配器。

定点反例在北京时间 **19:06:48** 完成：

- 使用阶段 A 已保存的首个受影响小账：模型 `A_alpha0_11`，任务
  `task_02e4542ceffef12de844a17d56f2b4a6548619303c938d5280b32febeec0f99f` 第 1 步。
- 精确原请求保留 `label_contains=netIncome`、`unit=million USD`、
  `start=2010-09-27`、`end=2011-09-25`、`limit=1` 与原 source_id。
- 只读取一份公开 SEC companyfacts 快照：CIK 0000804328，2026-07-08 快照，
  4,314,648 bytes，SHA-256
  `175aaa0b481f51a8c9e2ab9c881bfcc1feb64547b11fe14b70ceb0af6b7ecafc`。
  原模型响应大文件和 callback 均不重读。
- 首个受影响元数据是
  `/facts/us-gaap/EffectiveIncomeTaxRateReconciliationFdiiAmount/label`，
  label 和 description 均为 null。过滤器遍历概念时即可遇到它，不表示这是本题
  应选择的财务概念。
- 旧工具准确复现原 TypeError；新工具正常执行，**total=0、returned_records=0**。
  修复了工具异常，不等于该请求变成正确查询，更不等于模型交付已恢复。

三项新增最小 CPU 控制一次通过（0.09 秒）：null 标签/说明的命中和合法空结果；
正常数据的精确过滤、单位、分页及其他方法不变；原错误类型与参数校验仍保留。
Ruff 通过。首次定点命令因工作树没有 rawdata 在文件读取前停止；指定已有公开
源根目录后执行成功，没有因此重复读取公开快照或重新扫描历史会话。

原 runtime SHA 修复前后均为
`6833fb218c8e41630dc6994d4aec4fa168a504013e1011561903e131fca87d94`，
且匹配 Git blob；模型重评次数为 0。
收据 `stage_A/tool_repair/receipt.json`：
`public_query_repair_receipt:f8c9d91fc2751dd551b48017d950e532c27e6538e28acb05073c6135c0b87aed`。

## 5. 阶段 B：三包局部监督与恢复合同

从三个目标家族各 40 个已见训练任务按冻结的元数据哈希规则预选一个，随后
确定原 A/train 包；不按本次模型输出、损失或是否容易选择任务，不使用 sealed。
仅打开三个原始编码包，不重新分词、不对全部数值数组重新散列、不加载 GPU。

下表区间为零起点、右开区间。实际消费者使用 `target_positions - 1` 取因果 logits。

| 训练家族 | 计算目标 / 因果 logits | Final 目标 / 因果 logits |
| --- | --- | --- |
| annual_flow | 4159:4200 / 4158:4199（41 token） | 4596:4617 / 4595:4616（21 token） |
| stock_rollforward | 5736:5797 / 5735:5796（61 token） | 6352:6378 / 6351:6377（26 token） |
| company_defined_metric | 4171:4215 / 4170:4214（44 token） | 4608:4630 / 4607:4629（22 token） |

三包的原目标位置与标签在实际融合缓存中均保留，label 等于对应输入 token；
计算目标合计 146 token，Final 目标合计 69 token。没有发现这三个样本被整体
遮蔽、丢失 Final 或标签错位。该结果不是 7,076 个包的新全量质量证明，也不是
模型已学会这些目标的证据。

九模型的历史实际恢复收据与模板绑定均匹配；没有再次九次加载模型或哈希基座。
训练时 EOS/模板后缀未纳入注册响应目标这一合同事实保留，但尚不能认定是失败原因。

已冻结六份原 Probe 公开历史：三个家族各计算前、Final 前一份。未来调用只能传
`input_messages`，参考下一条响应只留作离线比较，不能注入输入。Probe 已完成
的发现/读取/计算不能记作 Student 自主成功。本轮六前缀均未执行模型续接。

## 6. 阶段 C 为什么未运行

原 C 只允许改变通用公共 API 说明，使用原工具、原 32/32/2048/24576 预算，
复用旧 27 个微调会话作为旧条件基线。现在发现直接工具实现缺陷，审计要求先修复。

新修复工具记作 R1，原工具记作 R0。R1 + 新说明与旧 R0 会话比较，同时改变
工具和说明，不能声称识别出“说明的单独效应”。也不能偷偷补跑旧条件，扩大
已经冻结的 33 完整会话 + 60 单步、最多 1,116 次生成边界。

本轮保留原 C 的准备适配器与三个 CPU 控制，但不自动加载模型、不产生 GPU
结果，也不把工具修复接进这个仍标记“原工具不变”的适配器。准备控制中发现的
新代码父冻结 ID 选择错误已局部修正；它不是旧 1,620 会话失败的证据。

下一步需要单独冻结 R1 的对照设计：若要识别公共说明的效应，两侧都必须使用
同一 R1 工具；旧 R0 会话只能作为历史背景。若先做工具修复效应，需固定公共
说明，不与 Gamma_doc 混合。未确认新的比较范围前，不启动新增模型实验。

## 7. 核验与归档

已完成的新增 CPU 控制：阶段 A 五项通过（0.09 秒）、阶段 B 三项通过
（0.57 秒）。C 准备控制首次二项通过、一项因新父冻结绑定失败；修正后只重跑
失败项，一项通过（1.93 秒），未重复其余两项。各新脚本的 Ruff 检查通过。
这些是有明确目的的局部实现控制，不是 GPU 模型实验或财务能力证据。

主要收据：

- `stage_A/report.json`：
  `failure_location_report:52cd717e505659b746c43f5f9467bbaeb9c26b3fce9c4e4f3a48596f3f93572f`。
- `stage_A/sessions/`：1,647 个小型失败位置账，各自引用旧 runtime_session 路径和 SHA。
- `stage_B/report.json`：
  `delivery_stage_B_report:1504e5c9d942fb0c437e8ffeab67e73cdbcfa5f7876da1a844a0e4ae490a6259`。
- `stage_B/contract_ledger.json`：
  `delivery_training_evaluation_contract:0488fcf59422ab60613a5223c240fcb47d7eb5554785ea942645924f59e4d3b0`。
- `stage_B/freeze.json` 与 `stage_B/prefixes/`：预选任务、三个原包和六份公开历史前缀。

推送范围收窄为代码、详细报告、阶段 A 汇总、定点工具修复收据和继续门禁。
整目录上传被自动审查拒绝，原因是此前忽略的产物目录内数据未逐项明确；没有
绕过整目录限制。1,647 份每会话小账、阶段 B 收据/冻结记录/六份公开历史前缀，
以及旧的大型原始会话、模型权重和 callback，均保留本地，不声称已全部推送。
原 src 和两个原实验结果目录不做覆盖修复。
