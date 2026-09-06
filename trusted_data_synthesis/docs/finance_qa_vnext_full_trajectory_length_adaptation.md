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

此处先登记方案；正式准备、编码、CPU 加载及测试完成后再填实测结果。当前不预填
`34/34` 或 `2/2` 表示通过，也不改写旧 24,576 下的 `contains_not_fit`。
