# V63：旧批次 seed251 固定12对轨迹的助手逐例阅读

阅读日期：2026-10-20。对象是已经完成的反馈批次 `b=0`、`step894_dev883_greedy`、seed251 的 C1→C05 转移，不是正在运行的 V63 `b=1` 新结果。

本记录由助手逐对阅读形成，不是独立人类审计。严格沿用既定12对：6对 I→R、6对 R→I，没有重新选择、替换或扩展样本。已完整阅读这24条轨迹在封存阅读包中的全部 `raw_turns` 和 `existing_tool_events`，共36个原始响应、24个既有工具事件；没有以自动类别摘要代替逐例阅读，也没有在输出截断后宣称读完。

未执行模型、工具程序、parser 重放、修复或重评分，未读取其他 seed 的轨迹。下文的 I/R 和工具返回数值来自既有记录，不是本次独立重算。对原文中财报证据的引用，仅描述模型当时写了什么；本次没有再核验完整财报或私有答案。也没有重新读取原 episode 的全部 token 数组。

## 来源与阅读边界

- [固定选择记录](../../../artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v63_balanced_feedback_repetition_01/diagnostics/invalid/batch0/selection/record.json)：ID `8a123abcaf73fd725b6155a91c05683d064579f885c935bb396309e8e80a0e23`。
- [封存阅读包](../../../artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v63_balanced_feedback_repetition_01/diagnostics/invalid/batch0/reading_packet/record.json)：ID `ddd93457381ea6012664548c69eefd3a0d0a5b332e65dd36f3c9ac8f1e1066a8`，其 `selection_id` 与上述选择记录一致。
- 规则 ID：`8a7d13db71aa6e67af033ec2defbd1189b6cfae68680fa33f3344aa284ac1042`。

每侧来源 SHA-256 以下直接沿用阅读包的 `original_episode.sha256`，不是宣称本次又重哈希了原 episode。精确原路径可由文末的共同路径模板与逐对 `episode_key` 复原。原 packet/selection 的 `manual_reading_completed=false` 等历史字段不回写；本文件是独立追加的阅读说明。

I 表示原生无效，R 表示原生正确。本组 I 侧的原生原因均为 `missing_or_invalid_submission`，停止原因为 `no_tool_call`；R 侧均已实际调用 `submit_program`，停止原因为 `final_answer`。两类示例的 `saved_final_answer` 都可以是 `null`，因此不能用这个文本字段代替原程序提交回执判断有无有效提交。

## 1. `finqa/PM/2015/page_85.pdf-4`：I→R

选择 digest：`038520a7e97681abe2ff97f4d0c109cdf42ff1abd202a107a6055384b9155c2c`。

C1：1轮、0个工具事件。原文已引用2015年888与2014年120，并明确拟计算前者减后者，但整轮只有 R/U/Q 文字，没有 `<tool_call>` 封套；既有终态为 I、类别 A。它没有实际运行或提交程序，不能把文字中的计算意图算作已完成答案。

C05：2轮、2个工具事件。第一轮以完整封套调用 `run_program`，程序为 `subtract(888, 120)`，既有返回为 `768.0`、`is_error=false`。第二轮以完整封套对相同程序调用 `submit_program`，回执为 `submitted=true`，原生为 R。

有限解释：双方可见文字使用相同两个数值和减法方向，主要可见差别是是否真正进入运行与提交步骤。这不单独证明低温新增了求解能力，也不赋予未提交的 C1 一个反事实正确分。

来源绑定：

- C1 `episode_key=d4a9b38741b074c03d1eb00dacc89635a579555a1625b4f135006552288aea19`；SHA-256 `7ff326072c7ea6bdaa26ea5b09cf4b753eeadac92266b5a59293883045e4cabb`。
- C05 `episode_key=c62b1a28a2c975d295bab3af5d4134b0bdd6aefee6ae3f1ebdc5342c7048c8d8`；SHA-256 `c3e3dfb5136eab6e7d61f56b639c51b23bcbe384ceb06e699ccc1094827d468b`。

## 2. `finqa/ABMD/2004/page_26.pdf-4`：I→R

选择 digest：`047e3574e786467061954ad3187df6732506902acfb7f69b4b7be25cd2421265`。

C1：1轮、0个工具事件。文字列出2007年769和合计4578，说明拟计算 `769 / 4578`，但没有工具封套，随后以 I 结束。

