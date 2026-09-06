# Action 公开合同修复与原 B 任务两会话完整可达性

日期：2026-09-06。阶段：`finance_qa_vnext_action_public_contract_repair_and_branch_reachability_pilot`。

## 1. 授权与不变的历史结论

本轮由用户“参照审计继续实验”授权实施。用户审计原文 552 行、27,163 bytes，SHA-256 `faed220ec5e344741d239883beb3d05020f1d65e82d045a3c98bca19aec0ebeb`；实际准备将保存完整原始字节。

前序结果保留：最早完整试验 1/12，指定 accept 的单步 O/R 校准 0/12 与 12/12，随后六个完整会话 C 2/2、B 0/2、S 2/2（4/6）。六会话中的 13 个动态 Observation 都首次 accept 并 commit，C/S 已有完整见证；B 的主要消耗为 54 次 Action 候选全集遗漏拒绝，尚未进入真实增长和分支合并。

本轮只修复已经由源码和实际请求共同定位的 Action 模型侧公开缺口，然后只对原 B 任务运行两个全新完整会话。不重复 C/S 或 24 次单步校准，不修改历史工件，不将不同生成条件的成功拼成“同条件 6/6”，不声称无同期对照的前后差值是精确因果效应。

## 2. 有限 Action publication 与反馈

新增 `finance_qa_action_public_contract.v1`，以当前请求中的 `public_action_contract` 给出静态公开关系和表达式。Runtime Request 与独立测量重建均加入此 publication 并获得新 Request ID；原 `finance_qa_public_decision_protocol.v2`、Submission Schema 和 `finance_qa_update_public_contract.v1` 保持原样。

| Action 响应字段 | 公开来源或规则 |
| --- | --- |
| state_id | 当前 `/state/id` |
| decision.candidate_action_ids | 当前全部 `/available_actions` 的 id，集合相等且不重复，清单顺序不限 |
| decision.selected_action_id | 模型自行选择当前可用集合中的一个 id |
| operation / inputs / parameters | 完整对应这同一个选中项，保留原 JSON 内容与数组顺序 |
| decision.obligation_id / subgoal / basis / expected_effect | 同一个选中项的对应字段，不混用其他候选 |
| decision.selection_rule | 该选中项 selection_rules 的一个成员 |
| decision.unresolved_uncertainty_refs | 原规则要求的空数组 |
| Claim 依赖 | 当前 State 中 status=accepted 的 Claim；保持原角色、selector 和依赖约束 |

`candidate_action_ids` 是接口要求的完整当前清单，不是选中项、不只是模型考虑的子集，也不是某个 obligation 内的候选。新 growth 可能在接受 lookup Claim 后出现，不能实现为从初始四个 ID 单调删除。只有候选 ID 清单按无序集合比较；inputs、basis 等其他数组仍按原合同处理。列全 ID 本身不是逐个内部比较、关键推理或 VTDO Contribution 的证据。

对 `admission.alternative_set`，新反馈只提供该公开 rule_id、当前 ID 的集合路径以及 missing_ids / extra_ids / duplicate_ids。选中项字段不一致时只标出字段和 selected binding 来源。不会替模型选择 Action、补齐其清单、修改原响应或在没有新模型提交时继续执行。Update 及 Final 的反馈分支原样委托既有实现；不改 Final 答案投影或 Share 路线偏好。

## 3. 原标准保持与局部零调用检查

基线提交为 `5df110cc6b98bd65658ad4204c3ccd5b4ec1c9a7`。准备要求：

- `protocol.py`、`canonical_json.py`、`update_public_contract.py`、Program/Share adapter 字节均不变；因此 Schema、数值与 Final 验证标准不变。
- Runtime `_admit` 与独立测量 `_admission` 的 AST 不变。运行新增 readonly Action 入口时，直接调用原 `_admit`，包括既有纯 adapter.prepare；不构造运行会话、不执行金融 Operation、不 commit、不调用 Provider。

控制优先读取前序真实 B01/B02 Request：覆盖 2/3/4 个可用候选，以及 lookup 接受后出现非初始 growth 候选的动态状态；另读一个 C 单候选、一个 S 多候选请求作局部接线检查。隔离接收端仅解释 publication 的公开路径、集合、选中项绑定和选择表达式，不导入旧 action_response 或 Runtime 私有构造。

共 6 个实际来源请求、69 个局部控制，每个响应在原请求和加入 publication 的请求上都走同一原准入路径（138 次只读准入评价）。包括任一合法选中项、候选清单换序、选中项/合法子集遗漏、重复、额外、旧初始全集、错误选中 ID、混用 operation/basis，以及 inputs 换序仍拒绝。两种呈现的合法/非法结果和错误码必须一致；这些不是 69 个模型样本。

读取既有完整 B fixture 的 17 个阶段请求，仅检查新完整 HTTP 请求字节预算，不重新执行旧 lookup/growth。检查包括后期增长、signed gap、absolute gap 及 Final；当前检查最大为 78,532 bytes，低于 98,304。真实在线每次请求仍由原传输层单独执行字节准入，不按离线结果豁免。

## 4. 调用前冻结的在线总体

