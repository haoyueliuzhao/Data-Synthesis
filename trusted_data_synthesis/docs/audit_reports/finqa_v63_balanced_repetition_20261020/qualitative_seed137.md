# V63 seed137：固定 12 对的助手逐例定性阅读

日期：2026-10-20。阅读者：本轮协作助手。本文是助手逐例阅读已保存输出后的定性记录，不是独立人工评审、人工签字或盲化标注。

## 1. 范围、来源与实际完成量

只读旧反馈批次 b=0、step894 dev883、seed137 的 C1→C05 固定选择：I→R 六对、R→I 六对，共 12 对、24 侧原 episode。未读取 seed251/389 的定性样本，未补选、扩样或重新排序。

冻结来源：

- 规则 ID：`7fc72b1db84b8765ddc5632a23703061fdb20c2215f25d88ed7e1cb8c0e97d73`。
- selection ID：`8a123abcaf73fd725b6155a91c05683d064579f885c935bb396309e8e80a0e23`。
- reading packet ID：`ddd93457381ea6012664548c69eefd3a0d0a5b332e65dd36f3c9ac8f1e1066a8`。
- selection 与 packet 分别位于新科学根 `v63_balanced_feedback_repetition_01/diagnostics/invalid/batch0/selection/record.json`、`reading_packet/record.json`。

本次先读取 packet 中 seed137 的原生结果、选择摘要与原文件引用，再实际打开 24 侧原 `episode.json`：逐例完整阅读全部 `turns[].raw_text`、保存的 `tool_calls` 及全部 `tool_events`，同时读取停止原因、实际调用数与最终答案字段。对这 24 个原文件分别读取完整字节计算 SHA256；24/24 与 packet 的绑定一致，缺失文件为 0。全量 token ID、logprob 数组不属于本次定性阅读内容，不将“完整文件 SHA 已核对”冒称为逐项人工审阅了所有数值数组。

实际阅读完成 12/12 对、24/24 侧，覆盖 36 个已保存模型返回 turn 和 26 个已发生工具事件。本文所写工具返回值与提交动作均来自旧事件，不是本次执行。未调用模型、重执行工具、修补输出、重新评分或计算反事实准确率；原 I/R 标签沿用已有原生评价。

原 packet 的 `manual_reading_completed=False` 保持不变，没有回写冻结或已封存记录。本文仅新增助手阅读证据，不能解释成原 packet 已获得独立人工签字。

## 2. 逐对观察

以下 I 表示原生 invalid，R 表示原生正确。`submit_program` 工具返回 `submitted:true` 只说明提交动作已发生，不等于提交程序一定可执行或正确。

### P01．`finqa/BLL/2010/page_28.pdf-1`，I→R

来源：附录 P01-C1、P01-C05。双方各 2 个返回 turn。

C1 第一轮有完整 `<tool_call>…</tool_call>`，实际调用 `run_program`，程序为 `subtract(178.93, 100), divide(#0, 100)`；旧工具事件成功返回 `0.7893`。第二轮文字复述 78.93%，表示执行已确认算术、无需再读来源，但没有任何工具封套或提交。终态为 `no_tool_call`，原生理由 `missing_or_invalid_submission`，I。

C05 第一轮使用同一程序，实际运行同样返回 `0.7893`；第二轮以完整封套调用 `submit_program`，旧事件保存 `submitted:true`。终态 `final_answer`，R。

谨慎解释：本对直接可见的差异是同一已运行程序在 C1 端没有完成正式提交，在 C05 端完成提交。不能把此对称为算术或抽象推理改善，也不能补造 C1 的提交后重新计分。

### P02．`finqa/MRO/2006/page_33.pdf-2`，I→R

来源：P02-C1、P02-C05。双方均只有 1 个返回 turn。

C1 的文字已列出 24、77、71 mbpd，并说明要求三者总量，却提交了三次重复的 `table_sum(matching buy/sell volumes, none)`。工具封套及 `submit_program` 均被接收，已有事件 `is_error:false`、`submitted:true`；终态 `final_answer`，但旧原生评价为 `nonexecutable_submission`，I。没有先执行 `run_program`，提交事件也没有给出原生执行器的具体异常文本。