C05：2轮、2个工具事件。先运行 `divide(769, 4578)`，已保存工具返回为 `0.16798`；第二轮文字解释为约16.8%，随后实际提交同一程序。运行与提交事件均无错误，原生为 R。

有限解释：可见操作数与比例定义相近，C05 增加了实际执行及提交。不能把 C1 的自然语言比值意图直接计为可执行答案；也没有证据把此对转移归因于百分数表示或奖励规则变化。

来源绑定：

- C1 `episode_key=19c601e2f609650b48585c2b1197000e002e4da005aa649189cedfd1e9ea4a3b`；SHA-256 `8c14460208f117d6d198fd0ecc52fa93e0c5448948c32b0ca7be8f4888792419`。
- C05 `episode_key=74708e54b93f8c4c2ae4b5c88a8cc5776337b05e3c3c125e95e37604d964d395`；SHA-256 `ece15b6a70c2b77e42c8c316daeb581ff801170f6ffc1bce7c131942cc3e518c`。

## 3. `finqa/TSCO/2017/page_31.pdf-1`：I→R

选择 digest：`069cf91cd1db885866ae50cfa25598217e2c96b8effd17643870847cb95042e2`。

C1：2轮、1个工具事件。第一轮已合法运行 `subtract(174.14, 100), divide(#0, 100)`，返回 `0.7414`，没有执行错误。第二轮解释74.14%并写出“submit the predicted program string”的意图，但没有任何工具封套；这一轮没有实际 `submit_program`，原生最终仍为 I。

C05：2轮、2个工具事件。先运行 `subtract(174.14, 100.00), divide(#0, 100.00)`，既有返回同为 `0.7414`；第二轮合法提交该程序，原生为 R。

有限解释：这是较清楚的“已获得工具结果，但末轮未提交”对照。两侧实际执行返回相同，不需要通过重新执行才能看见这一点；它支持把末轮交付完成与中间程序执行区分开，而不是把整个 I→R 都归为推理改善。

来源绑定：

- C1 `episode_key=d9701d53a17c4cc9ef322d6a197f8d5a781addfe3f575c7620ed39b7d5821df3`；SHA-256 `e8933823b1c29836e5d281d4f2c1d4492afaa39e04fd5cd9b5b562e6d2101f80`。
- C05 `episode_key=dd357d76f2bf605d5686f4c87df34451b0ce6446bb509b0655a53b17ab4e51c3`；SHA-256 `cad6131d99c88d45ff3bf7a9c6320d7cb75d4cd5fa36b1348420879a22e71a04`。

## 4. `finqa/SPGI/2015/page_57.pdf-1`：I→R

选择 digest：`0aaf393168ee90db1e44a3df204bc55de0b13442951eca46cc0afe9baebbeaa6`。

C1：1轮、0个工具事件。文字列出2378减144并写出2234，另以普通文本写了 `Program: subtract(2378, 144)`，还表示将执行确认；但没有工具封套，实际未执行、未提交，原生为 I。

C05：1轮、1个工具事件。其文字也使用2378与144，随后在完整封套内直接调用 `submit_program` 提交 `subtract(2378, 144)`，已保存 `submitted=true`，原生为 R。这里没有先行 `run_program` 事件。

有限解释：区别不是“有没有写出程序字符串”，而是是否按原接口实际提交。本例也显示先调用 `run_program` 不是所有 R 侧的必要轨迹；不能把“多一次工具执行”概括为本组统一机制。

来源绑定：

- C1 `episode_key=f8f15728e95759a5194b0066afc04c7010f68d0a0f940e5dab0705a9e8a4a15f`；SHA-256 `fbf4dfec1b91fde59bdc1f6a4bba69e78d9d038f638a2588093a5eb9aabb5251`。
- C05 `episode_key=cbb1974142941ba4399a7db66803bbf3816615aca356343c59d004265e9e72c6`；SHA-256 `ccfb2fc41a1ea670955e371d9c12ba4f8ba69242a08fb65f2c28edec7dde8db1`。

## 5. `finqa/PM/2015/page_85.pdf-2`：I→R

选择 digest：`124a5e34189c36044d5bae5b3cb2dbd0d37bc2103c1c14d3bc709daca23c9591`。

C1：1轮、0个工具事件。文字使用2015年28.5与2014年29.5，说明以2015年减2014年求债务变化，但没有生成工具封套，原生为 I。

C05：2轮、2个工具事件。第一轮合法运行 `subtract(28.5, 29.5)`，既有返回为 `-1.0`；第二轮解释为减少1.0，并实际提交同一程序，原生为 R。

