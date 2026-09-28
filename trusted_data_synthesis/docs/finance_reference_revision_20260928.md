# R2／G2／H2：可见引用修订与 Direct-DSL 开发复测

## 授权和不变项

用户根据 `25afac43-31f2-4c5b-9812-65cbec6f95ee` 审计明确要求“参照审计修订并开展后续实验”。本次据此执行审计中的 R2/G2/H2 有界方案，不把审计中后续训练的建议当作训练授权。

原 FinQA 8281 题快照、1000／350／120 角色规划、同一120题 calibration、Base 与旧 Static seed11-step240、原生 evaluator 和正常缺预测计零政策保持。原480会话、4次G、全部分数、失败及登记纠错均保留，不重跑旧H0，不补写旧episode。本轮仍不采新SFT材料、不执行优化步、不修改C/N或固定核；全部金融轨迹的完整语义资格仍需独立判断。

本轮沿用已经用于诊断的120题，明确是**开发复测，不是未见确认**；不打开FinQA test或TAT-QA来选择新提示。新API模型约束仍为deepseek-flash；本方案只使用本地Qwen，计划API调用0。

## R2：一次局部接口修订

新 harness 为 `bigfinance-derived-vtdo-v3`（实验条件 H1-R），新公开 profile 为 `finqa_program_v2`。旧 v1 profile 和旧运行不改写。

模型看到的工具 content 明确包含 `result_handle`、`status` 和 `output`，短句柄为当前会话的 r1、r2……。原 `raw_output` 独立保存，ToolEvent 保存句柄／实际调用事件映射。失败结果也具有可观察的错误封套，但不进入成功结果引用表。

三种身份分离：

- `invocation_id` 绑定登记 run／episode／turn／attempt（工具再加 tool_index），表示真实执行，不从生成内容推断。
- 技术 call_id、请求／输出摘要和参数点摘要继续保留；相同内容摘要不会令两次真实执行被合并。
- `result_handle` 是模型使用的短公开引用，仅在当前session解释，不跨会话查找，也不猜测近似ID。

新的 `prev:rN.output.<path>` 只指向此前成功输出。未知、失败、未来及不存在路径明确报错。引用值、计算表达式和最终程序分开：calculate.variables 接收完整引用字符串，calculate.expression 只接收有限标量算式，Final.program 原样提交线性FinQA DSL，不把句柄或嵌套Python调用变成程序。

通用说明仅固定修订一次：合成Revenue120/90引用链、`subtract(120, 90), divide(#0, 90)` 两步例子及无额外引号的精确行名。例子与待评题gold无关，两条件共用；说明中的合成结果不作为待评题已经完成的工具历史。原始表文仍在初始上下文，不强制所有真实金融题先list_sources或read_source。

CPU准入使用实际本机冻结Qwen模板及tokenizer。脚本正控从模型可见工具content解析句柄，再走read_source→calculate变量引用→final_answer；不从内部状态表偷取正确ID。相应反例及Direct严格解析、结算、存储、调用预算控制一起保存JUnit证据。测试失败或跳过不能作为通过；测试代码和运行源码在真实生成登记前提交并绑定。

此前长度登记器已在a1d771cabb修复为实际input_ids计数；本G2使用固定合成样例，不再按待评题长度择例，也不重采旧G。

## G2：四个有限多步实例

真实点为同一旧Static11-step240；诊断虚拟点沿用明确的零矩AdamW、lr=1e-5、固定LoRA梯度1e-4、betas=(0.9,0.999)、eps=1e-8、weight_decay=0。不是新FinQA总体G，不继续旧Adam状态，不执行真实optimizer.step。

两点各运行两个预先固定的合成公开实例：

| 样例 | 规定的诊断链 | 每例上限 |
|---|---|---:|
| normal | read_source→用可见句柄计算→用计算结果句柄Final | 4次响应 |
| error_recovery | 错误来源请求→纠正读取→引用计算→Final | 4次响应 |

共4例，最多16次新生成；T=1、top_p=1、top_k=0，每响应最多256 token、上下文24576。此处256是短合成诊断的事前边界，不改变H2的2048。模型每次实际输出，包括错误动作和实际EOS，都保留原始TokenReceipt并在其原参数点严格回放；不将SFT正向mask用于反馈token，不放宽atol=1e-6／rtol=1e-5。

分别记录：脚本可执行正控、真实模型是否实际使用了可见prev引用、普通执行是否已结算且可运行、同点可微回放是否通过。模型没有走prev就不能报告该真实链通过；没有达到Final保留模型失败，不补“请继续”、不换例、不无限重采。原调用intent未结算则停止，不能重采覆盖。

H2启动的事前规则：CPU实际模板正控通过，G2没有未知／基础设施故障且普通执行通过。真实合成链成功率和反馈数值通过率独立报告；模型未学会链路不自动等同基础设施坏掉，也不能把普通评价准入解释为训练资格。任何情况下都不自动启动训练。

## H2：固定开发复测矩阵

| 条件 | 公共输入／交互 | 每题生成上限 |
|---|---|---:|
| H1-R | 原完整表文＋v2说明＋可见结果句柄工具＋显式Final | 32 |
| Direct-DSL | 同一原完整表文＋v2说明；无工具、无已执行历史；一次JSON提交answer/program/可选scale | 1 |

两模型×两条件×同一120题＝480新会话。两侧共同greedy；每响应2048 token，上下文24576，原生评分和缺预测政策相同。Direct只接受一个完整JSON对象，不剥代码围栏、不提取子串、不修复程序、不根据答案反造程序；非法输出在唯一响应后终止，正常失败计零，服务未知保留unknown。

H2生成上限是240×32＋240＝**7920**，加G2最多16，共**7936**；不再新增H0条件、64轮预算或其他模型。16个30题分片按同一offset交错四条件，最多4 GPU worker，只使用当前空闲卡，不终止其他项目。每个worker仅一次尝试，已完成会话不可重复生成；失败／未知停止新分片，保留已有结果。

全部480会话生成封存且worker退出后才读取参考评分。分别报告execution/program、程序可执行性、Final、失败原因、真实调用和token成本；CompletePass继续独立unknown，不能由原生正确推断。两条件不是等算力比较；H1-R同时改变可见输出与通用说明，与旧H1的差异不是“补ID”的单一因果效应。

## 执行文件与阶段状态

控制器：`python -m trusted_synthesis.finance_research.calibration_v2`。准备证据位于 `artifacts/finance_research_20260928/r2_preparation_20260928`；新运行固定为 `artifacts/finance_research_20260928/reference_revision_01`，不得覆盖 `audit_followup_01`。

新protocol固定审计附件摘要、源码、CPU证据、原快照及角色规划、120题、模型点、合成例子、全部480条件和7936调用边界。实际启动、CPU结果、G2结果和H2进度将在执行后追加；以上为执行前方案，不预写成功。

### CPU集成完成

实际运行 `test_finance_research_*.py`：**304 passed，12.15秒，无失败或跳过**；Ruff（排除未修改的官方metric_vendor）和diff检查通过。包括实际冻结模板可见引用正控、Direct严格提交、v1合同不变、v2原生分母政策、G2回放入口/上限、H2固定预算、全部worker退出后评分以及原有材料/编码/反馈接口回归。这些是CPU／接口验证，不是模型金融效果。

JUnit记录保留在 `r2_preparation_20260928/cpu_controls.xml`，登记器绑定其字节摘要及实际执行的测试源码摘要；没有重新生成旧实验，也没有读取参考答案用于选择公共例子。
