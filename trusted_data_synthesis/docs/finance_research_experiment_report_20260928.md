# 金融研究重构后 R/G/H 有界实验报告（2026-09-28）

## 一、结论与收口范围

**本轮 480 会话已经完整生成、封存并评分，四张 GPU 已释放；执行完成，但没有确认金融任务效果改善或训练价值，且发现 H1 前序工具引用的可见性缺陷。**

可以确认：审计指定的三个接口修订已经落地；4 次真实 Qwen 接线／回放诊断完成；H0/H1 × Base/旧 Static × 同一 120 题的固定 greedy 矩阵完整执行，没有以成功子集替代分母。不能确认：H1 已具备完整任务可用性、新 Static/Delayed-C 的训练收益、CompletePass 或真实金融泛化收益。

本轮四个条件官方 execution accuracy 分别为 1.67%、1.67%、0%、0.83%；program accuracy 全部为 0%。H1 的 240 会话中 188 个耗尽 32 次响应。分析发现冻结模板未将实际工具 call_id 呈现给模型，而 `prev:<call_id>...` 要求该 ID；因此 H1 的大量引用错误不能全部归因于模型能力。这是本轮结果的重要解释限制，需要下一轮独立修订，不能在本轮分数上追溯修复。

上述为描述性审计结论，不是事后新增预登记 PASS 阈值。本报告未开展新生成、补采、训练或原生重新评分。

## 二、范围、协议与模型身份

本轮承接 [审计修订与执行登记说明](finance_research_audit_followup_20260928.md)，不是旧跨市场校准实验的重算。

| 项目 | 实际执行设置 |
|---|---|
| 数据 | 原始 FinQA 快照 8281 题中的既定 calibration 120 题；四条件共用 |
| 用途隔离 | 原 1000 SFT／350 feedback／120 calibration 规划不变；不重新抽题 |
| 模型 Base | Qwen2.5-7B-Instruct，零 B LoRA 表示的基座函数，固定 seed11 坐标初始化 |
| 模型 Static | 旧 Static seed11、step240，事前按最小既定种子选定，不按本轮成绩择优 |
| H0 | 原 `_run` 循环的原 QA 兼容版，裸 JSON、顶层 first-Final、user-role 工具观察 |
| H1 | `bigfinance-derived-vtdo-v2`，原生 Qwen tool-call、工具角色历史、final_answer 终止 |
| 公开提交规则 | 四条件均为 `finqa_program_v1`，Final 必须包含可执行的 FinQA DSL program |
| 解码 | greedy，temperature=0；每题最多 32 响应、每响应 2048 token、上下文 24576 |
| 规模 | 4 条件 ×120＝480 会话；16 个 30 题分片，最多 4 GPU worker |
| 上限 | H 最多 15360 次生成；G 另外最多 4 次，无隐藏重采 |
| API／训练 | 本轮 API 调用 0，真实 optimizer.step 0；未来 API 仍固定 deepseek-flash |

H0 与 H1 共享原公开表格、文本、计算后端和 program 提交合同，但提示／交互结构不同。H0 是旧循环兼容接入，不是旧 900 题设置原样复现。Static 来自旧任务／协议训练，不是新 FinQA 主训练结果。当前 120 题用于工程校准，不能冒充最终 test 或独立外部评测。

TAT-QA、FinanceMath、MultiHiertt 均未在本轮执行；保留此前 TAT-QA 标签版本差异及官方 split 来源交叠说明，不新增“数据完全独立”主张。

执行源码：`954ad6dab6`；运行工作树保持冻结。`a1d771cabb` 的输入长度登记修复在独立工作树完成，仅供未来运行，不冒充本轮执行源码。

- 协议 ID：`1f8840f9ba4cb10301fb06362d25a37357ad4e1a4d9917da02dd3736cd24921a`。
- FinQA snapshot ID：`451490cf732399ee79c689933b56eb698837ed5370219d6f47c75938ec04368f`。
- Base 参数摘要：`7659b963dc0740351280b648764bd12f339d74bb7515b9429b4e8213776b434b`。
- Static 参数摘要：`1846eb7b9089c1590d1bcd73493c7e7b2f996ec10dd0942ab3d97b6fb9791cb7`。
- 静态 adapter 文件 SHA-256：`c91bb52396d22585dddc88f7d8a689ece18f0dc21bdf978107cbef8cff68a143`。
- FinQA 官方 evaluator 固定版本：`0f16e2867befa6840783e58be38c9efb9229d742`，沿用 vendored 原算法。

