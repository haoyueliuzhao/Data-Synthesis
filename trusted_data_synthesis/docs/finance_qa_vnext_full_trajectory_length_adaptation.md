# QA vNext：原样完整轨迹的独立长度条件适配

日期：2026-09-06。阶段：
`finance_qa_vnext_full_trajectory_representation_length_adaptation_only`。

## 1. 审计接受范围与本轮唯一问题

本轮依据用户提供的 559 行《本轮审计与后续实验方案》推进。附件 SHA-256 为
`79d1658bd7442a5343765664db3f3f9a1bdbd7ab9fdbc43bbb8bb42fdd1bfba0`。
既有 Action 修复及 B 完整可达性结论为 `PASS_AS_SCOPED`，没有强制历史修订、
重跑 B 或增加同内容独立审计的要求。本轮不重新打开 Action、Update、Registry、
Finance 数值验证或有限商比较。

唯一问题：固定两个已经 Qualified 的 B 会话及全部 34 条原请求—原响应，
能否在实际配置支持的独立 32,768 表示条件下，形成两个完整可消费的监督包？
这是表示资源条件变化，不是教师条件变化，也不是在相同 24,576 预算下消除超长。

输入锚定已发布提交 `9471c222b308e5de17b5aba1f9ceb673cb5186af` 的：

```text
trusted_data_synthesis/artifacts/qa_vnext_action_branch/
  action_contract_branch_v1_20260906/
    preparation/tokenizer_binding.json
    execution/analysis/supervision_candidates.json
    execution/analysis/token_representations.json
    execution/analysis/qualifications/{B01,B02}.json
    execution/analysis/exports/{B01,B02}.json
    execution/sessions/{B01,B02}/{runtime,transport}/...
```

历史目录 701 个文件先与发布提交的 Git blob 原始字节核对。后续只消费已接受的资格及
父绑定，不调用 `qualify_session`、`audit_session` 或任何 Finance Operation。
原始 HTTP body、原 target UTF-8 字符串和当前轮 Request 的绑定仍逐行核对，
这些是表示来源检查，不是再次测量或重新赋予模型资格。

## 2. 预先固定的范围与停止条件

| 对象 | 本轮固定处理 |
| --- | --- |
| 原任务、有效会话、监督候选 | 原 B，2 个会话，34 条，不替换、不删行 |
| 新表示条件 | 1 个；完整序列上限 32,768 |
| 教师条件与全部原始内容 | 保持不变，不归一化目标 JSON，不压缩状态，不注入未来状态 |
| Tokenizer、词表、模板、软件版本 | 同一历史绑定所指向的精确资产及版本 |
| Mask、因果位移、suffix | 原 assistant 内容监督；位移 1；suffix 两 Token 不参与 loss，但计入长度 |
| 新会话／Provider／Runtime 执行 | 全部 0 |
| Student 权重／forward／更新／GPU | 全部 0 |
| CPU 加载 | 每批最多 2 行，同一会话内动态右侧 padding，不拼接成整段聊天 |
| 新来源、任务面板、类权重、Contribution、P/Q 损失 | 全部不启动 |

通过条件只有：原始输入与身份不变；实际本地配置支持新上限；34 条真实编码及 mask
正确；两会话所有准入单元完整。若仍有不合规行则保留原始候选和诊断，不通过丢行、
截断、改写或提高至 tokenizer 声明的 131,072 来补救。

本轮完成后停止，不自动进入审计所建议的未来统一条件 QA 面板采样或 Student 实验。

## 3. 资产身份与表示政策分离

历史 tokenizer binding 保留原 ID：
`share_training_tokenizer_binding:19bd113181c70cdc83291facccc25e7bc28ecd789588be5020ba9940d4fbaf58`。
它的 `maximum_sequence_length=24576` 及历史 Student 配置文件均不修改。

新阶段新增独立内容寻址 `tokenizer_assets` 和 `condition`：前者绑定五个成员哈希、
模板哈希、软件版本、模型 revision 以及实际 `config.json`；后者将这些资产与 34 个
候选 ID、两个资格 ID、教师条件、原表示数据集及新长度政策相连。
新 Token 记录使用独立 `qa_vnext_length_adaptation_token_record.v1`，每条携带新条件、
资产 ID 和旧 Token 记录 ID，不冒用旧 Token 记录或旧 binding 的身份。

