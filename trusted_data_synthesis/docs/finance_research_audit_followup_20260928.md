# 金融研究重构审计修订与有界后续实验

## 本次授权与不变项

用户要求“参照审计修订并开展后续实验”，并明确允许先预留几张空闲 GPU。本次保留原 FinQA 8281 题快照、1000／350／120 用途规划、TAT-QA 1663 题版本、历史评价和全部失败记录，不重新出题、不重导全库、不改历史原生 scorer 算法。

按审计顺序先修复 R 接口，再运行 G 真模型准入和 H 固定矩阵；新的材料采集及 Static／Delayed-C 大训练尚不启动。所有后续 API 模型仍固定 `deepseek-flash`；G/H 使用本地 Qwen，不调用 API。

## R：三个修复

1. 本地 H1 固定 Qwen2.5 原生 `<tool_call>JSON</tool_call>` 协议，合法封套不是 JSON repair。保留原采样串、参数字节和 TokenReceipt；规范消息中的 arguments 为对象，避免模板双重编码。历史不重复塞入整段原封套和结构化 tool_calls；裸 JSON 只在明确的 H0 legacy profile 下使用。重复键、非有限值、残缺封套不修复。
2. `finqa_program_v1` 在所有条件公开同一通用 DSL／允许算子／必交 program 规则。正常已结算的无 Final、漏程序、非法程序按预登记外围规则计官方两项零分；工具可接受漏交的 Final 为终态，不额外强制重采来掩盖漏交。服务错误、未知调用、评分依赖缺失及参考矛盾保持 unknown／unsupported／null。Final 与程序执行值一致性另报，不充当 CompletePass。
3. 新 `CallSettlement` 分为 returned、pre_call_rejected、service_failure、unknown，实际计数由调用前后证据导出。缺回执的超时会保存 incomplete、停止下一题且不写全批 seal；明确服务错误即便已结算也属于基础设施失败，不记金融零分。合法调用前上下文拒绝可保留正常失败分母。封存与评分入口重复验证这些事实，不能仅改一项布尔值放行。

公开提交规则通过独立运行 view 绑定原 QA hash，不覆盖原题。新 H1 ID 为 `bigfinance-derived-vtdo-v2`，旧验收和 preflight 原始文件保留。

## 训练接口的明确政策

API Probe 的真实公开请求、原响应和实际工具执行，与 Student 离线编码、虚拟 Student 原采样 TokenReceipt 分开。API 没有原采样 logP 不妨碍 SFT；但离线 Student token 永远不能伪称 API 采样 token，更不能进入 gJ 回放。

首项新训练准备恢复“成功公开响应＋首个 Final”监督。失败响应和反馈仍在后续上下文，target mask 为零；本地 EOS 仅监督实际成功响应的 EOS，API 编码添加的 Student EOS 明确属于离线编码策略。全响应监督不混入本次迁移。

全池接口保留供总体 G 和 CPU 控制；TaskBatch 使用 `μ(x)/(B·p_s(x)) · π(z|x)/(n_state·L_package)`。均匀 1000 题、每批 5 题即 `π/(5·n_state·L)`，不再除第二次 B，也不能误用全池 1/1000。拟议 2000 steps、700 条反馈不是已经放行的运行预算。效用准备登记为 `J_FinQA_execution@H1`；材料资格、Mapper 与实际有效支持仍需独立确定，unknown 不成为合格状态。

## G：真实参数点和诊断虚拟点

事前选择旧 Static seed11、step240（最小既定 seed，不按本轮效果挑点）。真实点加一个明确的数值诊断虚拟点：新 AdamW 零矩、lr=1e-5、全 LoRA 坐标固定梯度1e-4、betas=(0.9,0.999)、eps=1e-8、weight_decay=0。此梯度不是新 FinQA 总体 G，也不延续旧 optimizer 矩；不执行真实 optimizer.step。

从同一 120 题工程校准名册按实际 Qwen 模板选择最短、最长可容纳公开输入，选择过程不看答案或模型结果；真实／虚拟两点各两种长度，总计最多 **4 次新生成**。G 每次最多 256 输出 token，保留 24576 上下文；长输入筛选仍为后续 2048 输出预留空间。固定附加工程指令要求调用 `list_sources` 一次，不解题、不计入 480 条模型结果。