## 三、完成时间、资源与调用结算

以下时间均为北京时间 2026-09-28；JSON 原记录使用 UTC。

| 事件 | 时间／数量 |
|---|---|
| G 作业开始 | 09:02:58 |
| H 第一批 worker 开始 | 09:04:26 |
| 最后 H 作业写完成结果 | 10:58:59 |
| 全部 worker 已退出的全局封存 | 10:59:03 |
| 原生评分全部完成 | 10:59:42 |
| H 开始至全局封存 | 1 小时 54 分 38 秒 |
| 封存后 CPU 评分 | 38.17 秒 |
| H 真实模型调用 | 7708／15360 |
| G 真实模型调用 | 4／4 |
| 新 API／真实优化步 | 0／0 |

17 个作业（G＋16 H）均只有 attempt01，均 COMPLETE。480 会话全部已结算，7708 次 H 调用均有实际 TokenReceipt；没有未知调用、Provider 失败、回执缺失或额外重试。日志检查未发现 traceback/OOM/FATAL。合法模型失败仍进入固定分母，不与基础设施未知混淆。

GPU3、GPU1、GPU2、GPU0 上最后一个本项目 worker 的完成记录依次为 10:33:02、10:33:48、10:46:04、10:58:59。完成记录时刻不是精确 CUDA 显存释放时间；10:59:03 的全局封存确认全部退出，11:35 的 NVML 核对也未见本项目进程。其他项目 GPU6/PID643277 未受影响，不能据此声称整台机器 GPU 全空。

H 的 worker 墙钟之和为 23602.07 秒（约 6.56 GPU 进程小时），包含各进程加载与工作时间，不等同于 GPU 内核忙时、能耗或费用；不含早先纯占位等待和 G。曾预留的四个 holder 也均已退出。此前预计 10:45–11:15 完成，实际 10:59 落在该窗口内。

回执身份补充：7708 条 H 回执的 call_id 字符串有 7481 个唯一值，其中 227 组在不同参数点复现相同内容寻址 ID；`(parameter_digest, call_id)` 有 7708 个唯一值、无重复。不能只按 call_id 去重，否则会漏计不同模型的真实调用。

## 四、G 真实模型接线与可微回放

| 参数点／输入 | 实际 prompt token | 实际输出（含 EOS） | 最大 logP 绝对误差 | 梯度 L2 |
|---|---:|---:|---:|---:|
| real／short | 2309 | 16 | 0 | 180.4611 |
| real／long | 6299 | 16 | 0 | 16.4036 |
| virtual／short | 2309 | 16 | 0 | 146.3292 |
| virtual／long | 6299 | 16 | 0 | 26.6206 |

四例均完成合法 `list_sources({})`，规范化后历史只渲染一次工具封套；下一轮历史已构造，但未进行第二次模型生成。严格沿用 atol=1e-6／rtol=1e-5，112 个梯度坐标有限，完整前缀 KV 导数保留；回放使用原 token、零重采，最终真实参数、模式和 RNG 恢复。G 耗时 85.21 秒，峰值 allocated 30.532 GiB／reserved 31.680 GiB。

虚拟点是零矩 AdamW＋固定小梯度的数值诊断，不是本轮 FinQA 总体 G，不延续旧 Adam 矩，也不是实际训练更新。四个实际输出均仅 16 token，不能外推为 24576 上下文／2048 输出压力测试或多轮金融工具链通过。

**长度登记纠错保留：** 原登记器把 `len(BatchEncoding)` 的两个字段误当 token 数，留下 `[2,2]`，选题实际退化为 task_key 字典序首尾。事后只读 CPU 重算 120 个公开输入，确认选中的 AAPL/2008/page_38.pdf-2 与 NCLH/2018/page_69.pdf-1 恰好是真最短 2309 和真最长 6299，全部 120 题满足 prompt+2048≤24576。因此实际极值覆盖成立，但选择器算法与原登记字段仍有错误，不能改写历史。纠错单独保存，无新增生成；未来登记器已修复。

