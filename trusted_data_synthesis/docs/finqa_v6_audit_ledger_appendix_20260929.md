# V6 系列阶段与账本对账附录（2026-09-29，等待审计）

本附录只读核对既有阶段记录、汇总报告及共同账本。未修改协议或门槛、未重判旧审阅、未启动模型/API/GPU，也未重复读取 Base 的8093份 token 回执。不同审阅版本单列，不能跨版本拼接成功返回或合并成一个通过率。

## 1. 总调用与费用守恒

SQLite 以 `mode=ro`、`PRAGMA query_only=ON` 查询。当前确切总数是 **18,942**，不是19,942：

`18,437 旧生成 + 427 原审阅 + 12 R1 + 12 R2 + 15 R3 + 15 R4 + 12 R5 + 12 R6 = 18,942`。

- 生成：18,437次调用，完成8000个原会话。
- 审阅：505次实际派发，其中504次已取得结算返回，1次保持UNKNOWN。
- 全账本：18,941行SETTLED、1行UNKNOWN；pending=0、halt为空。
- 已结算峰值费率保守上界：**120.043464元**。
- 原UNKNOWN最大预留：**2.228224元**，没有补造usage或改成已结算。
- 总风险占用：**122.271688元**；原800元上限内剩余 **677.728312元**。
- 原请求硬上限258,000不变，剩余请求额度239,058；700元预警不变。

费用是按真实已知usage计算的峰值费率上界，不是供应商发票或实时账户余额。UNKNOWN已按原授权作保守弃置：原行仍为UNKNOWN、预留仍计入占用，只是不再是未处置的停发事件；不得写成“UNKNOWN已经结算”或“unknown总数为0”。

## 2. 各阶段分母、结果与独立费用

| 阶段 | 实际派发 / 已结算返回 | 本阶段登记分母 | 接口/完整校验 | 语义一致 | length返回 | 本阶段新增已结算上界（元） |
|---|---:|---|---|---|---:|---:|
| 旧真实生成 | 18437 / 18437 | 1000题×8槽=8000会话 | 全8000生成封存；不是语义资格 | 未由生成证明 | 2 | 30.665504 |
| 原大JSON审阅 | 427 / 427 | 全队列2000次审阅，实际中止于427 | 完整合同通过0 | 未独立计数；无完整可接受审阅 | 426 | 83.162619 |
| R1 compact | 12 / 12 | 固定6题×双审=12，小批先于2000扩展 | 完整校验0/12 | 未独立计数 | 0 | 1.599296 |
| R2 strict | 12 / 12 | 同固定6题×双审=12 | 完整校验0/12 | 未独立计数 | 0 | 2.355650 |
| R3 分解审阅 | 15 / 15 | 工程小批96逐槽+12对齐；只完成15逐槽、0对齐 | 1/15 | 0/15 | 0 | 0.650226 |
| R4 typed定位（原记录） | 15 / 14 | 同96逐槽+12对齐；0对齐 | 原assessment为0/14；另1次transport UNKNOWN | 0/14 | 0 | 0.597411 |
| R4 独立离线主机绑定更正 | **0 / 0新增** | 只复核上述原14返回 | 更正后12/14；原false门不覆盖 | 0/14 | 0 | **0** |
| R5 空Q栏零损失新类 | 12 / 12 | 同固定6题，各原slot0×双审=12 | 9/12 | 5/12：2 valid、3 invalid | 0 | 0.544372 |
| R6 flat结构 | 12 / 12 | 同固定6题、原slot0×双审=12 | 8/12 | 6/12：4 valid、2 invalid | 0 | 0.468386 |
| 合计（不重复计R4离线复核） | **18942 / 18941** | 不合并不同阶段的科学分母 | 不汇成跨版本通过率 | 不拼接各版正例 | **428** | **120.043464** |

R4另外保留2.228224元UNKNOWN预留，该项不是上述已结算费用。表中length合计428仅用于响应状态账目（生成2+原审阅426），不构成跨任务、跨协议的成功率或模型能力指标。

原始大JSON阶段的唯一非length返回也没有满足证据契约：138个引文全部为空。R1为5次JSON错误、7次引用定位错误。R2旧版记录将JSON/schema/证据/过程一致性合并为完整校验，并未登记后来R3使用的独立 `interface_admitted` / `semantic_consistent` 两率，因此不能事后把“0完整通过”伪装为同口径的接口或语义发生率。

R4原14份assessment均受主机落盘排序/定位重建绑定问题影响；离线复核是单独的新证据对象，12接口通过不替换旧门，也不增加API调用。复核仍有2个实际JSON错误，12个其余返回均未通过完整语义一致性。空Q栏与实质语义问题不能混为一类金融错误。