C05 同样从文字中的 24、77、71 出发，实际提交 `add(24, 77), add(#0, 71)`；封套完整，提交事件成功，旧原生评价 R。

谨慎解释：不是“C1 未输出合法调用封套”。差异涉及程序构造和操作数表达：重复 table 操作变为显式数值加法。`submitted:true` 与后续原生不可执行判定可以同时成立，不能把无工具错误标志误写成程序可执行；也不从这一个样本推断一般推理能力变化。

### P03．`finqa/IP/2005/page_35.pdf-4`，I→R

来源：P03-C1、P03-C05。C1 为 1 个返回 turn，C05 为 2 个。

C1 仅有文字：使用总债务 11,810 与未来义务 6,281，表示将计算 `6281 / 11810` 并直接提交；原输出没有工具封套，`tool_calls` 和 `tool_events` 均为空。终态 `no_tool_call`，`missing_or_invalid_submission`，I。

C05 的文字改为 2005 债务 1,181 和总 contractual obligations 4,617，第一轮实际运行 `divide(1181, 4617)`，既有事件返回 `0.25579`；第二轮完整封套提交同一程序，R。

谨慎解释：这里同时改变了数值/分母解释与交付行为，不能概述为“仅补格式”。本阅读未另外打开任务私有答案、改写 C1 程序或计算其假设性得分，只记录保存的两套取数和原生结果。

### P04．`finqa/AES/2015/page_117.pdf-3`，I→R

来源：P04-C1、P04-C05。双方各 1 个返回 turn。

C1 文字列出 205、163、110，并称要计算 recoverable environmental capital expenditures 的平均；随后转而使用 `proportional non-recoverable environmental capital expenditures` 作为行名，提交 `table_average(proportional non-recoverable environmental capital expenditures, none)`。完整提交封套被接收，旧事件为 `submitted:true`、`is_error:false`，但原生评价是 `nonexecutable_submission`，I。

C05 文字同样列出 205、163、110，完整封套提交 `add(205, 163), add(#0, 110), divide(#1, const_3)`，R。双方都没有在提交前调用 `run_program`。

谨慎解释：本对可见的是程序表达的变化，还包括 C1 文本中 recoverable/non-recoverable 标签不一致；不能仅归为封套问题。提交事件未保存原生执行器具体报错，故不自行指定它究竟是行名、操作格式还是其他解析细节触发。

### P05．`finqa/ZBH/2017/page_71.pdf-1`，I→R

来源：P05-C1、P05-C05。C1 1 个返回 turn，C05 2 个。

C1 文字写明 2016 年 42.5、2015 年 40.2，并写出变化 `42.5 − 40.2 = 2.3 million`，但没有任何工具封套或工具事件；终态 `no_tool_call`，I。

C05 第一轮也写出相同数值与减法，并实际运行 `subtract(42.5, 40.2)`；旧事件返回 `2.3`。第二轮完整封套提交同一程序，R。

谨慎解释：文字中的算术内容相近，但只有 C05 完成原协议的可核查程序交付。C1 文字给出数值不改变其原生 invalid 标签；本文不把这类可见算术文字直接当成“若提交就一定正确”的新增评价。

### P06．`finqa/TROW/2010/page_22.pdf-2`，I→R

来源：P06-C1、P06-C05。双方各 2 个返回 turn。

C1 第一轮有完整 `run_program` 封套，实际运行 `divide(240.0, 5.0)`，旧事件返回 `48.0`。第二轮文字称应提交产生结果的程序，只写 `Program: divide(240.0, 5.0)`，没有 `<tool_call>` 或实际 `submit_program`。终态 `no_tool_call`，I。

C05 运行相同程序并得到 `48.0`，随后完整封套提交同一程序，R。

谨慎解释：本对区分了“在 prose 中写出 Program/submit 意向”和“真正被原系统接收的提交动作”。C1 已有成功运行记录，失败出现在随后交付边界，不能因此断言需要新的数值求解能力。

### P07．`finqa/ABMD/2004/page_26.pdf-4`，R→I

来源：P07-C1、P07-C05。C1 2 个返回 turn，C05 1 个。

