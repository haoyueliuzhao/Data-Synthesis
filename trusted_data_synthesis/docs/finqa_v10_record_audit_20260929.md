# 原8000轨迹：记录、投影与Student文本机械核对

## 1. 结论范围

已对原 `new_full_probe_v8_launch_01` 的1000题、8000个原登记槽完成有界机械核对。成功产物为 `STUDY/process_review_v10_01/record_audit_02/`。

在本次明确的记录层检查中，8000条均通过原Episode字节/内容绑定、原公开初始输入、实际API正文与解析调用、动作—观察对应、实际请求历史回填、公开视图及Student文本渲染检查，未发现机械差异。

这支持“现有库存保留了公开正文与真实工具交互，而不是仅有工具调用列表”，但**不证明8000条均有实质推理、正确理解了观察或具有正确的金融推导**。没有将R标签、字符数、工具次数、参数改变或原生正确率当作过程质量。没有生成正向mask，也没有据此放行训练。

本次不重评分、不重新执行原工具，不调用任何模型/API、不使用GPU、不打开钱包、不更改原件或运行中的政策。

## 2. 全量实际计数

| 记录事实 | 实际数量 |
|---|---:|
| 原任务／原槽 | 1000／8000 |
| 有非空公开正文的Episode | 8000 |
| 实际保存的模型轮次／请求对象／原API响应字符串 | 16286／16286／16286 |
| 非空公开正文轮次 | 16286 |
| 公开正文字符数 | 3872586 |
| 原API调用条目／解析调用／保存工具事件 | 16243／16243／16243 |
| 公开视图正文／参数／观察段 | 16286／16243／16243 |
| 观察进入下一轮实际请求的Episode | 7590 |
| 进入下一轮实际请求的观察事件 | 8286 |
| 位于终态后、因此没有下一次请求的观察 | 7957 |
| 有工具错误的Episode／错误事件 | 85／127 |
| 未解析API调用条目 | 0 |
| 非空独立reasoning_content字段 | 0 |
| Student文本成功渲染轮次 | 16286 |
| 机械差异Episode | 0 |

终态分别为7957个 `final_answer`、43个 `no_tool_call`。这里只报告原保存状态，不把后者伪装成基础设施UNKNOWN，也不从显式提交推出答案正确。

复用原native报告的Q=True为5691、Q=False为2309；没有再打开private reference评分。它们仍与过程有效性、训练准入分开。

以下表面事件模式不是互斥分组，也不是语义质量等级：

| 固定机械模式 | Episode数 |
|---|---:|
| 仅一次实际成功submit_program，即直接提交 | 374 |
| 实际run_program之后成功submit_program | 7521 |
| 实际错误事件之后出现名称/原参数不同的后续动作候选 | 85 |
| 完整已结算会话，原Q_native=False | 2309 |

85个“错误后改变动作”只是**待语义核对的修订候选**；不能写成85条已证实的有效修订。

## 3. 检查了什么、没有检查什么

全量检查每条原Episode的现有字段，比较实际请求的消息历史与原公共输入＋原assistant正文/调用＋原可见工具观察。没有用Host生成的理想推理补齐历史，也没有强制要求先read_source才可使用初始已可见资料。

公开视图沿用原 `public_trajectory_view`：正文保持原字符串，动作参数保持原参数字符串，观察保持当时实际可见输出。Student文本沿用原 `_student_messages` 与 `_native_response` 及冻结Qwen tokenizer模板；API历史中的参数对象化是已有适配，不冒充API原采样Token。

全量完成的是文本层渲染与原内容存在性核对，没有为全部8000条重做Token级准入。只有下述4个固定案例进行了真实CPU tokenizer的完整Token往返核对；其余Episode不据文本渲染自动得到正向mask或24576上下文准入。

没有对整个历史归档重新递归hash/重读事件目录；持久事件日志的详细顺序与payload对照只针对4个固定案例。全量Episode本体每次扫描只读一次。

明确未测：

- 任务相关解释的实质性及金融推导正确性；
- 观察是否在语义上改变了接受判断；
- “错误后改变动作”是否构成有意义、有效的修订；
- 公开解释是否忠实于供应商内部全部计算；
- 新过程审阅资格、状态归类与SFT监督决定。

## 4. 四个固定顺序完整案例

选择规则在扫描前登记：按原 `protocol.slots` 顺序，取每类第一个匹配记录；不按成功程度、正文丰富程度或后续Student表现换例，允许类别复用。本次实际得到4个不同原包，序号采用从0开始的原登记ordinal。