| 项目 | 冻结值 |
| --- | --- |
| Task/Context/Evidence/Operation | 原 B：CDW FY2015/FY2016 分支合并，完全沿用原来源和数值 |
| 会话 | 新 B01、B02，两条独立新 session/transport 身份，不续接历史 Claim |
| 初态 | accepted Claims=[]、pending=null、计数 0、feedback=null |
| 调度 | 一个固定轮次，按 B01/B02 登记启动，并发最多 2；不按结果调整顺序 |
| 教师条件 | deepseek-v4-pro；thinking disabled；temperature=0.7；top_p=1.0 |
| 消息 | 原中性完整任务 SYSTEM_PROMPT + 当前完整公共 Request；无 accept-only 或固定执行脚本 |
| 每会话 Action / Submission / Provider attempt | 12 / 32 / 32，含 Final |
| Provider 总上限 | 64 |
| 输出 | JSON object，非 stream，max_tokens=8192 |
| 完整 HTTP body 上限 | 98,304 bytes；输入准入代理 body bytes+1024，上限 99,328 |
| 时限 | 总 deadline 180 秒，连接 30 秒 |
| allowance | 每次 107,520，每会话 3,440,640，总上限 6,881,280；不是实际用量 |
| 自动网络重试 / 回退 / 失败替换 | 0 / 0 / 0 |
| 新来源 / C/S 在线重复 / Student / GPU | 0 / 0 / 0 / 0 |

合法 Final 立即停止；两条都失败也不提高上限、不补样。结构或公开语义拒绝后的纠正是新的模型响应，计入原预算；旧响应不修写。完整记录的资源/超时/无内容终止按既有资格规则判断，缺失或内部无法确定的证据保留 unknown。已启动的并发会话均保留，不因另一条失败而替换。

准备绑定设计、全部 Python 源文件与提交、软件与 tokenizer-only 资源、生成配置、两行登记、两个初始 Request/HTTP、局部控制，以及前三阶段的完整工件清单。TaskPanel 的本轮 coverage 只选 B（1 个类型）；另 7 个有来源类型未在本轮在线测量，3 个类型来源未实例化。旧 C/S 见证不挪入这一新条件。

## 5. 主结果、真实推进与附加测量

完整成功仍为有效 Final ∧ 独立 QA 验证 ∧ 轨迹验证。两行均可判定时 q_B,new=(Y1+Y2)/2；unknown/not_started 不填零、不删除后重归一化。至少一个 Qualified 完整 B 会话即可提供当前条件的构造见证，不要求 2/2；两个样本也不能精确估计稳定总体能力。

逐会话报告当前全集准入、lookup Claim commit、第一个实际非透明操作、growth 对 accepted lookup Claim 的真实消费、两条 growth 依照原角色进入 signed gap、signed gap 进入 absolute，最后是否有效 Final。每个阶段引用实际 Receipt、Observation、Claim 与输入角色/selector；只说“要做 growth”不计执行。

实际深度从既有事件图恢复，完整轨迹和失败前缀分开。lookup 是透明操作，不把 lookup 个数或纠正次数充当语义深度。逐 Observation 的第一次 Update、最终 accept/reject、处理提交数及 Claim 消费仍保留；候选全集正确率不得补偿没有完成的任务。

若存在 Qualified B，会同轮通过原导出器保存完整真实请求—原样准入响应监督候选，排除失败前缀和未准入响应；做既有 24,576 Token 检查，过长保留原候选与诊断、不截断、不回写为轨迹失败。至多一个同任务 Qualified 无序配对交由既有限投影；纠正导致 projection undetermined 时仍保留资格。不构建新 Mapper、Assignment、类权重、Contribution 或训练。

## 6. 入口、测试和工件管理

从仓库根目录运行：

```bash
PYTHONPATH=trusted_data_synthesis/src trusted_data_synthesis/.venv/bin/python \
  -m trusted_synthesis.experiments.finance_qa_vnext_action_branch prepare \
  --root "$PWD" --preparation /absolute/new-run/preparation \
  --design /absolute/audit.txt --run-tag action-branch-20260906

PYTHONPATH=trusted_data_synthesis/src trusted_data_synthesis/.venv/bin/python \
  -m trusted_synthesis.experiments.finance_qa_vnext_action_branch run \
  --root "$PWD" --preparation /absolute/new-run/preparation

PYTHONPATH=trusted_data_synthesis/src trusted_data_synthesis/.venv/bin/python \
  -m trusted_synthesis.experiments.finance_qa_vnext_action_branch analyze \
  --root "$PWD" --preparation /absolute/new-run/preparation --output /absolute/new-analysis
```

真实运行不可 resume、重复启动或覆盖已有目录；read-only analyze 不可写入已封存 execution。历史原始工件不变。本轮代码、文档和新工件按用户授权提交并推送同一仓库 main。

新增接线测试包括全集和对应字段的反馈、两种合法调度、纠正、已知失败、unknown、空正向池、64 次上限及只读重分析。另在提交源码后执行真实 CLI prepare/读回/完整双 B 模拟 HTTP 往返；模拟数据不是 Provider 样本。相关 Runtime/测量/资格回归的手写测试轨迹需要加入新 publication；初次遗漏使 11 项先报 `event.actual_request`，现仅更新测试请求呈现，不放宽读者或原标准。初次失败记录将与最终通过记录分别保留。

## 7. 实际结果

调用前记录：新增 23 项测试和 69 项局部控制已通过；相关回归与真实已提交 CLI 往返仍在完成。尚未发起本轮真实 Provider 调用。待两条实际登记记录、独立复核与导出完成后，本节按实际结果填写，不以测试或历史 C/S 成功替代 B 的结果。