C1 根据 769 与 4,578，完整封套运行 `divide(769, 4578)`，旧事件返回 `0.16798`；随后完整封套提交同一程序，R。

C05 文字列出同一组数值并表示将计算 `769 / 4578`，但整轮没有工具封套，`tool_calls`、`tool_events` 均为空；终态 `no_tool_call`，I。

谨慎解释：本对可见 C05 有运算意向但没有实际交付。它与前述 I→R 个例方向相反，提醒不能把温度影响概括成单向的协议改善；文本意向不构成已执行程序。

### P08．`finqa/AES/2016/page_185.pdf-2`，R→I

来源：P08-C1、P08-C05。C1 2 个返回 turn，C05 1 个。

C1 先完整封套运行 `subtract(618, 460)`，旧事件返回 `158.0`，再完整封套提交相同程序，R。

C05 文字同样列出 2016 年 618、2015 年 460，并称会计算差值，但没有工具调用封套、已执行程序或提交事件。终态 `no_tool_call`，I。

谨慎解释：在这对保存轨迹中，取数和运算意向并未落实为 C05 的正式提交。不能据此推导如果延长生成会发生什么，也不把缺失动作重记为算错。

### P09．`finqa/MRO/2008/page_69.pdf-1`，R→I

来源：P09-C1、P09-C05。双方各 1 个返回 turn。

C1 文字列出 WTI 高价 145.29 与 Western Canadian Select 高价 114.95，直接完整封套提交 `subtract(145.29, 114.95)`；已有事件 `submitted:true`，R。没有预运行事件。

C05 文字列出相同数值并表示会计算差值，却没有任何调用封套或工具事件；终态 `no_tool_call`，I。

谨慎解释：该样本也说明 R 不必先有 `run_program`，原合同允许实际直接提交。真正不同的是是否产生了合法提交动作，而不是工具次数越多越好。

### P10．`finqa/UA/2009/page_50.pdf-2`，R→I

来源：P10-C1、P10-C05。双方各 2 个返回 turn。

C1 实际运行 `subtract(0.3, 1.2), divide(#0, 1.2)`，旧事件返回 `-0.75`；第二轮完整封套提交同一程序，R。

C05 第一轮也有完整运行封套，执行同一程序并得到 `-0.75`。第二轮虽写出 `Program: submit_program: subtract(0.3, 1.2), divide(#0, 1.2)`，但这是 prose，不是 `<tool_call>…</tool_call>`；保存的解析调用为空，没有提交事件。终态 `no_tool_call`，I。

谨慎解释：与 P01/P06 类似，这是已有成功执行之后未完成正式提交，但此次发生在 C05 端。不能把文本含有字符串 `submit_program` 当作工具确实执行，也不能把它修补后替换原结果。

### P11．`finqa/GS/2017/page_106.pdf-1`，R→I

来源：P11-C1、P11-C05。C1 2 个返回 turn，C05 1 个。

C1 第一轮完整封套运行 `subtract(35, 25)`，旧事件返回 `10.0`，第二轮完整封套提交同一程序，R。

C05 文字同样写出 35、25 及 `35 − 25 = 10`，称不需要额外表查找，随后未产生任何工具调用封套或事件。终态 `no_tool_call`，I。

谨慎解释：C05 原文字含算术结果，不等于按原 native 协议完成了提交。该对只能支持“保存输出中交付动作缺失”的描述，不能新增一条反事实正确结果。

### P12．`finqa/PNC/2013/page_62.pdf-1`，R→I

来源：P12-C1、P12-C05。C1 2 个返回 turn，C05 1 个。

C1 根据 2013 年 1,356 与 2012 年 2,220，完整封套运行 `subtract(1356, 2220)`，旧事件返回 `-864.0`；第二轮完整封套提交同一程序，R。

C05 文字列出同样的两年值，并说明按 2013 减 2012，但没有工具封套、执行或提交事件。终态 `no_tool_call`，I。

谨慎解释：本对有相同取数和运算方向的文字证据，仍不能据此把未实际交付的 C05 当作完整解答。没有观察到在本次阅读之外发生过新的执行或补答。

## 3. 仅限此固定样本的综合描述