| 类别 | ordinal／题目 | 原工具事件 | 原Q_native |
|---|---|---|---:|
| 执行后提交 | 0，GIS/2008/page_83.pdf-1 | run_program→submit_program | True |
| 正常模型失败 | 8，MAS/2017/page_37.pdf-1 | run_program→submit_program | False |
| 错误后改变动作候选 | 19，TSCO/2017/page_68.pdf-3 | 错误run_program→成功run_program→submit_program | True |
| 直接提交 | 24，DRE/2016/page_64.pdf-4 | submit_program | True |

原完整案例位于成功审计根目录下：

- `cases/original_0000/record.json`
- `cases/original_0008/record.json`
- `cases/original_0019/record.json`
- `cases/original_0024/record.json`

每例包括原完整消息、原公开正文、原API tool_calls、解析调用、当轮实际请求、下一轮实际请求、实际工具事件、公开视图、完整Student prompt/response及原件路径/摘要。字段入口是 `turns[]`、`public_view`、`original_messages`、`durable_events` 和 `Student_token_roundtrip`。

4例共检查40份持久事件文件，顺序与原payload一致；合计8轮实际Student Token往返全部精确，保留完整文本，没有裁切：

| 案例 | 各轮完整序列Token数，计一个Student EOS |
|---|---|
| ordinal0 | 4212、4416 |
| ordinal8 | 4050、4253 |
| ordinal19 | 4168、4358、4644 |
| ordinal24 | 4506 |

此处EOS是Student离线表示事实，不是API采样收据；`target_positions=null`，没有替代尚未作出的监督决定。这些个例Token数不能外推为8000条的完整长度分布。

## 5. 首轮发布故障及一次必要补跑

首次 `record_audit_01` 在74.29秒完成8000条扫描，但最后给不可变工件工具传入嵌套 `cases/.../record.json` 文件名，触发“只允许本地文件名”的发布限制。主results尚未创建，内存结果随进程结束丢失；不能虚报首轮的检查通过计数。

01的原registration保留，追加：

- `publication_failure/record.json`：真实失败说明、已观察到的扫描完成进度及固定case序号；
- `publication_failure/audit_source.py`：首轮实际源码快照，与起始source_bindings一致；
- `source_identity_clarification/record.json`：说明01旧 `source_commit` 取自canonical checkout的HEAD，并非执行工作树提交；该字段没有覆盖。

在主执行流程明确确认后，只修正发布组织和来源元数据，按完全相同的8000分母、检查判据、原登记顺序和case规则进行一次必要补跑。没有重评分、重执行工具或新增模型调用。成功02报告明确 `scan_attempt_index=2`，并引用首轮失败记录；**整个工作实际扫过两次，不能声称只扫过一次**。

02扫描约82.54秒，统计生成阶段累计82.74秒。来源元数据使用真实工作树 `/tmp/data-synthesis-finqa-process-review-20260929` 的基线提交 `860109eebd5928e78840353b90c69e4f92d90c81`。新未提交执行文件以source_bindings为准，成功归档的audit_source.py与起始绑定一致：

`82c257a14b0474d800ea020bfff254a366a916ade477b7067317c065da71015d`。

现在先不可变发布report/rows/source，再分别发布案例，最后写complete索引；发布单测覆盖此路径。7项必要CPU合成/发布控制通过，Ruff通过。后续未修改本次已经执行的审计源码。

## 6. 成功工件与复现入口

成功报告：

`STUDY/process_review_v10_01/record_audit_02/results/report.json`

报告ID：

`7b2569744e85358acf10212bc015d92067fbf07ec1c5a5ef009c4fce01dba3e5`。

完整发布索引：

`STUDY/process_review_v10_01/record_audit_02/complete/record.json`

ID：

`984dd1236f2fcac7765e3d252b1fa45de648b5e628334b57f471af36a59ebc66`。

8000轻量逐槽结果位于 `results/rows.jsonl`；起始登记位于 `registration/record.json`；源码副本位于 `results/audit_source.py`。案例路径相对于审计根目录，而不是results子目录。

实际补跑命令：

```bash
PYTHONPATH=trusted_data_synthesis/src \
/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/.venv/bin/python \
  -m trusted_synthesis.finance_research.v10_record_audit --workers 8 \
  --output /data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/process_review_v10_01/record_audit_02 \
  --recovery-of /data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/process_review_v10_01/record_audit_01/publication_failure/record.json
```

不要为重复证明已有结果再次全量扫描。后继可读取已绑定的逐槽机械记录与固定案例，并把新的语义审阅/监督定义独立登记；不能将本报告的机械通过直接改写为过程valid或训练价值。
