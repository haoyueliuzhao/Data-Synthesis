# VTDO 金融研究主线重构（2026-09-28）

## 结论与边界

本次落实用户提供的两份数据集／金融 harness 调研，新增独立、可执行的 `trusted_synthesis.finance_research` 主入口。研究主线由“持续自产金融 QA 和来源平台”转向“原作者 QA／公开资料 → 真实工具轨迹 → 固定材料核上的 VTDO → 原生指标与轨迹指标分别报告”。

保留最新 anchored AdamW 回传、C/N/π、原包训练 consumer 和分段 token 梯度回放；不以旧 cold-start SGD probe 替换它们。历史数据湖、历史控制器、固定实验源码、原失败与结果不搬移、不改写。旧跨市场实验继续其独立流程；新接口测试不用于宣称其正向训练价值成立。

本次交付是工程重构、真实数据接入及有界接口验证，**不是已经完成新的 FinQA 训练实验**。未发起真实 Student、API、H0/H1 的 480 会话对照或新模型训练。代码存在与真实 GPU 数值准入必须区别：新本地 Provider 与旧分段 replay 的完整 Qwen GPU 对接尚待后续有界验证。

## 新架构

```text
原作者冻结快照
  ├─ PublicTask ──> BigFinance-derived 循环 ──> 真实工具事件／模型 TokenReceipt
  ├─ Lineage ────> 调用前固定角色、任务名册和分母                 │
  └─ PrivateReference ─────────────────────── 全部生成封存后 ──┤
                                                              ├─ 数据集原生指标
                                                              └─ 独立轨迹资格／unknown
合格 SFT 轨迹 + 显式固定状态映射 ──> 原包材料／μ、π 系数 ──> 原训练 consumer
虚拟点的真实反馈回执 ──> 原 segmented_logp ──> gJ ──> 原 AdamW pullback／C、N、π
```

| 文件 | 新职责 | 保留／复用边界 |
|---|---|---|
| `contracts.py` | 公开任务、私有参考、谱系、Provider、回执、Episode | 公共循环只接受 `PublicTask`，不接受含答案 bundle |
| `datasets.py` / `catalog.py` | FinQA、TAT-QA、FinanceMath 最小原始适配与用途登记 | 全表文保留；无 QA 重写、gold 片段裁剪或动态 SEC 请求 |
| `planning.py` | 原 split、父问题、来源组与用途隔离 | 在模型调用前按固定 seed／来源组分配，不按效果挑题 |
| `harness.py` / `tools.py` | BigFinance 受限派生循环、公开读取、算术、明确 Final | 原始／规范／实际参数、原始／可见输出分开记录 |
| `providers.py` | 本地真实 token 回执；DeepSeek Flash 评测；脚本 fixture | API 文本不冒充本地 Student token 或可微回执 |
| `storage.py` | 冻结快照、调用前持久意图、会话保存、整批生成 seal、离线评分 | 完成会话恢复不重采；未结算调用不偷偷重试 |
| `native_metrics.py` / `metric_vendor/` | 固定原作者 FinQA、TAT-QA 评分 | 不把原生指标重命名为 CompletePass |
| `materials.py` | 显式资格／状态映射、固定原包、通用系数与 cache | 只读调用原 `trajectory_consumer.execute_update` |
| `feedback.py` / `kernel.py` | 全分母真实回放、虚拟点梯度、原优化内核 | 不改旧 180／360 人群，不复用旧硬编码 `/5` 系数 |
| `cli.py` | `vtdo-finance` 统一入口 | 旧 `trusted-synthesis` 保留为历史／基础设施入口 |

## 上游版本及实际数据发现

主来源只绑定作者仓库或数据卡，不使用简化镜像取代程序／证据字段：