这 12 对按照转移方向各取六对，是结果分层选择，不代表全部 seed137 任务或所有 invalid 的自然发生比例，更不能将样本中六增六减解释为整体净变化为零。

在实际读取的 12 个 invalid 侧中：

- 10 个没有最终提交封套：其中 7 个整轮无工具事件，3 个先成功 `run_program`，随后只有 prose、未完成提交。后三个是 P01-C1、P06-C1、P10-C05。
- 另 2 个已有合法 `submit_program`，但原生评价为不可执行：P02-C1 的重复 `table_sum`，P04-C1 的 `table_average`。这些不是 parser 漏接合法调用的例子。
- 26 个已有工具事件均标为 `is_error:false`。这不能推翻两个 `nonexecutable_submission`，因为提交动作回执与原生程序执行判定是不同阶段；这两例也没有预运行失败及纠错事件。
- 已阅读 12 个 R 侧均保存了实际提交：9 个先运行后提交，3 个直接提交。没有由本次阅读新增的成功、失败或工具事件。

P03 同时改变了取数/分母与交付，P02/P04 改变了程序构造；因此，即使不少样本的可见差异位于交付边界，也不应把全部 I↔R 转移等同于纯格式现象。相同文字数值、程序意向或内部方向一致性都不足以证明未完成提交的输出一定能答对。

本样本没有用于检验温度因果机制、抽象推理改善、总体协议退化或后续监督目标的有效性。若提出“提交动作相关监督可能值得研究”，它仅是待另行定义公平对照的假说，不是本报告确认的机制。

## 4. 24 侧原文来源与实际 SHA256

以下路径按同一个精确模板展开，避免重复省略长路径造成来源不明。`OLD` 是：

`/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v54_feedback_temperature_01/automatic_recovery_01`

每行完整路径为：

`OLD/evaluations/jobs/step894_dev883_greedy_seed137_{arm}_draw20260928/shards/step894_dev883_greedy/generation/episodes/{episode_id}/episode.json`

每一行均已实际打开、完整文件字节 SHA 已读取并与 packet 匹配；没有以只读 packet 引用代替原文件读取。