## 五、官方主指标与提交结果

正常、已结算的无合法 Final／非法 program 按事前规则计官方两项零分。基础设施未知、缺评分依赖和参考矛盾不按零分处理；本轮这些情况均未出现。每条件主指标都具有完整的 **120/120 分母**。

| 条件 | Execution accuracy | Program accuracy | 显式 Final | 可执行预测程序 | 精确 Final 诊断 |
|---|---:|---:|---:|---:|---:|
| Base/H0 | 2/120（1.67%） | 0/120（0%） | 117/120（97.50%） | 3 | 13/120（10.83%） |
| Base/H1 | 2/120（1.67%） | 0/120（0%） | 28/120（23.33%） | 5 | 7/120（5.83%） |
| Static/H0 | 0/120（0%） | 0/120（0%） | 91/120（75.83%） | 0 | 12/120（10.00%） |
| Static/H1 | 1/120（0.83%） | 0/120（0%） | 8/120（6.67%） | 1 | 0/120（0%） |

“可执行预测程序”对应 native status=scored，不是“可以计入分母的题数”；非法预测在本轮规则下也有合法的零分。精确 Final 是项目派生诊断，不是官方主指标，不进行额外宽松数值、单位或百分号归一化，不能拿它替代 execution accuracy。

| Native 结果原因 | Base/H0 | Base/H1 | Static/H0 | Static/H1 |
|---|---:|---:|---:|---:|
| 程序容器／结构非法 | 103 | 16 | 86 | 7 |
| 程序无法执行 | 11 | 7 | 5 | 0 |
| 正常终态无合法 Final | 3 | 92 | 29 | 112 |
| 程序可执行、交官方指标 | 3 | 5 | 0 | 1 |
| 合计 | 120 | 120 | 120 | 120 |

实际显式 Final 的 program 都是非空字符串；主要问题不是在 Final 中完全漏 program，而是没有到达 Final、程序结构或程序可执行性不符合要求。

同题配对 execution（右条件减左条件，纯描述性，不做显著性或因果主张）：

| 左／右 | 共同正确 | 仅左正确 | 仅右正确 | 共同错误 | 差值（百分点） |
|---|---:|---:|---:|---:|---:|
| Base H0／Base H1 | 1 | 1 | 1 | 117 | 0.00 |
| Static H0／Static H1 | 0 | 0 | 1 | 119 | +0.83 |
| Base H0／Static H0 | 0 | 2 | 0 | 118 | −1.67 |
| Base H1／Static H1 | 0 | 2 | 1 | 117 | −0.83 |

极少正确例、单一旧 Static 保存点及已确认的 H1 接口限制，均不足以支持“新版提高准确率”或“训练使能力下降”的因果结论。本轮没有 Delayed-C 条件，也没有新训练。

## 六、轨迹终止、成本及瓶颈

| 条件 | Final | 达32次响应 | 无工具调用终止 | 模型调用 | 输入 token 总和 | 输出 token 总和 | 每题耗时中位数／P95（秒） |
|---|---:|---:|---:|---:|---:|---:|---:|
| Base/H0 | 117 | 3 | 0 | 230 | 903135 | 19628 | 2.32／11.81 |
| Base/H1 | 28 | 89 | 3 | 3031 | 17071297 | 163059 | 79.22／113.96 |
| Static/H0 | 91 | 29 | 0 | 1200 | 5773514 | 106907 | 12.02／176.80 |
| Static/H1 | 8 | 99 | 13 | 3247 | 18504711 | 173581 | 77.39／123.79 |

Token 按每次真实回执计数，输入包含逐次重复送入的历史，不是去重后的数据集长度，也不是 API 账单。P95 使用 nearest-rank（ceil(0.95×120)）。H 总输入 42252657 token、输出 463175 token。