R5/R6的单份valid也不是训练包：还需要同版本双审、Q_native、完整状态映射和统一mask/Student编码。两轮均未达到各自登记的12/12技术要求，没有自动放大至108或全量复审。R3/R4亦未完成原96+12小批；已实际运行的部分不能当作完整108次试验。

## 3. 已完成研究工作与仍然阻塞的主线

| 工作 | 已验证状态 | 不能声称的结论 |
|---|---|---|
| 旧Experiment0生成 | 原1000题、8000会话完整；native execution 4109/8000（51.3625%） | 不是已准入的共同语义材料核 |
| 旧材料任务支持上界 | 224题的8槽均无native正确；共同Q/V支持最多776题 | 审阅不能凭空补齐原1000题；不能静默删题训练 |
| 新V7整批 | 已登记同1000题×8全新槽；`REGISTERED_NOT_STARTED`、`execution_admitted=false`、新调用0 | 不是已经重新采集8000条；不得拼接旧批成功 |
| Base dev883 | 完整生成和评分；execution33/883、program6/883、未知0；原两worker退出；API调用0 | 不是五臂训练收益；不能据dev反向改prompt/资格 |
| Experiment1–3 | 五臂/3seed设计与固定2000步五任务日程已登记；`DESIGN_AND_CPU_READINESS_ONLY`、`BLOCKED_MATERIAL_CLAIMS` | Static/Manual±/C-only/Full尚无真实训练结果 |
| Experiment4 | 冻结平滑C及尺度的数学子问题与纯CPU合成控制已完成；0模型/API/GPU调用 | 不是实际Student闭环收敛或算法训练价值证明 |
| Experiment5及独立消融/test | 保留后续独立登记范围 | 未执行，不自动展开 |

Experiment4原件包含161条迭代记录（初值0至第160次更新）及256对随机控制；观测最大距离比约0.8000000000000003，数学充分条件的收缩上界为0.8，浮点末位不解释为理论违例。其证书明确要求固定平滑后的C及尺度、正归一化概率，并明确 `real_training_closed_loop_convergence=false`。

当前主要阻塞是材料与审阅接口/语义/映射/编码准入，而不是已花完800元预算。资金余额不构成放宽门槛、继续未登记付费重试或将未知转为正例的理由。用户已要求后续等待审计，本附录不提出或启动新实验。

## 4. 核对来源

除Base与设计项另注明外，以下相对路径均位于：

`trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/`

- 共同账本：`experiment0_01/budget.sqlite3`，仅只读查询计数、状态与金额；没有导出数据库或认证信息。
- 旧生成：`experiment0_01/generation_seal/record.json`。
- 原审阅427计数、原始累计费用：`review_revision_01/historical_audit/record.json`。
- R1/R2：各自 `capacity_gate/record.json` 与 `capacity_audit_report_01/record.json` 的独立runs记录。
- R3：`review_revision_03/technical_gate/record.json`、`status.json`。
- R4：`review_revision_04/technical_gate/record.json`、`status.json`、`offline_binding_correction_01/record.json`；UNKNOWN处置位于 `unknown_disposition_01/`。
- R5/R6：各自 `result/record.json`、`started/record.json` 和逐份既有assessment汇总。
- 新V7登记：`new_full_probe_v7_01/registration/protocol.json`，ID `ed78f27d36129f3668f40914824178ce5604b25c60ffc030b1fbb0b90703e1bb`。
- Experiment4：`experiment4_01/record.json`，ID `finqa_v6_experiment4:97e43c1da30d7d2f1276da671b7590b523a0233de7554e42551593e951a22ccc`。
- Base：同级 `../finqa_five_arm_mainline_20260929/base_dev883_01/status.json`、`scores/record.json`，详细核验沿用 [Base终报](finqa_v6_base_dev883_report_20260929.md)，未重复做token回放。
- 主训练设计：同级 `../finqa_five_arm_mainline_20260929/experiment123_design_01/registration/protocol.json`，plan ID `v6_experiment123_design:1d3f865325e3f5e2946131f2331cd7836cb1f2f82c5e424a844d0df473bed436`。

费用再用SQLite执行坐标namespace独立聚合核对：`v6-slot`18437次/30.665504元；`v6-review`427次/83.162619元；`v6r1-review`24次/3.954946元；`v6d3-slot`29次已结算/1.247637元加1次UNKNOWN；`v7m5`12次/0.544372元；`v7flat6`12次/0.468386元。R1/R2和R3/R4各自拆分金额来自不可变阶段累计值之差，分项和与账本总额完全相等。