| 来源 | 固定版本／角色 | 实际验证 |
|---|---|---|
| [FinQA](https://github.com/czyssrs/FinQA) | `0f16e2867befa6840783e58be38c9efb9229d742`；主训练与同任务族测试 | train 6251、dev 883、public test 1147，共 8281 条完整适配 |
| [TAT-QA](https://github.com/NExTplusplus/TAT-QA) | `870accc41953dcde885aabeb963d94aabdc0fbc3`；先作外部测试 | 发布的 `test_gold` 实际 1663 题／277 个上下文 |
| [FinanceMath](https://huggingface.co/datasets/yale-nlp/FinanceMath) | 外部评测，只接受有权使用的本地原作者格式快照 | 适配器及合成 schema 测试已完成；未下载 gated 数据或代替用户接受条件；原生指标未准入 |
| [Big Finance Harness](https://github.com/Rogo-Technologies/big-finance-benchmark) | `d794a65fe583edc6852b44c817b0a2aef33ca831`；仅借用代码结构 | 已读实际 loop/interface 源码并保留 Apache-2.0、哈希与派生说明；没有复制其 benchmark 数据 |

### TAT-QA 不能直接写成“1669 条已就绪”

调研报告中的 1669 是原测试规模。固定仓库的盲测文件为 1669 题／278 个上下文，但 `test_gold` 是 1663／277；两份文件的问题 ID 交集为 0。精确表格＋段落上下文相交 272 个；精确上下文＋问题相交 1626 条，盲测独有 43、gold 独有 37。不能据此简单认定“只缺 6 个答案”，也不能靠顺序拼接 ID 或答案。

本次忠实接入作者实际发布的 `test_gold` 原 ID 和版本，并保存差异统计，没有补题、改标注或强行映射。未来结果必须注明这个 released-labelled 版本和实际分母，而不能宣称完整复现 1669 条盲测集合。

### 服务器上的冻结数据

根目录：`/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/`。

- `snapshots/finqa`：8281 题，ID `451490cf732399ee79c689933b56eb698837ed5370219d6f47c75938ec04368f`。
- `snapshots/tatqa_test`：1663 题，ID `c730e009859d8b00bccf4007cc7d2e9f76e0e5b4e6127b49da09258c1c8f5af3`。
- 每份 snapshot 含 `public.jsonl`、`lineage.jsonl`、`private.references.jsonl`、源文件 hash／commit／数量的 `manifest.json`。没有向 Git 推送整套原始答案数据。

FinQA 保留全部 `pre_text/table/post_text`，`gold_inds`、参考程序、答案、retrieval 选择结果、`qa.model_input` 不进入模型可见对象。TAT-QA 保留全部表格和段落，不公开 `answer_type/answer_from/derivation/rel_paragraphs` 等参考标注。程序步数与参考证据类型可作离线预登记分层，不能作为隐藏提示。

## 角色与谱系

真实 FinQA 第一次确定性来源组规划结果：SFT 1000、反馈 350、工程校准 120、reserve 4781；原 dev 883、public test 1147 保持原用途。plan ID 为 `0a6a8c0d5fc82ea5f691d43535941b38af0f8e8930247a7df5c9531e2bc444ab`。

这些是数据用途规划，**不是已执行的训练数量或训练预算授权**。默认候选数量来自调研建议；按完整报告组分配，普遍情形下允许实际数量小于目标，不拆组凑数。本次恰好满足目标。

FinQA 公司／年份报告组不跨 SFT、feedback、calibration；同原问题、明确父问题或相同上下文＋问题跨用途会拒绝。官方 split 的报告重叠独立列为审计项，不能因保留官方划分就声称公司／报告隔离。TAT-QA 仅知道 context 组，不伪造 report 组。跨库独立性以及基座预训练污染不存在，均未被本次精确指纹检查证明。

TAT-QA 若以后用于训练，必须显式单列实验，不允许通过开关把 FinQA 和 TAT 训练混成一轮又继续宣称 TAT 是外部迁移。FinanceMath 不用于 SFT、反馈或校准调参；MultiHiertt 在 FinQA 父题重叠审核前拒绝训练用途。OpenEnv 的 Snorkel 290 题只作评测，明确不是原始 FinQA 训练集，也不臆造其原 FinQA 父谱系。

## 执行器与模型边界

这里是 **BigFinance-derived VTDO harness**，不是官方 BigFinance 设置。采用注入式 `ModelProvider.chat`、工具分派、显式停止和逐步 trace 的简洁结构，同时固定：

- 默认 32 个响应、每次 2048 输出、本地总上下文 24576；不沿用上游 50／65536 默认预算。
- 每次只允许一个工具；多调用显式失败且不执行其中任何一个。不把无工具文本当作最终答案。
- 不隐藏重试、自动继续、压缩、摘要、审稿、repair、reader 或额度升级。
- 公开工具为 `list_sources/read_source/calculate/final_answer`。无网络、文件工具、任意 Python／SQL；计算工具是有大小限制的 Decimal AST 运算，不是通用安全沙箱。
- `prev:<call_id>.<path>` 只解析本会话真实成功工具输出。这个小解析器借鉴 FinanceHarness 报告中的思路，不宣称已经集成整个 FinanceHarness。
- Final 支持数字、文本、列表、独立 scale 和可选 FinQA DSL program；跨度题不强制计算。程序在模型可见工具中不调用参考评分器。

上游代码许可证和差异在 `vendor/bigfinance/`；FinQA/TAT-QA 官方评分代码固定在 `metric_vendor/`，附各自 MIT 许可及 SHA256。数据许可和代码许可不合并表述。

Provider 的真实调用计数与 `provider.chat` 尝试数分开。脚本 fixture 的真实调用为 0；本地进入 `model.generate` 和 API 发出请求时才增加实际计数。上下文拒绝不伪记一次 GPU 生成。

本地回执绑定实际参数字节、tokenizer/chat template、真实输入 ID、全输出 ID（含终止 EOS）、逐 token 采样 logprob、实际输入消息／工具 schema、RNG 和 finish reason。随机种子与 call ID 取决于注册 seed 和实际请求，不依赖其他任务先前调用数。原始 JSON 参数字节保留；拒绝重复键、非有限数，不做 JSON repair。

DeepSeek API 固定 `deepseek-flash`，无模型回退或自动重试。API 不提供本地真实 TokenReceipt，不能进入 VTDO_FEEDBACK。其 metadata 明确 `context_limit_locally_verified=False`：未声称 API tokenizer／预算与本地 Torch 相同，也未用重新分词文本伪造回执。

## 材料、反馈、评分与恢复

`EVAL_NATIVE` 是普通外部执行／评价路径；`VTDO_FEEDBACK` 还要求真实本地点、T=1/top_p=1/top_k=0、完整 token/logprob 回执和反馈用途准入。原生评测跑通不代表反馈 GPU 数值准入已通过。

新 `prepare_run` 在首次调用前固定模型、配置、任务／seed／参数点名册、源 manifest 和分母。`execute_run` 只读取公共 snapshot 及角色谱系，不打开参考文件；每个模型调用前保存意图。完成 Episode 保存后可恢复跳过，首次封存前还核对耐久末事件与 Episode 一致。未结算调用会停止并要求显式处理，不通过重采掩盖成本或改变样本。全部任务终止后才写生成 seal；`score` 在验证 seal 后才打开私有参考。

这是公开数据对象／执行工具／评分调用路径的隔离，不声称仅凭同一主机文件布局建立了 OS 级权限沙箱。无任意代码或文件工具是第一版的重要限制。

`seal_feedback_cohort` 强制与预登记的完整有序 episode keys、源 manifest hash、分母一致；合法失败保留分母，基础设施失联或缺回执不补成零奖励。反馈 replay 包含全部真实模型响应及 EOS，不 retokenize、不使用 SFT 正例 mask、不按长度归一化。

`materials.py` 要求预声明状态支持、资格判定／validator／证据绑定；不会从答案正确、工具成功、措辞或工具顺序自动推断 CompletePass 或新状态。unknown/invalid 留在清单中；任一声明状态缺合格材料时拒绝训练，不删状态再归一化。单状态任务是静态控制。原包训练系数为 `μ(x)π(z|x)/(n_state × 全包目标 token 数)`，不偷带历史 `/5`。

FinQA 的官方 execution/program 指标要求模型实际提交 DSL program；只有 final 数值时，官方项明确 unsupported，另列项目的 exact-final-answer 诊断，不冒称官方分数。TAT-QA 调用作者 EM/F1/scale 实现。FinanceMath 原生 scorer／答案提取协议尚未绑定，明确 unsupported。各数据集分别汇总支持覆盖、分母与分数；有 unsupported 时完整数据集均值为 null，不将其过滤后冒称完整 benchmark 成绩。轨迹完整语义支持当前默认 unknown，不把原生正确率等同 CompletePass。

## 操作入口

```bash
cd trusted_data_synthesis
python -m pip install -e ".[research]"
vtdo-finance catalog
vtdo-finance preflight --output /tmp/vtdo-preflight-new-directory
```

未安装 console entry 时，用 `PYTHONPATH=src python -m trusted_synthesis.finance_research` 替换 `vtdo-finance`。

```bash
# 仅离线导入一个明确原始 split；路径必须是自己的合法本地快照。
vtdo-finance import --dataset finqa --input /path/to/original/train.json \
  --split train --revision 0f16e2867befa6840783e58be38c9efb9229d742 \
  --output /path/to/new-snapshot
vtdo-finance plan --snapshot /path/to/new-snapshot --output /path/to/new-role-plan

# 只有显式 run 才会调用真实 API；小规模工程校准，不是反馈。
vtdo-finance run --provider deepseek --snapshot /path/to/new-snapshot \
  --role-plan /path/to/new-role-plan/plan.json --role calibration --limit 1 \
  --config config/finance_research.json --env-file /path/to/project/.env \
  --output /path/to/new-generation
vtdo-finance score --run /path/to/new-generation --output /path/to/new-scoring

# 只恢复同一已登记运行；不替换配置／任务名单。
vtdo-finance run --provider deepseek --resume --output /path/to/new-generation \
  --env-file /path/to/project/.env
```

本地入口 `bind-local --output DIR` 只对既有 checkpoint 做 CPU 文件绑定；`run --provider local --checkpoint-binding DIR/checkpoint.json` 才会加载 GPU。必须预设 `CUBLAS_WORKSPACE_CONFIG=:4096:8`，自行指定可用 GPU。可传 `--adapter` 与 `--adapter-record`，复用原 LoRA 载入器；没有 adapter 文件时使用同一基座加零 B 初始化的原 q/v LoRA，以保留明确参数坐标。不自动下载模型，也不抢占本轮或其他项目的 GPU。

原 `kernel.prepare_virtual_point` 返回的 `theta_bar` 必须实际安装后重新绑定 Provider，不能仅改 point_id。新材料训练与反馈接口见对应模块；没有真实 CompletePass 状态资格和 GPU 接线验证，不能据 CPU fixture 自动启动 π 对照训练。

## 实测验收与尚未完成部分

已实测：全量 FinQA 原始三 split 8281 条、TAT-QA released-labelled test 1663 条的 CPU 适配及持久化；实际来源组规划；离线角色／隔离、工具、Provider、回执、恢复、封存和官方指标接口测试。另用 FinQA 首条训练参考程序及 TAT 三种答案类型的原参考作四项 scorer 控制，均得预期原生分值。这只是评分实现控制，不是模型成绩。

一次 4×4 合成 CPU 模型确实通过原 consumer 完成 optimizer step；也不是实际 Student 训练。单独的 `preflight` 只完成三次脚本响应、0 模型／API／GPU调用，所有合成数据显式标注 synthetic。最终统一测试数、preflight 运行身份与提交信息见配套公共验收记录。

尚未完成：

- 新 H1 的真实 Qwen 生成＋梯度回放数值准入；原 GPU replay 已有历史证据，不等于本次新提示／工具接线实测。
- 报告建议的 H0/H1 × 两 checkpoint × 120 题工程对照；不能将旧 Static 的陌生工具迁移表现直接当作 harness 优劣。
- 新数据上的实际多状态语义验证、材料采集和 VTDO/Static 对照训练；不得把官方参考程序当作真实模型轨迹。
- FinanceMath 的合规本地快照及官方评分绑定、跨库谱系独立性审核。
- MultiHiertt、BankMathBench、长文 RAG、EdgarTools／OpenBB 数据接入和完整 FinanceHarness 系统对照。这些是后续独立扩展，不应为了给定表文 FinQA 第一轮而整栈引入。

因此，本次可以宣称“新的原始 QA 工程主线已落地，保留研究内核且界限可审计”，不能宣称已完成报告的全部后续研究，也不能宣称获得新的正向训练收益。