H1 共 188/240（78.33%）会话到达 32 次响应上限，平均每题约 25–27 次模型调用。全 H 仅 7/7708 个响应达到 2048 输出 token，因此主要不是普遍输出截断，而是多轮工具失败与终止失败积累。Base/H1 的模型调用数是 Base/H0 的约 13.18 倍，但 execution 正确数相同；这只是本设置的成本比较，不是普适 harness 效率结论。

| 条件 | 工具事件 | 工具错误 | 主要错误信息及次数 |
|---|---:|---:|---|
| Base/H0 | 4 | 3 | 三种错误各1次 |
| Base/H1 | 3028 | 2732 | 非法算术表达式2340；前序引用失败323；不支持语法／变量65；数值类型4 |
| Static/H0 | 271 | 230 | 非法表达式109；不支持语法／变量91；变量名非法30 |
| Static/H1 | 3234 | 2774 | 前序引用失败2330；非法表达式350；不支持语法／变量91；来源ID2；变量名1 |

H0 的顶层 Final 不计 ToolEvent，H1 的 final_answer 计 ToolEvent；H0 格式错误反馈也不等于工具调用。因此工具事件数量不能直接当成同口径能力指标，应优先参考真实模型调用、终态与原生分数。

## 七、已确认的接口缺陷与代表性失败

### 7.1 H1 的实际 call_id 对模型不可见

冻结 Qwen 模板原始 UTF-8 字节 SHA-256 为 `cd8e9439f0570856fd70470bf8889ebd8b5d1107207f67a5efb46e342330527f`；`provider.chat_template_digest` 为 `2e2d2512cfe46af53dc1eed45368ecaab26ac4461c480e6b69fe571cf0ceaa75`（对模板字符串作 canonical JSON 编码后取摘要，口径不同）。模板不渲染 assistant call ID 或 tool_call_id，只渲染工具名称、arguments、tool content；当前工具内容也没有补充实际 ID。

除 CPU 模板检查外，还直接解码 ETFC/2013/page_84.pdf-1 的 Base/H1 第3次响应之前的实际 TokenReceipt prompt：3853个原始token，解码后重新编码与原ID逐项相同。前两次成功工具的实际 `local:<hash>:0` ID 均不在该真实 prompt 文本或工具 visible_output 中。此项用原采样输入核验，不依赖序列化消息字典的再次渲染顺序；见 [逐字段可见性证据](../artifacts/finance_research_20260928/public/audit_followup_report_01/tool_reference_visibility.json)。

与此同时，解析器要求 `prev:<实际call_id>.<path>` 指向此前成功调用。模型无法从该公开历史取得所需的不透明 ID，因此这一路引用存在真实接口可观察性缺口；直接使用公开表中的数字仍可计算，不意味着全部工具路径不可用。该缺口与错误计数吻合，但本轮没有修复后的对照，**不能量化它解释了多少失败，更不能把所有表达式错误都归到同一原因。**

可复核实例：`jobs/base_H1_000/generation/episodes/9dfb15ee7500b760e10c590df3e57e0ef8a826319ae2a1f5b067e37979fc1e69/episode.json`（相对于本轮运行根目录）。G 只调用 list_sources 并构造下一轮消息，未使用 prev；所以 G 的通过没有覆盖这一缺陷。

### 7.2 重复错误耗尽上限

ETFC/2013/page_84.pdf-1：Base/H1 在两个成功工具动作后，连续30次把 `prev:0...` 形式直接写进算术表达式，报非法表达式；Static/H1 同题连续30次尝试 `prev:read_source.table_sum(...)` 形式，报引用路径错误，最终均耗尽32次响应。计数与预算按原规则保留，没有事后 early-stop、修正参数或继续生成。

### 7.3 数值答案正确不保证 program 合法

AAPL/2008/page_50.pdf-2 的 Base/H0 Final 为653，按固定 exact Final 诊断正确，但预测 `table_max('interest income', none)` 在行名中保留了额外引号，无法匹配原公开表的 `interest income` 行。该例官方 execution/program 均为0，说明程序提交失配与金融数值错误不能直接等同。

### 7.4 一致性诊断的尺度边界

Static/H1 唯一 execution 正确例 GS/2012/page_129.pdf-4 的 Final 为 `48.91555%`，program `divide(1060, 2167)` 执行结果为 `0.48916`。当前原始精确一致性诊断不归一化百分号或 scale，因而标记不一致；不能仅凭此把它说成已证实的财务矛盾，也不能为了改善结果追改本轮诊断规则。