模型采样后只回放原 ID；保留 EOS、RNG 和参数状态隔离、完整 KV 导数，仍用 atol=1e-6／rtol=1e-5。分开报告 `eval_native_passed` 和 `feedback_replay_passed`，数值错误完整保存，不放宽容差。普通执行通过可以进入 H；反馈失败则不准许 VTDO 训练。

## H：固定 480 会话

- 两个模型：未微调基座函数（零 B 的原 q/v LoRA 坐标）与事先指定的旧 Static11 step240。
- 两个 harness：H0 原循环 FinQA 兼容版与修订后的 H1。
- 同一 120 题原始 FinQA calibration，每个模型／harness 完整运行一次，总分母 480。
- 共同 greedy（temperature=0），32 响应、每响应 2048 token、总上下文 24576；生成调用上限 15360，G 的 4 次另列。
- 16 个 30 题分片，按同一 start 波次交错四个条件；最多四 GPU worker。在途任务不迁移。
- 全部 480 生成完成且 worker 退出后才读取参考评分。未知调用停止新工作，无自动重采或换题；完整会话可恢复复用。

H0 不是重命名 H1：使用原 `finance_qa_vnext_fixed_kernel_value.runtime._run` 的私有函数副本，保留旧 `{tool,arguments}`／顶层 `{final:...}`、first-Final、格式错误反馈后继续及 user-role 工具观察。为原 QA 接入，公开来源和计算后端与 H1 共用，增加同一 program 提交合同，因此明确称“旧循环原 QA 兼容版”，不称旧 900 题设置原样复现。原循环及 helper 源码纳入新运行绑定。

H 检验的是接口／迁移，不是 VTDO 收益；旧 Static 对旧协议更熟悉，必须作为解释边界。完成后分别报告 execution/program、Final/程序一致性、轨迹 unknown、错误、tokens 和资源。

## 资源预留和执行状态

08:39 的短暂空闲窗口被其他项目先取得，本项目没有杀进程抢卡。有限监测随后于 08:42 成功预留 GPU0／1／2／3，各 49152 MiB、30 分钟自动到期；这些持有进程模型调用和训练次数均为 0。GPU6 的其他项目未触碰，GPU4／5／7不预留。

正式 worker 先在对应卡剩余空间内加载模型，再按精确 PID＋出生标识释放自己的预留进程，减少从持有到实用的空窗。预留不等于模型已经开始运行，也不是操作系统级独占保证。

运行目录为 `artifacts/finance_research_20260928/audit_followup_01`，`protocol.json` 固定任务、点身份、预算、公开规则、源码和初始 lease；`status.json` 给出 G/H、活动 worker 与阻塞；G 原调用意图和回放结果、H 各分片事件/会话/封存分别保存。

## 实际启动与首批结果（2026-09-28，北京时间）

修订代码和本次冻结执行版本为 `954ad6dab6`。集成测试先完成 238 项；之后控制器新增 5 项测试，并与调用结算、G 检查共 21 项相关回归一同通过。它们是 CPU／接口测试，不等同于金融准确率或训练收益。第一轮测试未覆盖真实 tokenizer 的登记返回类型，具体偏差见下一节。

09:02:57 启动协调器 PID1037391。协议 ID 为 `1f8840f9ba4cb10301fb06362d25a37357ad4e1a4d9917da02dd3736cd24921a`。

G 在 GPU0 上完成，耗时约 85.21 秒，实际新生成 4／4 次、API 调用 0、真实 optimizer.step 0。四个响应均为 16 个实际 token，包含 EOS；原生工具协议往返与原 token 的 logP／可微回放均通过，四例最大 logP 绝对误差均为 0，沿用 atol=1e-6／rtol=1e-5；真实状态和 RNG 未改变。该结论仅覆盖所测两种输入、两个参数点和短 `list_sources` 响应，不是任意长响应、多轮训练链路或金融效用验证。虚拟点仍为固定梯度数值诊断，不是新 FinQA 总体梯度。

