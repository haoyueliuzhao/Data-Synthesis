# FinQA 五臂主线：原始 Base 的 dev883 完整终报（2026-09-29）

## 1. 结论与边界

原始 **Qwen2.5-7B-Instruct、无 LoRA/adapter、无本轮训练**的固定 dev883 评价已完成。北京时间 **2026-09-29 04:50:15** 控制器登记 `COMPLETE`；883/883 会话全部封存，随后完成全队列 CPU 原生评分，两个原 GPU 工作进程已经退出。

| 主指标 | 成功数 / 固定分母 | 完整 dev 均值 |
|---|---:|---:|
| FinQA execution accuracy | 33 / 883 | **3.737259%** |
| FinQA program accuracy | 6 / 883 | **0.679502%** |
| 原生评分未知 | 0 / 883 | 0% |

这是**同一冻结公开工具协议下的未训练 Base 基线**，不是普通 SFT、Manual、C-only 或 Full VTDO 的训练结果。当前数据不能确认训练价值、分布干预收益、Contribution 方向性、Novelty 收益或五臂优劣，也没有给轨迹授予 `CompletePass`。

本报告只作全量描述与最小封存核验，不选取单题成功/失败作例，不根据 dev 结果修改生成提示词、资格规则、工具协议、参数或训练策略。后续15个模型必须保持本轮已登记的883题名册、评价配置和评分语义，才能作对应比较。已独立确定的审阅工程修订不能由此处 dev 结果驱动。

## 2. 原件、身份与事前协议

原件根目录：

`/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/finqa_five_arm_mainline_20260929/base_dev883_01`

主要原件是 [protocol.json](/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/finqa_five_arm_mainline_20260929/base_dev883_01/protocol.json)、[全局生成封存](/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/finqa_five_arm_mainline_20260929/base_dev883_01/generation_seal/record.json)、[完整883题评分](/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/finqa_five_arm_mainline_20260929/base_dev883_01/scores/record.json) 和 [最终状态](/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/finqa_five_arm_mainline_20260929/base_dev883_01/status.json)。逐题原响应、工具观察、真实本地 token receipt 和结算记录在两个分片的 `generation/episodes/`，未被报告重写。

| 绑定对象 | 内容身份 |
|---|---|
| 协议 ID | `64ebaffc77904b667c5cfa44a48ab262ab2e2505c152ae93ccfad085ae1e65ad` |
| 执行源码 commit | `39f090c2f3ecd13d3b04aa26bb037c1ebf3eb05e` |
| 原 QA snapshot ID | `451490cf732399ee79c689933b56eb698837ed5370219d6f47c75938ec04368f` |
| 原始 Base binding ID | `student_checkpoint_binding:0d8299b134d14f292a20b24747bb275b4f9fde96495d46a2524ed2964ecab164` |
| 全局生成封存 ID | `c0ff0fdfb1ecdc0264f10bac6375b5f9e00466c400994b23899fadcfa73e5f3f` |
| 完整评分 ID | `a777398d33b3fdd60013d3a46b71a90d7bbb5c5181eff7b6f21c7a86525ec36c` |

协议登记于北京时间01:01:22.930，早于01:01:29开始的真实工作进程。任务为已登记 `development` 角色的官方 FinQA dev 全部883题；完整原题、表格和文本进入公开上下文，作者答案/程序不进入生成请求。角色划分不等于报告或公司来源绝对隔离，本报告不额外作这种声明。

### 固定评价配置

| 项目 | 本轮配置 |
|---|---|
| 模型 | 原始 Qwen2.5-7B-Instruct；adapter=`null`；本轮训练数0 |
| harness | `bigfinance-derived-vtdo-v7` |
| submission profile | `finqa-public-reasoning-v2` |
| 本地工具序列化 | `qwen2.5-native-tool-call-v1` |
| 解码 | greedy，temperature=0，top_p=1，top_k=0 |
| seed 字段 | 20260928；本轮不是多 seed 随机评价 |
| 每轮输出上限 | 2048 token |
| 完整上下文上限 | 24576 token，不截断原上下文 |
| 每会话最多响应 | 32轮 |
| 最终提交 | `submit_program(program)`；不要求另填 numeric answer 或 scale |
| 公开工具 | `list_sources`、`read_source`、`run_program`、`submit_program` |
| 评分 | `v6_task.score_public_reasoning_program`，独立于旧 numeric Final scorer |
| 本轮 API 调用 | 0；配置中的 `api_model=deepseek-flash` 不表示使用了 API |