有限解释：两侧可见数值和减法方向一致，差别落在实际执行与提交是否完成。此题与第1对来自同一份 PM/2015 报告，不能把它们当作两个独立来源来放大证据。

来源绑定：

- C1 `episode_key=a40316e222011715cb4f3f75c8571db9cbb5ee7a0e3dc5392cdc3bad56ca63e8`；SHA-256 `4b543717b9010fa80ceb609e2da328d55f8d751fceaf00fba099851e01e8f197`。
- C05 `episode_key=33fcb78cfca3a6faf67a16507c80372e9fd6f175bd5394e227b1d3b3b7c4d09a`；SHA-256 `30dd56e5588cafab75b15ee8effffa3afce1915620fbd82006d0c76ef0879264`。

## 6. `finqa/LMT/2006/page_90.pdf-1`：I→R

选择 digest：`1ae34bc7c04245f767cab4b9c3cd5f1d00e668c7dc0cc710295d539ca08da1bb`。

C1：1轮、0个工具事件。文字已把11亿美元换成1100百万美元，并说明计算 `288 / 1100`，但没有工具封套，原生为 I。

C05：1轮、1个工具事件。文字同样使用288和1100，并自行写出约26.18%的说明，随后实际提交 `divide(288, 1100)`，提交回执无错误，原生为 R。这里的比例小数是模型文字，不是一次 `run_program` 返回；本侧只有提交事件。

有限解释：没有观察到单位换算方向在两侧发生改变；可核实变化是程序提交完成。本次不把文字中的数值说明冒充额外工具核验，也不推断 C1 若补提交会得到何种分数。

来源绑定：

- C1 `episode_key=b317c4f774c9a7d7cae5dbd62ff59d794d469726884ad6c9d79dd9a75a553819`；SHA-256 `db23961f70a93c01bfc0dc0d2ff0cf315d2179bcae76178dd6e7ff7ca9f8e79e`。
- C05 `episode_key=618ae57e00d9f7dc73409e6af62ea2ea6ff3cbd533b7d86e5af6d559d1193453`；SHA-256 `40a9b9dd62c81b2e06f6cd50b1f1c66cef5d20a14ff5bf2e4ccaddf72e7b7e40`。

## 7. `finqa/ETR/2008/page_355.pdf-2`：R→I

选择 digest：`050f7ba14bfe271bdaf6e8ffced8db77ac6204299bc267568b4ebc18e2819bcd`。

C1：2轮、2个工具事件。文字用2008/2007净收入之差21.7与 rider revenue 3.9说明比例，实际运行 `divide(3.9, 21.7)`，已保存返回 `0.17972`，第二轮实际提交，原生为 R。

C05：1轮、0个工具事件。文字给出相同收入数值、21.7的差和3.9的分子，并明确写出 `Program: divide(3.9, 21.7)`，表示将运行后提交；但整轮没有工具封套，原生为 I。

有限解释：这是与前面 I→R 相反的交付变化。不能因为候选文字包含同样的表达式，就把它视作已经执行或提交；也不能只凭该反向例子断言低温普遍损伤数值推理。

来源绑定：

- C1 `episode_key=ba8b47b7277ac038a0c5c5844b1e57f9d4c33390852c94df74bfb23ee92d31f4`；SHA-256 `79d0c7ec9391a4aff0e415b2760930df1484a410942a12a6524d3bd2ca2d66cd`。
- C05 `episode_key=71b6206a7182ac55f8fa18ed5663859b1ff035375890ec2f414b89b80003e6ff`；SHA-256 `7c9307377a98384c8e383bc25a549056cb37cfe7fcd48147e2758702cca1c5d1`。

## 8. `finqa/APD/2016/page_96.pdf-1`：R→I

选择 digest：`14f78f5f562e0b36c526c4b1d181d131c8f5c3b797a602c31a2f80bf6523664e`。

C1：2轮、2个工具事件。运行并随后提交 `add(121.1, 97.5), add(#0, 132.4), divide(#1, const_3)`；既有运行结果为 `117.0`，两个事件均无错误，原生为 R。

C05：1轮、0个工具事件。文字也拟求三年利息支付均值，随后出现三个 `<tool_call>` 开标记、但只有末尾一个 `</tool_call>` 闭标记；其中第一份 JSON 使用与 C1 相同的 `const_3` 程序，后面又出现一份使用字面量 `3` 的提交 JSON。没有任何工具事件实际发生，已有首拒绝/终态类别为 `E_missing_closing_envelope`，原生为 I。