H 于 09:04:26 开始启动，四个条件已经在 GPU0／1／2／3 实际并行。对应预留 holder 已释放，卡上保留的是模型计算进程，不再只是占位。09:08:25 的只读快照中已保存 37／480 会话，完整会话内模型调用合计 218，未结算会话 0。这只是即时进度，不是四条件均衡的可比结果；在途调用不计入该已保存合计，也不能由正常终止推断答案正确。全部生成封存前未进行本轮参考评分。

协调器会在 GPU 可用时继续剩余分片，完成全部 480 会话后再评分；遇到未知调用或 worker 失败则保留证据、停止启动新分片，不擅自重采。训练资格和训练收益仍未确认，新的大材料采集和训练尚未启动。

09:12:51 更新：67／480 会话、已保存会话内调用 522、未结算 0；1／16 分片完成、4 worker 活动、blocked 为空。该时刻 GPU0／1／2／3 的本项目计算 PID 分别为 1038790／1046367／1038723／1038724。GPU6 上其他项目 PID643277 未触碰，未追加占用 GPU4／5／7。

## G 长度登记偏差与只读纠错

登记器调用 `apply_chat_template(tokenize=True)` 后直接取 `len()`。本机 Transformers 返回包含 `input_ids`、`attention_mask` 的 BatchEncoding，因此原协议 `gate_prompt_lengths=[2,2]` 实为字段数，选择器退化为按 task_key 字典序取首尾。原协议及四次采样均原样保留，不能追写成“选择算法正确”。

发现后，仅用原公开 120 题、原公开模板和原 tokenizer 在 CPU 重算真实 token 数，不读取参考答案、不调用 GPU/API。选中的 `AAPL/2008/page_38.pdf-2` 为 2309 token（排名 1），`NCLH/2018/page_69.pdf-1` 为 6299 token（排名 120）；两者恰好也是真正极值。120 题均满足 prompt+2048≤24576。因此实际长短输入覆盖没有丢失，但登记字段和选择器有实现缺陷，二者必须分别表述。无需追加任何 G 生成。

后续登记器已在独立工作树 `/tmp/data-synthesis-finance-research-registration-20260928` 修复：先渲染原生模板，再按不补特殊 token、不截断、不填充的 input_ids 数计长，并加入 BatchEncoding 和本机真实 tokenizer 两项 CPU 回归。本轮 G/H 继续在 `/tmp/data-synthesis-fixed-kernel-parallel-tail-20260914` 使用冻结版本，避免运行中改变源码绑定。新提交只供后续登记使用，不能拿修订源码冒充本轮执行版本。纠错只补充旁证，不重写旧协议、旧结果或挑选新响应。

新增两项与既有控制器测试合计 7 项，于本机真实 tokenizer 环境通过（3.80 秒，未跳过）。运行目录另存 `registration_correction/record.json` 指向原协议和上述纠错；不覆盖原始 `gate_prompt_lengths`。

审计定位（SHA-256 为原文件字节摘要）：

- `audit_followup_01/protocol.json`：`59f530eb10503612920fd88166e9cb1d1d303c4c423d8d1c0f28513953024408`。
- `audit_followup_01/gate_complete/record.json`：`611cb483441a63316c79651496f8dc743f170912c8c9c200e25ecf7022895da6`。
- CPU 长度表按 task_key 排序、每行 `{task_key,tokens}`，使用 `contracts.digest`（UTF-8、ensure_ascii=False、sort_keys=True、紧凑 JSON）得到 `0a60df957063b2eac23d5211432de1e0c45871f510a73b3955ba040e48c9f01c`；原 calibration_tasks 同口径摘要为 `54756f03ecff4e638f1580308bfae68e0a789b82761cfee34979d995554e7eda`。计数为公开模板 tokenize=False 后、add_special_tokens=False 的 input_ids 数，未截断或填充。
- 全部逐次生成／回放／参数状态证据位于 `audit_followup_01/gate`；四条件会话位于 `audit_followup_01/jobs`。