本轮仍属**工具增强、特定公开协议**的 FinQA 评价，不能把该数值直接当作其他提示词、标准 FinQA 官方模型设置或无工具 QA 的可比成绩。

## 3. 完成率不等于成功提交率或金融正确率

全部883会话均正常结算并完成记录。`final_answer` 在此是成功调用 `submit_program` 后的通用终止标签；程序仅被提交，并不代表它语法正确、可执行或答案正确。

| 会话终止原因 | 数量 | 占883 |
|---|---:|---:|
| `no_tool_call`：未解析到本轮要求的原生工具调用，普通文本不构成程序提交 | 486 | 55.039638% |
| `final_answer`：实际 `submit_program` 成功终止 | 266 | 30.124575% |
| `max_steps`：达到32轮上限仍未成功提交 | 131 | 14.835787% |
| 其余终止原因 | 0 | 0% |
| 完整已结算会话 | **883** | **100%** |

因此，266/883 不能写成“实验完成率”；它只是显式提交率。没有成功提交的617会话仍属于固定883分母，其原记录没有被删除或重新采样。

## 4. 程序可用性与原生失败原因

评分记录的 `native_status_counts` 为 `invalid_prediction=809`、`scored=74`。这里的74表示成功进入可执行程序评分分支；**不意味着另外809题未评分**。按事前规则，正常终态的缺失/非法预测得到确定的0，所以两项指标均是883条确定值、未知0条。

| 全量、互斥分类 | 数量 | 原生处理 |
|---|---:|---|
| 没有成功显式提交：486 `no_tool_call` + 131 `max_steps` | 617 | execution=0，program=0 |
| 已提交，但不满足合法预测程序/结构检查 | 164 | `missing_or_invalid_submission`，两项0 |
| 已通过结构检查，但程序不能执行为有限数值或 yes/no | 28 | `nonexecutable_submission`，两项0 |
| 已提交且程序可执行 | 74 | 进入固定原生 execution/program 比较 |
| 合计 | **883** | 固定完整分母 |

换言之，266次成功提交中有164次不满足程序预测格式要求、28次不可执行、74次可执行。74次可执行提交中，33次 execution 正确、41次 execution 不正确；6次满足原生 program accuracy。主报告始终以883为分母，不用74或266替代完整分母。

原生 reason 的原始全量计数为：

- `missing_or_invalid_submission`：781 = 617 + 164。
- `nonexecutable_submission`：28。
- 正常 `scored`、无 reason 错误：74。

这些分类反映**当前模型在固定提交语言和运行协议下的结果**。不能把所有缺失/格式非法预测简单解释为已证实的金融事实错误；也不能因为某程序可执行就认定它的推理或金融含义正确。

### 工具执行：保留真实错误，不把错误观察当作模型正确答案

| 实际工具 | 成功事件 | 错误事件 | 合计 |
|---|---:|---:|---:|
| `list_sources` | 683 | 0 | 683 |
| `read_source` | 806 | 0 | 806 |
| `run_program` | 118 | 5734 | 5852 |
| `submit_program` | 266 | 0 | 266 |
| 合计 | **1873** | **5734** | **7607** |

`run_program` 的5734个错误事件按已保存工具错误消息可穷尽分为：

| 错误类 | 事件数 |
|---|---:|
| `invalid linear FinQA program syntax` | 4482 |
| `FinQA program did not execute to a finite number or yes/no` | 1117 |
| 参数包含工具 schema 不允许的额外字段 | 135 |
| 合计 | **5734** |

135次额外字段拒绝中，原日志字段计数为 `toolbench_rapid_response` 53、`toolbench_rapid` 30、`toolbench_rapid_answer` 28、`toolbench_rapidfix` 20、`toolbench_rapidfire` 3、`parameters` 1。这是全量协议错误描述，不是据 dev 设计新的容错、字段修复或提示词建议。