## 八、语义资格、训练边界与下一步建议

Final/预测 program 精确一致性分别为：Base/H0 一致0、不一致3、不可比117；Base/H1 3／2／115；Static/H0 0／0／120；Static/H1 0／1／119。该检查只比较最终值，不验证实际工具轨迹的金融语义支持。

**全部 480 条轨迹的 semantic support／CompletePass 仍是 unknown。** 不得由原生分数、正常结算、工具成功、G 数值通过或正确 Final 自动升级为训练合格材料。API Probe、Student 离线编码、实际 FeedbackTokenReceipt 的区分仍保持；positive-only SFT mask 和 TaskBatch 权重政策已准备，但本轮没有证明真实新材料→训练→反馈的完整价值链路。

以下为后续建议，尚未执行，也不构成本次新预算登记：

1. 优先修复 H1 工具引用的可见身份和路径合同，并用真实模板检查 read_source→calculate→final_answer 的完整可见往返；不能只验 list_sources。
2. 用少量固定公开样例验证模型能提交合法线性 FinQA DSL、表格行名与中间值引用；仅提供通用语法示例，不泄露待评题答案，不加入 oracle 修复。
3. 将接口修订、调试样例及后续独立确认名册分别登记。本轮 calibration 的失败已用于诊断，后续在相同120题上的结果只能明确标注为开发复测，不能冒充未见确认。
4. 完成接口准入后，再登记材料采集上限与训练比较；不要仅凭本轮4次数值诊断或0–1.67% execution 就启动大规模 Static/Delayed-C。

本次用户请求为查看进度并生成报告，因此未热改运行 harness、未重采、未重新评分、未启动后续实验。

## 九、可审计交付与复现

运行根目录：`/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/audit_followup_01`，原始记录约3.0GB，保留在服务器；未把大型逐轮日志全部推入 Git。

本次发布：

- [机器可读汇总与证据清单](../artifacts/finance_research_20260928/public/audit_followup_report_01/summary.json)：四条件结果、配对计数、16分片时间、G原结果、登记纠错、源记录摘要、480个封存会话的路径与hash。
- [480会话逐题指标表](../artifacts/finance_research_20260928/public/audit_followup_report_01/per_task.tsv)：不重评分，保留原生状态、失败原因、成本、终态、会话摘要；不含全量原始文本。
- [只读汇总脚本](../scripts/report_finance_research_audit_20260928.py)：只读取已封存会话与既有评分，不打开 private.references、不调用模型；输出不同字节时拒绝覆盖。
- [报告辅助测试](../tests/test_finance_research_report.py)：同题配对方向、P95口径、输出不可覆盖三项通过；脚本 Ruff 检查通过。另由独立只读审查交叉核对关键指标、执行状态与模板可见性。

汇总 ID：`4d1f1b2554fe71e45f1a29d24a17f86e59195c7a4c9b04a25db8428cea64c09b`。

原协议文件 SHA-256：`59f530eb10503612920fd88166e9cb1d1d303c4c423d8d1c0f28513953024408`。G原结果文件 SHA-256：`611cb483441a63316c79651496f8dc743f170912c8c9c200e25ecf7022895da6`。480会话清单 digest：`ff797819322f8448cd9526ed1dc7f850f81c59d3ec4df6d3e889cb146caf12e0`。原 protocol、G/H结果、旧失败、长度纠错均未覆盖。

在本仓库根目录使用项目 Python，可复现描述性汇总至一个新的输出目录：

```bash
/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/.venv/bin/python \
  trusted_data_synthesis/scripts/report_finance_research_audit_20260928.py \
  --run /data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/audit_followup_01 \
  --output /tmp/finance-research-audit-report-reproduction-20260928
```

报告生成时检查了每条件相同120题、各30题分片、run／seal／score关联、全部480会话的封存hash、调用结算及实际token长度；没有重新运行原生评价或改变任何预测。配对统计为完成后的描述性汇总，未事后加入显著性检验、择优选择或金融总分。