服务器上的实际配置读取结果为 `max_position_embeddings=32768`、`rope_scaling=null`。
完整准备和执行仍须重新校验同一五文件的字节及软件版本，不能只依赖这段文字。
tokenizer 声明的 `model_max_length=131072` 仅记录，不作为位置权限。

共享编码器仅提取显式长度参数：历史 `tokenize_candidates` 和私有默认入口仍固定
24,576，完整渲染、无截断编码、offset、UTF-8 恢复、suffix 和 mask 算法保持不变。
回归测试要求历史公开入口对全部 34 条输入重现整个旧 Token 数据集的原始规范字节，
包括原两条 `not_fit` 的空消费数组及原数据集 ID。

## 4. 每行与整会话检查

每条完整序列必须精确满足：真实 prompt prefix + 原 target 字符串 + 既定 suffix。
编码不截断；目标 Token 连续且有因果前驱；目标 Token 解码恢复原 UTF-8 内容；
prompt、角色头、EOS、suffix 和 padding 的 labels 为 `-100`。完整长度包括 suffix。

对原 32 条 fit：比较四个编码数组、目标位置、渲染哈希、长度和全部非政策诊断。
对原两条 not-fit：从原始候选重新编码，比对原渲染哈希、长度和边界；旧消费数组是
`null`，因此不伪称完成了不存在的旧数组比较。

两条原 T16 的已知长度 24,885 / 24,924，对新上限的预期余量为 7,883 / 7,844；
这是准备阶段基于历史长度的预期，不代替新编码结果。

会话完整性分母来自历史 Session 的全部实际 admitted events，不从已经筛过的 fit 行
倒推。每个包应为 8 Action + 8 Update + 1 Final，共 17 个独立响应监督单元，
特别单列 T16 与 T17。包是逐真实请求的监督集合，不是把 17 个请求合成一条长序列。

CPU 加载使用小批次、实际张量与确定性 NPZ 回读。检查动态 padding、attention、labels、
目标 mask 与 `labels[:, 1:]` 的因果前驱；不运行模型、受控 NLL、旧 P/Q 权重或 loss。
NPZ 仅为 CPU 整数数组，不含参数权重。

## 5. 最少局部控制与零执行边界

局部控制包括：删除任一 T16 但保留 Final 必须判包不完整；改变目标 JSON、未来 Request、
跨会话 Request 或候选数必须拒绝；截断 prompt、目标尾或 suffix、漏计 suffix、错误
监督 prompt/suffix、漏掉目标尾、错误因果位移及跨会话 Token 父引用必须拒绝。
旧 binding 同 ID 改长度、重新计算 ID 后改旧长度、伪造旧结果、新上限改为 131,072 或
引入 RoPE 扩展均不得通过冻结条件检查。

运行期对 Provider sender、模型 callback、credential 读取、socket connect、Runtime
构造、Program/Share execute、资格及域审计重算、Student Module 构造、权重加载与 CUDA
初始化安装抛错计数器。另拦截 `.env` 和本地模型目录非绑定文件的读取。
准备和执行分别保存守卫计数；CPU 张量实际检查 `device=cpu`。
这些计数说明受监测入口未被调用，不把它们说成针对任意第三方代码的形式化隔离证明。

历史四阶段工件在准备前后和执行前后作文件清单与字节哈希比对。
本轮代码和测试也作冻结快照；运行中任何漂移导致拒绝。新输出不允许覆盖已有目录。

## 6. 可复现入口

从仓库根目录，使用现有环境，不安装或下载资产：

```bash
PYTHONPATH=trusted_data_synthesis/src trusted_data_synthesis/.venv/bin/python \
  -m trusted_synthesis.experiments.finance_qa_vnext_length_adaptation prepare \
  --root /data1/zhuxinrui/projects/Data-Synthesis \
  --output trusted_data_synthesis/artifacts/qa_vnext_length_adaptation/original_32768_v1_20260906/preparation

PYTHONPATH=trusted_data_synthesis/src trusted_data_synthesis/.venv/bin/python \
  -m trusted_synthesis.experiments.finance_qa_vnext_length_adaptation run \
  --root /data1/zhuxinrui/projects/Data-Synthesis \
  --preparation trusted_data_synthesis/artifacts/qa_vnext_length_adaptation/original_32768_v1_20260906/preparation \
  --output trusted_data_synthesis/artifacts/qa_vnext_length_adaptation/original_32768_v1_20260906/adaptation
```