上述是事件数，不是互斥的题目数：一个会话可以包含多个工具错误及后续恢复。没有把错误动作拆成另一个成功候选，也没有按成功结果挑选分母。

## 5. 真实调用、token 与输出终止

| 项目 | 全量计数 |
|---|---:|
| 已完成会话 | 883 |
| 真实本地模型生成调用 | **8093** |
| `returned` 结算记录 | **8093** |
| 实际本地 token receipt | **8093** |
| 输入 prompt token 累计 | **47,115,065** |
| 实际生成 token 累计 | **594,656** |
| 回应以真实 EOS 结束 | 8085 |
| 回应达到输出长度上限（`finish_reason=length`） | 8 |
| API 调用 | **0** |

Token 数来自每次实际本地生成的 `usage`，不是重新分词推估，也不是 DeepSeek API token。输入累计包含每轮重发的完整历史，因此不是883份初始问题的去重文本 token 数。输出包含实际生成序列；8085条真实EOS与8条长度终止分别保留，不声称所有回复均自然结束。

8次长度终止是既定2048输出上限触发的实际结果，不是主机截断初始资料或删除历史；没有为其添加未登记续写/重试。本轮没有未结算调用被转换为财务错误0。

## 6. 两个固定分片、时间与 GPU 释放

以下全部时间为北京时间2026-09-29；“工作窗口”由 `launched` 到 `outcome`，含加载、生成、工具执行及记录写盘，并非纯CUDA计算时间。

| 项目 | dev00 | dev01 |
|---|---:|---:|
| 原固定题数 / 完成题数 | 442 / 442 | 441 / 441 |
| GPU | 7 | 0 |
| 首次启动 | 01:01:29.183 | 01:01:29.188 |
| 生成完成 outcome | 04:49:04.020 | 04:48:42.672 |
| 工作窗口 | 13654.837秒（3时47分34.837秒） | 13633.484秒（3时47分13.484秒） |
| worker attempt | 1 | 1 |
| 本地生成调用 | 4081 | 4012 |
| prompt token | 23,947,496 | 23,167,569 |
| completion token | 311,223 | 283,433 |
| 工具错误 | 2877 | 2857 |
| execution 正确 | 20 | 13 |
| program 正确 | 3 | 3 |
| 单会话耗时中位数 | 13.454秒 | 13.651秒 |
| 单会话耗时P95 | 109.732秒 | 102.116秒 |

两分片是事前固定分工，成绩差异只是描述，不能用作选卡、选题或推断GPU影响正确率的因果证据。二者运行于允许共享的 GPU，工作窗口亦不能当作独占满载GPU小时。

全量单会话耗时中位数13.517秒、P95为105.106秒、最大294.693秒；P95采用排序后第 `ceil(0.95*N)` 项。883会话 `elapsed_seconds` 合计27149.631秒，这是并行分片各会话时间之和，不能替代总墙钟时间。

全局状态登记完成于04:50:15.651。从最早启动到终态共 **13726.468秒，约3时48分46.468秒**。最后分片生成完成到终态登记约71.631秒，包含控制器等待、全局核验、CPU评分和写盘，不将其全部冒称纯评分耗时。

原进程为 GPU7 的 PID `4066895`（process identity `303928435`）和 GPU0 的 PID `4066896`（`303928436`）。原 `outcome` 均为 `COMPLETE`，最终状态为 `workers_exited=true`；本报告核对时这两个 `/proc/<pid>` 均不存在。故**本轮两个模型进程已退出，未继续占用GPU**。这不表示两张卡目前没有其他项目，也没有为核对而中止其他进程或重新加载模型。

## 7. 最小审计核验与封存屏障

本次报告对已完成原件做了以下离线核验，全部通过：