有限解释：这是封套不配对，而不是整个文本完全没有闭标记。两份提交内容并存，不能擅自选择其中之一修复后算分。包内既有摘要记录本轮以实际 EOS/`stop` 结束；本次没有把它归因为 token 上限截断。可见协议结构失败并不等于已经证明训练温度导致了该失败。

来源绑定：

- C1 `episode_key=37a169026ca36d6c3d80072b831004d7ba5d1910456ce41d9f3d14ddc7ec671b`；SHA-256 `9f1561519cf3a1c9bf53731a5c3c2309673f77a0ab2850f92007eaa66baa1b98`。
- C05 `episode_key=f463e4e2764b1cd2b4bece43f69f2316b7f1cca3f6f8aed9a46c29a72ac03659`；SHA-256 `61f20e5ad02b3b2ea6f39af7b8d817a760ff01953b0e962396eed0496c64c9bd`。

## 9. `finqa/AON/2014/page_47.pdf-4`：R→I

选择 digest：`1764124a7c3014e887e77d29f4eb8b7d544b8d481f34e5f166b14fb7f6353c3d`。

C1：2轮、2个工具事件。将4264视为35%的收入份额，实际运行 `divide(4264, 0.35)`，已保存返回为 `12182.85714`，随后实际提交，原生为 R。

C05：1轮、0个工具事件。文字同样使用4264与35%，以普通文本写出 `multiply(4264, const_100), divide(#0, 35)`，但没有工具封套；它另外自称 `(4264 × 100) / 35 = 12,177.14286`，这一文字数值与 C1 已保存的同一比例问题的工具返回不同。原生为 I。

有限解释：此例不宜笼统称为“只有格式差异”：候选还存在可见的数值陈述不一致。候选程序没有实际执行回执，本次不判断补执行、补封套或选择某份表示后的正确性，不创建反事实准确率。

来源绑定：

- C1 `episode_key=5ca08571ac500c9078baa4310a95f1105319561c26ca7fd0a31a2b059d3fbec2`；SHA-256 `d9f7d4985cc1f04fde72a7018fea98ea5d436a2bb557300336a01615ff285a0f`。
- C05 `episode_key=45edd1b462719a6bfab8440097e74c7f84c1be7c1e514452cdcbba1992c523ec`；SHA-256 `cce3559761194d3e939e8a971300ada5a8430a8e1f390501ccc23114cc47e2de`。

## 10. `finqa/TROW/2010/page_22.pdf-2`：R→I

选择 digest：`1c84cf885f340d85a8cc770b79797a0851bc2fd604fa030de2ff1e094c52a873`。

C1：2轮、2个工具事件。围绕2.4亿美元回购约500万股，实际运行 `divide(240.0, 5.0)`，既有返回 `48.0`，随后实际提交，原生为 R。

C05：1轮、0个工具事件。文字同样引用240.0与5.0，并直接写出 `240.0 / 5.0 = 48.0`，但没有工具封套，原生为 I。

有限解释：候选自然语言中的数值与 C1 工具回执相同，但这不能替代原合同要求的程序提交。该对说明“出现一致数值陈述”与“原生交付成功”不是同一个测量对象，不支持为候选追加正确分。

来源绑定：

- C1 `episode_key=f3bdaef24f05cd2191fa6f681d0d9c82412281a1eb6ec06049e949dd339af2bd`；SHA-256 `9c5bc9dc54f8dc587e92405a326b6f7e1b244e9e4ad3f27bc50901f2960d56e5`。
- C05 `episode_key=bdec446116e8ae49f14fbe3330efb06d98d8f476c6641406246d4a362433e1ec`；SHA-256 `ad56bad170b46582409e0661d2bf8dd896d2284f6464813d58c33251a7d2921b`。

## 11. `finqa/UPS/2006/page_32.pdf-1`：R→I

选择 digest：`3569453de1690f32d6896c57ae0987d538312f35d1921e14762686697864f300`。

C1：2轮、2个工具事件。先运行 `divide(148.92, 100), subtract(#0, const_1)`，已保存返回为 `0.4892`，再合法提交，原生为 R。

C05：2轮、1个工具事件。第一轮合法运行另一种写法 `subtract(148.92, 100.00), divide(#0, 100.00)`，已保存返回同为 `0.4892`。第二轮解释48.92%并称将提交，但只输出 R/U/Q 文字，没有 `submit_program` 封套，原生最终为 I。