完成后不要重用以上输出目录。`verify --output <directory>` 只读检查该目录完整清单和
哈希，不重新调用模型、重建 Token 或重判任务资格。

## 7. 正式结果

### 7.1 冻结、实际运行与结论

正式准备和适配已完成，源提交为
`7ad17013286c0cd09bc007be91d68f36cd06d85d`。上述第 1–6 节先于正式运行提交，
本节在实际输出与 CPU 文件回读之后追加，不把预期余量当作事先通过结果。

新表示条件：
`qa_vnext_length_adaptation_condition:f148b6fa4fadd2ae8c57326a4d638c378061b9076674c7e838b66f82916e6fc2`。
资产身份：
`qa_vnext_length_adaptation_tokenizer_assets:e4cd677e56122d1b99f174ab605d257be1dc7e7b2becfd0aded26ff1e89f88e0`。
正式报告：
`qa_vnext_length_adaptation_report:ee16c07f1972e0c19c3de49c791d7d725b61883d14d4d534ffd0ce2bd638d9e6`。

实际完成对象如下；两个条件的差异不能解释为相同预算下的修复。

| 表示对象 | 旧条件：24,576 | 新条件：32,768 |
| --- | ---: | ---: |
| 原始候选数 | 34 | 同一 34 |
| 可消费 Token 记录 | 32 | 34 |
| not-fit 记录 | 2 | 0 |
| 完整会话监督包 | 0/2 | 2/2 |
| 数据集状态 | `contains_not_fit` | `all_fit` |
| 全量正向表示验证 | false | true |
| 原始内容、目标 JSON、状态、模板变化 | 无 | 无 |

原 32 条 fit 的四个数组、渲染和非政策边界诊断全部一致。两条原 not-fit 重新编码后
生成完整消费数组，原候选 ID、长度、渲染哈希、目标 UTF-8 内容和目标边界均保持不变。
旧数组为 `null` 的事实保留，比较记录中对应的 `arrays_identical=null`，不是伪造的 true。

新 Token 数据集 ID 为
`qa_vnext_length_adaptation_token_dataset:e65591c8907132c3b4e35ae6da3970c63de07f917a8c95f11083abbb1b3ab530`。
旧数据集 ID
`qa_vnext_model_execution_token_representation_dataset:e68d8863055587a9acd1fafe5ba48fffcd21a48b4d4ff784f3625647cc79e10e`
及其 `contains_not_fit` 内容没有回写。

### 7.2 两个关键 T16 与整会话完整性

| 原记录 | Prompt | Target | Suffix | 完整长度 | 新上限余量 | 新状态 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| B01/T16 Update | 23,913 | 970 | 2 | 24,885 | 7,883 | fit |
| B02/T16 Update | 23,932 | 990 | 2 | 24,924 | 7,844 | fit |

两者都没有变短。原来超出 24,576 的 309/348 Token 仍是原历史条件下的真实超长。
新上限容纳了它们，而不是删除 target 尾、忽略 suffix 或去掉后期 accepted Claims。

| 会话包 | Action | Update | Final | 可消费／应有单元 | T16 | T17 |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| B01 | 8 | 8 | 1 | 17/17 | 保留并可消费 | 保留并可消费 |
| B02 | 8 | 8 | 1 | 17/17 | 保留并可消费 | 保留并可消费 |

每个单元绑定自己的原 Request、原 Submission、候选及 Token 记录，既没有跨会话替换，
也没有把十七次完整请求拼成一个新长对话。B 两会话的 Qualified 结果被复用，不是本轮
又获得了两个新模型成功样本。

### 7.3 CPU 加载的实际范围

保存并回读了 18 个 CPU NPZ 小批次：每会话 8 个双行批次和 1 个单行批次。
全部 34 行恰好加载一次，最大实际序列长度为 24,924，最小为 20,882；没有把所有行
统一 padding 到 32,768，也没有整会话拼接。

同一 tokenizer 下，34 条记录的总量为：

```text
prompt tokens       749,286
target tokens        25,197
suffix tokens            68
实际序列 tokens      774,551
动态 padding tokens    8,768
```

以上是本地 Token 表示与 CPU 加载计数，不是新增 Provider usage，也不是模型 forward
的实测代价。目标 mask 与实际 labels、动态 attention/padding、目标 UTF-8 解码以及
`labels[:, 1:]` 对应的合法前驱均检查通过；磁盘 NPZ 中的数组与正式 Token 记录逐行一致。