1. 协议、全局生成封存、评分三个顶层内容ID与内容digest一致；协议ID及封存ID引用链一致。
2. 两分片封存文件 SHA、run/seal身份及442+441计数与全局封存一致；评分题目名册及顺序与协议的883题完全一致，无重复题或成功子集替代。
3. 为汇总token/工具事件只读遍历883个保存会话，核对配置、结算声明、真实调用计数；按注册顺序计算其内容digest，与全局封存的883个 episode hash逐项一致。没有重新生成、解码全部token或执行概率回放，也没有重复作全量原始文件hash/token校验。
4. 8093模型调用、7607工具事件、5734工具错误与已保存评分行汇总一致；33/6原生正确计数一致。
5. 评分实现先要求全部分片封存并构建全局883封存，再读取私有参考和执行原生评分。保存的全局封存为 `private_references_read=false`、`all_generation_complete=true`、`all_provider_calls_settled=true`；评分绑定该封存，不是边生成边评分。本报告未重新打开 `private.references.jsonl` 或重新评分。

原件文件 SHA-256（与上文内容ID不是同一概念）：

| 文件 | SHA-256 |
|---|---|
| `protocol.json` | `682cdfd4ecaf2d4a019e30e14b6ccb94b1130e8cac5c5d88966a7351cb48db74` |
| `generation_seal/record.json` | `9f1462f61b8757ea40ba6662be8a960e0dda7b80ae72928d7b150662f1a68112` |
| `scores/record.json` | `a9c790bfcf76a9ab8eca964ff3f2805c5300d1640c2a9822047ac6b96381e699` |
| `status.json` | `3e063c0ada8796fe300a4ae0aaca3b03ee73256faeeaa7db518b1c077864dee8` |
| `dev00/generation/generation_seal/seal.json` | `c67ce3919fc164807c56ac299503afd465bf0e7ef8eb928d85435602cb488505` |
| `dev01/generation/generation_seal/seal.json` | `435d9fd3e604afc58d86ff6d7ab61d0e8ac6478123d46eb0656ce156ada1ca35` |

## 8. 后续15模型比较必须保持的口径

本轮协议已明确 `future_fifteen_models_require_same_evaluation_configuration=true` 和 `base_results_not_for_prompt_collection_or_qualification_tuning=true`。需要保持的具体绑定包括：

| 绑定 | 内容digest |
|---|---|
| 评价 config | `8e6fa1b70fe1f93c09cb30cfa3916f2b4a49ac2476d73e80def6aaaceed5362f` |
| public system message | `f256e6882152b09c1659bcacb3a7f3fef3544780e6a96542709a110d80ea807a` |
| public tool specs | `826c1d991cced5765aadbe335fbdcd941ee4765917f6a7ad7c399ce507bf29cd` |
| tokenizer | `f9be72de469e1dcb00337706a315ef1d4f2d80d33922a73eac5e75741c30fa79` |
| chat template | `2e2d2512cfe46af53dc1eed45368ecaab26ac4461c480e6b69fe571cf0ceaa75` |
| 原生 FinQA executor source | `b64686fab3de2053da53c40f01a14fac7783cae101d64af722c1b59d54269df2` |

还须保持原题/公开视图hash名册、生成长度和上下文限制、缺失/非法正常预测记0与基础设施/参考异常记未知的政策、全封存后评分、最终checkpoint及数据角色。未来若评价协议另改，必须单列新实验，不能把新配置成绩混入当前Base的配对比较。

本轮 `unknown=0` 是实际记录，不是政策把未知当0：若后续出现未结算调用、依赖缺失或参考异常，其指标必须保持 `None`/未知，不可因为需要883分母就改为金融错误0。原生正确也不等于公开推理轨迹资格成立。

## 9. 本轮已经完成和仍未完成的工作

已完成：883题真实原始Base生成、全队列封存、CPU原生评分、固定分母汇总和GPU工作进程退出。

尚不能据本轮声称：共同训练材料核已准入；15模型已经训练；Static−Base、Manual±−Static、Full−Static 或 Full−C-only 已有结果；C/N机制成立；完整VTDO闭环收敛；轨迹过程质量已通过双审。

Base不依赖训练材料而独立完成，属于主线准备和最终比较所需基线。五臂训练及机制实验仍按各自原登记的材料、编码、资源和执行条件推进。本报告未改任何运行源码或既有原件，未发起任何API/GPU调用，也没有用本轮dev逐题结果开展针对性适配。