| 来源号 | arm | episode_id | 实际文件 SHA256 |
|---|---|---|---|
| P01-C1 | C1 | `48605fd749988c1b23d3c9b166c150d11720dafad93d9369d5abcd427cee8e9a` | `ae00df2933216efc5144f458c6c9de09b09f819e656c3f13c92ae397a6588047` |
| P01-C05 | C05 | `d3495fff8c29bf9e09ba4c810588af876fc1008c2a426a98c898422724982316` | `d84b2b1f3d94f20ae7431216bfb7bb58ddd9d3469dee8936d9ee6809152951d6` |
| P02-C1 | C1 | `600f01a74060846e15bbabeab3cb78233439821c4f2453e9d54ae728c252a737` | `095a0ea27c859f75b8e7131443222e87851e9968897788cf58ff02883f2d7ee3` |
| P02-C05 | C05 | `532adb0ee0c81a5bd6b1c5aa48522256d2db98233526a2bc26a1138fb45fa839` | `42e4d127d2ad86b245118c705d178903960ae33d9be8f4073e18fb1b0cd97ed6` |
| P03-C1 | C1 | `1f7b7f6ff8b37291c60e64f5c46359a5e11014282a34e29bc237a933f537aee3` | `7fc1587a153143b4d61402f74a4323d98271ce034fccc4f6d8f42d5732e3a656` |
| P03-C05 | C05 | `3fdcbf82e0b5afe0687229f1c441bfc5998c60c265d34327630519a9700acd2a` | `796d0c6edac33f4a90c7f54b445239a9db40eefab95a2a5c284a8728f8a5f4e6` |
| P04-C1 | C1 | `5f3347347a1259773a25fcedcf3cdabc08132fdc7a7bad4ca85903cf53a90bfb` | `72963c11c9b7eb931db2cded35062b5af620d04fb0cb931ee533c4383cd87152` |
| P04-C05 | C05 | `b026a6f1607ce33b1de1616c15343509f3ac61ae8515575b1164bf0ab5d0f7fb` | `0d005abff1c4fe9b8f3f2a9927fab18b6b092a51556db55fe3c173a2e48295c2` |
| P05-C1 | C1 | `ccf4f1acef5848391bbfe8f008f3ec2a38904a6cc042475a932f93f8747e7629` | `9ae55c849339d57a723a6c8a1cb7ab37e41d0f01082c53e408dadba3b8cfd758` |
| P05-C05 | C05 | `254cdacf5249ab580b5e089e552e7fac752ac70eae1f0141fb7e45ad06d58917` | `b1dc0f2a1338387a849ddf3df0bb347b819212bf4fcf7b7e93c27312ec8690d3` |
| P06-C1 | C1 | `cfb7cb2c9577f27861bcf3e65c3b409e522396fd98897c645a3774b9f16ef94e` | `5a37d5b826459590ae1294d6d02f70d15aaac74c5c14c4f35e3dc175bad6d513` |
| P06-C05 | C05 | `4babb1a6fc71e37bb1720e3ca9126903afc1fbdeadb590d561e1794cd88a54d4` | `7a1298bd23783294196d6ff56cfe9a0cee60d983395f74791f8ac13e00d5672e` |
| P07-C1 | C1 | `50f952be99b4c698bd6140f0b4cdeb7dd44eacd3e4f400fd8c0a2773922bfef8` | `710e0c72a3446e179369bf71372920dcda32a504822a205245df213471d1a0c7` |
| P07-C05 | C05 | `9a15fed439ec419b9b24de9777e768360ff7bc7afb2b30f4c7a5b41aff153a9c` | `eb64ee4e2ada991e9726d5c0ce77198e9aa08f7d2a6dd2c80dca52491961d7da` |
| P08-C1 | C1 | `6ce4b81500268aec3f32cd5ad297f4ca72b9dcc0a436a8d33e7c257abf8b671a` | `b2bf41432ea77344f4ed325d037d5cf9505014e659b38657a37297139fd7f671` |
| P08-C05 | C05 | `1e1477d3fe12315fc582d0053d0b4555c724d7dc826cc1cb7a02c0e75d46d16a` | `32ed22c1f3c93a551cf2945e3a86b4014b8ec068adc264be48a3084add7bcbd8` |
| P09-C1 | C1 | `5cd510bd537bc899403f9047716533c25cd81e4e57b1e63f2ed7411287e0f4ae` | `307fc334bfc85e6be022af2be7d9ec280c5301c36f1071f32bad0f11ab2b9b95` |
| P09-C05 | C05 | `f6abdb006ac5ebdc9cb66b0ecf8135872f3add64666c52ea727da2f326fa82f8` | `5a6648a56e1d118500f5d1d6cfcbcdac3e14b6dd0e6ca675bf260a63c3d71ae1` |
| P10-C1 | C1 | `29d9c21ca31358f4d4c384ab923f9159332c1798cf3c33651013a17ef7f90322` | `a8653ebad50b4b354e19565eea70bcfdb1f0e98645ef625a1c89a8fc0b994224` |
| P10-C05 | C05 | `eb52dec97e2fc8994b9886f2dd5fecbfc9743da4e61619c16848288e3c2554f8` | `f0584e7fb11ca1a4098db94582dec7c7d28eff0ed47553b673d84db41b4802dd` |
| P11-C1 | C1 | `82b71a09978d47362292481f2771337079387ec78dea556d2d4aca4ef34b5c65` | `eec8d805db2db12c628f41431c888133a0015e6124d58915f5849fd31430cc76` |
| P11-C05 | C05 | `0482ff656c70aa742c9b9e7e9e7db245937fa9bcdcefeb1f4ea189220561b672` | `00ab776e44fd49b5797a654f24c75630306807fd943d31c8c3b7fb63a4b26e71` |
| P12-C1 | C1 | `5e645164e6848c53f730ff57bab36329a8d0c0d06362f4ee7b743d74b91ab00e` | `92d2c51d62dcd1487953af79ebfefacb861c4a5e1431e625a45aa4dca1f423f5` |
| P12-C05 | C05 | `bba269b8fc71e946b5793af370a49fb5d942d72d6891bc07a19f718b72cd4177` | `719faee5d44ffb34600237d8c2d54d3d0168c538e6ad6666f9b2efcce131565e` |