本轮只完成原样 Token 表示、实际模型配置边界及 CPU 消费接口，未测量 GPU 显存、
训练吞吐、优化器行为、Student 可训练性或学习收益。`training_or_utility_validated=false`。

### 7.4 测试、控制、历史与零执行证据

源冻结前的 27 项测试全部通过，耗时 298.96 秒，无失败、错误或跳过；受测实现与正式
冻结源码一致。测试包括实际 CLI prepare/run/verify、拒绝覆盖已有输出目录，以及
历史公开 Token API 对全部 34 条记录逐字节复现整个原数据集。
测试日志 SHA-256：`ce42c20cec896161afe7aee8a5a701f841a587885a61592f0f754156f1d988ba`。

正式运行的 21 项局部表示控制全部得到预期结果：其中删除 B01 或 B02 的 T16、
保留 Final 时，相应完整包失败，分母仍为 17、剩余可消费单元为 16；其他变造按其
内容、父绑定、边界或身份错误拒绝。它们不是新的教师轨迹、模型样本或任务测量。
没有重跑历史 145 项协议测试、69 项 Action 控制或重新执行历史财务资格审计。

准备、正式适配及发布回读中的 16 个禁用入口计数全部为 0，CUDA 均未初始化。
新 Provider、模型会话、Finance Runtime/Operation、资格重算、Student 权重/forward/
更新和 GPU 作业均为 0；本轮也没有读取 `.env`。

全部 9,514 个历史工件、420,810,288 字节保持不变；其中本轮直接来源的 701 个文件
与已发布父提交的 Git blob 原始字节一致。1,216 个源代码/测试文件的冻结快照不变。
另核对历史 Student 配置、canonicalizer、Protocol、Runtime、独立 measurement、
Action/Update publication、两个 adapter 和 tokenizer binding 实现，共 10 个受保护
文件，与父提交字节一致。唯一共享实现改动是第 3 节所述的显式长度参数提取。

发布回读只验证持久化的数组与来源/文件绑定，没有再次 Token 化、执行任务或重判资格。
回读记录 ID：
`qa_vnext_length_adaptation_publication_verification:4f47a56532dd0f551ba7e57f9e1bd09c158a15f5081f5804c3add50b3fdc5b0c`。

### 7.5 工件入口

本轮新目录为 `artifacts/qa_vnext_length_adaptation/original_32768_v1_20260906/`，
共 43 个文件、14,071,814 字节：准备 11 个、适配 27 个、发布验证 5 个。
不复制或改写历史 HTTP 目录、模型权重或 tokenizer 资产；CPU NPZ 是整数输入数组。

- [正式报告](../artifacts/qa_vnext_length_adaptation/original_32768_v1_20260906/adaptation/report.json)
- [完整会话包清单](../artifacts/qa_vnext_length_adaptation/original_32768_v1_20260906/adaptation/session_packages.json)
- [逐行长度](../artifacts/qa_vnext_length_adaptation/original_32768_v1_20260906/adaptation/lengths.json)
- [新旧表示对照](../artifacts/qa_vnext_length_adaptation/original_32768_v1_20260906/adaptation/historical_comparison.json)
- [CPU 加载及批次引用](../artifacts/qa_vnext_length_adaptation/original_32768_v1_20260906/adaptation/cpu_loading.json)
- [局部控制](../artifacts/qa_vnext_length_adaptation/original_32768_v1_20260906/adaptation/controls.json)
- [发布回读与测试证据](../artifacts/qa_vnext_length_adaptation/original_32768_v1_20260906/publication_verification/report.json)

## 8. 收口与后续边界

本轮原样完整轨迹表示适配完成：34 个原始候选、34 条可消费记录、2 个完整会话包。
它使已经获得的深度三有效行为原样接入 CPU 监督接口，不增加模型行为样本量，
不升级为新商类、贡献估计、权重优化或 Student 效益证据。

下一项研究可按审计建议另行冻结统一 Action/Update publication、模型条件及训练表示
下的 QA 任务面板和 `mu(x)`，明确已有来源及缺失类型，再开展同条件采集。
本轮未启动该面板，不拼接旧条件成功率，不为获得非退化商分布而事后删任务；
旧主线保持暂停。