有限解释：这与第3对呈反方向，但两对都清楚区分了中间执行成功和最终提交成功。本对两侧程序文本并非逐字相同，现有工具返回却相同；没有理由把候选的 I 简单归为计算结果错误，也不能据此给它补提交后的分数。

来源绑定：

- C1 `episode_key=9707b9b094c3e080e2a48dad55ee2d1b37f272efc765e3d2a788ff28b26ccb6b`；SHA-256 `207b4cacfef621524c2bf78949c240241ca46f5096818565ff88c3e580eb39e1`。
- C05 `episode_key=2f555275c7c88cff59ee01370dfac8781ce1502a39433cf6fb1893f7901b798b`；SHA-256 `48d6b6115f9272ab66a374bcb0199ccb00cdcc649655de27c66eceff4ff1952a`。

## 12. `finqa/ABMD/2007/page_52.pdf-1`：R→I

选择 digest：`8187267e8c48162ca7988cee95326ff3d345d133d4f3bca08f4ec9eb59d496e1`。

C1：2轮、2个工具事件。将45.1百万美元购买价与至多11.2百万美元的或有支付相加，运行 `add(45.1, 11.2)`，已保存返回为 `56.3`，随后实际提交，原生为 R。

C05：1轮、0个工具事件。文字最终仍选择45.1与11.2，并以普通文本写出 `Program: add(45.1, 11.2)`；另有关于“stated”与“approximate”数值表述的疑虑及确认后再提交的计划，但没有工具封套，原生为 I。

有限解释：在可见文字里，疑虑没有导致它换用另一组操作数；实际失败表现为没有完成原生提交。不能根据这段疑虑推断它是停止的因果原因，也不能把未发生的下一步确认或提交补进轨迹。

来源绑定：

- C1 `episode_key=a6be2c6938cab3230fb703fa5dd31fe35d2af2b8ea9af495075a72fee2b83d41`；SHA-256 `6430fdfe4c03d8ec4922185aaeddae7aacac6d1585ecd6d8a59ca8ffe3737ab8`。
- C05 `episode_key=769faca42af1042a3c9e9c8747a49d429d52c23d67fef54070a0228df175d0af`；SHA-256 `051c7eae8cbf5dc5fba7636409dc1a84a1b96af45fa88f991f6ccbeacb11707b`。

## 本固定样本能够支持的有限结论

1. 12个 I 侧中，11个终止响应没有开封套，另1个为 APD 的重复开封套/闭合不足。10条无效轨迹在第一轮结束；TSCO 的 C1 与 UPS 的 C05 则是在一次成功运行后，第二轮未真正提交。可见失败不只发生在“首次生成工具调用”这一环节。
2. 12个 R 侧全部有实际 `submit_program` 回执，其中10个先运行再提交，SPGI 与 LMT 两个直接提交。所有已发生的24个工具事件均记录 `is_error=false`；本样本没有显示工具执行报错是这些 I/R 转移的近端原因。
3. 缺少实际提交在两个方向都有实例。很多配对共享操作数或可见求解思路，但 AON 还出现候选文字数值与既有工具返回不一致。因此，既不能把 I→R 全称为推理改善，也不能把 R→I 全称为纯格式损伤。
4. 6对与6对是预设分层配额，不是 seed251 两种转移的总体频率；不能据此推断总体净收益为零。样本来自已见结果，且含同报告任务，不构成新的独立验证、盲化分析或总体比例估计。
5. 本次没有改变 parser、奖励、监督目标或输出预算；没有修复后准确率、继续生成后的反事实准确率，也不据此自动开展新算法试验。是否存在稳定温度收益，应由另外登记的完整新批次比较回答。

## 精确原 episode 路径模板

共同根为：

```text
/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/
finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/
v54_feedback_temperature_01/automatic_recovery_01/evaluations/jobs/
```

将上述三行路径连续连接，再接以下对应分支后缀，将 `{episode_key}` 替换为逐对列出的值，即得到阅读包绑定的精确原文件：

```text
C1:  step894_dev883_greedy_seed251_C1_draw20260928/shards/step894_dev883_greedy/generation/episodes/{episode_key}/episode.json
C05: step894_dev883_greedy_seed251_C05_draw20260928/shards/step894_dev883_greedy/generation/episodes/{episode_key}/episode.json
```

本说明只追加到文档树，没有修改该模板指向的任何原 episode、选择记录、阅读包、规则或评分记录。
