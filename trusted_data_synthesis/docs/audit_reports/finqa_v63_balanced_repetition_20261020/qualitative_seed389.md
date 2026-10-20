# V63旧批次固定样本逐例定性阅读：seed389

日期：2026年10月20日。状态：助手逐例定性阅读完成，**不是独立人类审计或新的科学验收**。

## 范围与证据口径

本记录只覆盖已经冻结的seed389十二对：C1→C05方向I→R六对、R→I六对；均为旧批次b0、step894、dev883 greedy、评价seed20260928。没有重新选样、扩样、读取其他seed的轨迹原文，未读取新b1评价结果，也没有运行模型、工具、parser、评分或bootstrap。

逐对阅读了packet中的双方完整 `raw_turns` 和 `existing_tool_events`，合计24条轨迹、76个原始模型turn、67个已发生工具事件；这些计数是阅读范围，不是新增科学调用。MRO长例首次显示被截断，随后按数组区间补齐全部32轮原文和32个工具事件，未将截断片段当作完整阅读。下文的I/R、停止原因和原native理由沿用封存值，不是本次重评分。

- 阅读包：`v63_balanced_feedback_repetition_01/diagnostics/invalid/batch0/reading_packet/record.json`，ID `ddd93457381ea6012664548c69eefd3a0d0a5b332e65dd36f3c9ac8f1e1066a8`。
- 固定选择：同级 `selection/record.json`，ID `8a123abcaf73fd725b6155a91c05683d064579f885c935bb396309e8e80a0e23`。
- 包中的 `manual_reading_completed=false` 是原生成时的状态，本记录不回写它。助手后续实际阅读通过本文件单独记载。
- 每对附双方原episode路径及packet保存的SHA256。这里没有重新散列全部原episode或宣称独立数值复现；路径/SHA用于定位被读取内容的原始来源。
- `raw_turns` 是模型当时生成的文字；其中“将提交”“已正确”等自述不是本助手对任务正确性的认可。工具事件中的 `submitted:true` 也不等于原native R。

## 十二对逐例观察

### 1. finqa/STT/2011/page_83.pdf-2：I→R

原native：C1=I、C05=R；模型turn数2/2、既有工具事件数1/2（均按C1/C05顺序）。停止原因为 `no_tool_call` / `final_answer`。无效侧原native理由：`missing_or_invalid_submission`。

实际原文与事件：双方第一轮原文相同，均实际调用 `run_program`：`subtract(99832, 81881), divide(#0, 81881)`，保存结果均为 `0.21923`。C1第二轮解释了这个结果并写出 “Submitting the program string completes the task.”，但整轮原文没有新的 `<tool_call>`，既有事件也没有 `submit_program`；其停止原因为 `no_tool_call`。C05第二轮则在完整封套内真实提交同一程序，事件保存 `submitted:true`。

有限解释：可核查差异位于成功试算后的实际提交行为，而不是本对首次执行程序或工具数值的变化。双方第一轮文字近似值与工具返回值并非完全相同，不能把C05的native R泛化为每句文字都经验证。没有将C1的文字意图补成一次未发生的提交。

- 选择digest：`1739904a67058335fc2b532089dd7558cc839fc0e691b8299f7aeac077b22c34`。
- C1原episode：`/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v54_feedback_temperature_01/automatic_recovery_01/evaluations/jobs/step894_dev883_greedy_seed389_C1_draw20260928/shards/step894_dev883_greedy/generation/episodes/9fa5c9f43ede413b715d4fbb5b9d11c46b20c361b15507b3d81a3cd09afeca73/episode.json`；SHA256：`1b850c59df843937a19ecd74d4c2e40236fd848c1a70b12db374963f5457c955`。
- C05原episode：`/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v54_feedback_temperature_01/automatic_recovery_01/evaluations/jobs/step894_dev883_greedy_seed389_C05_draw20260928/shards/step894_dev883_greedy/generation/episodes/63bac1e0e8a4db9bda57e6ae028b5cd452dc6ea2bc6fcc7366f58c2994a90fdf/episode.json`；SHA256：`f8ea552afd055ceeb04857d2e2e4af58c8234cd00606a1fa9920f6ac9cba40c0`。

### 2. finqa/BLK/2013/page_125.pdf-3：I→R

原native：C1=I、C05=R；模型turn数2/2、既有工具事件数1/2（均按C1/C05顺序）。停止原因为 `no_tool_call` / `final_answer`。无效侧原native理由：`missing_or_invalid_submission`。

实际原文与事件：双方都实际执行 `subtract(137, 133), divide(#0, 133)`，保存结果均为 `0.03008`。C1第二轮说 “Submitting the same program string is the appropriate final action.”，随后终止，原文没有调用封套，事件只有一次 `run_program`。C05第二轮除解释增长率外，还输出合法封套中的 `submit_program`，该事件保存提交成功。

有限解释：两个分支在本对使用相同程序和相同已发生试算结果，差异是是否把提交意图转为实际调用。不能据此称C1的原生invalid本来已经是正确提交，也不能由本例推断低温普遍改善提交。

- 选择digest：`39a1c1c291fe4226aa42ce7f0a8bebc6d8c2701fd2a15122815cbc42af602899`。
- C1原episode：`/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v54_feedback_temperature_01/automatic_recovery_01/evaluations/jobs/step894_dev883_greedy_seed389_C1_draw20260928/shards/step894_dev883_greedy/generation/episodes/558c3803668dccb71896746da173ebbe84e604a3cf48ddb7d5cb99319a65cf43/episode.json`；SHA256：`aab457e39ee7daaaaeb5c1b234c606d2653b2043130d36979d7d02d0151eaf33`。
- C05原episode：`/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v54_feedback_temperature_01/automatic_recovery_01/evaluations/jobs/step894_dev883_greedy_seed389_C05_draw20260928/shards/step894_dev883_greedy/generation/episodes/eca0eaf7deb378d21a37c8ab5e8419c686864772b850203de2ca9b3a37720bf7/episode.json`；SHA256：`27ba2dcb2c8965eb5bc9b1bf7ed6c5f66a60ddfb8ae988b9875f23bceca296a4`。

### 3. finqa/MRO/2009/page_56.pdf-3：I→R

原native：C1=I、C05=R；模型turn数32/2、既有工具事件数32/2（均按C1/C05顺序）。停止原因为 `max_steps` / `final_answer`。无效侧原native理由：`missing_or_invalid_submission`。

实际原文与事件：C1共32轮、32个工具事件。第一轮虽然文字列出2009的3.99和2007的6.86，却执行 `table_average(henry hub natural gas ( dollars per mcf ) ( a ), none), subtract(#0, 6.86), divide(#1, 6.86)`。全部32次 `run_program` 的已存返回都是 `ToolInputError: invalid linear FinQA program syntax`。后续原文反复声称要把行标签改为字符串字面量，但传入的程序没有发生相应变化；直到 `max_steps`，没有任何提交事件。32轮调用封套本身均被接纳。

有限解释：C05明确说不需要 `table_average`，直接执行 `subtract(3.99, 6.86), divide(#0, 6.86)`，已有工具返回 `-0.41837`，第二轮提交同一程序并得到原native R。本例同时呈现程序构造、错误后的修订路径和提交轨迹差异，不宜归结为单纯缺少调用封套。未重跑该错误程序，也未用额外步数构造反事实。

- 选择digest：`3e6e28a4f9d702a8be1d740ab5662b0e0086249c7cab07d3b2d63e6f436ee724`。
- C1原episode：`/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v54_feedback_temperature_01/automatic_recovery_01/evaluations/jobs/step894_dev883_greedy_seed389_C1_draw20260928/shards/step894_dev883_greedy/generation/episodes/ef4b0992cc598893969cd9b18d15d561ab3f099b34248a0f7cf4703cdcafaa6b/episode.json`；SHA256：`c15b5d9672bbfad94b7fb30d4ac49efadcd2e0ace38e67f91d10b4ca242de8ef`。
- C05原episode：`/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v54_feedback_temperature_01/automatic_recovery_01/evaluations/jobs/step894_dev883_greedy_seed389_C05_draw20260928/shards/step894_dev883_greedy/generation/episodes/607fb7d949206c1a21d995f92fc6a2f28df4ef4552bc7d63fbd31ec7d75a2f66/episode.json`；SHA256：`c769214ce84b0d5865459e1d33cda4a73507424b8ee5abe0050142c8702deab2`。

### 4. finqa/ETFC/2014/page_26.pdf-3：I→R

原native：C1=I、C05=R；模型turn数2/2、既有工具事件数1/2（均按C1/C05顺序）。停止原因为 `no_tool_call` / `final_answer`。无效侧原native理由：`missing_or_invalid_submission`。

实际原文与事件：双方实际运行 `divide(205.14, 137.81)`，返回均为 `1.48857`。C1第二轮的结尾是普通文本 `Program: divide(205.14, 137.81)` 和 `Submit: submit_program with that program string.`，没有 `<tool_call>`，因此既有事件只有运行、没有提交。C05则在第二轮真实调用 `submit_program`，参数仍为同一程序。

有限解释：自然语言出现工具名不等于发生该工具调用。这里观察到的变化是同一试算结果后的交付路径；不把文字中提到的 `submit_program` 当作已提交证据。

- 选择digest：`492d14521c521fb7d369e8fad9998aec699c44a3272146e5a7f799198de1d26a`。
- C1原episode：`/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v54_feedback_temperature_01/automatic_recovery_01/evaluations/jobs/step894_dev883_greedy_seed389_C1_draw20260928/shards/step894_dev883_greedy/generation/episodes/1df81dc0c94cb137a37b6b7b32d816a271144c18708033a3bc08ca23131aaf6d/episode.json`；SHA256：`af3ba163167dbec5c60e21fd044c5e72f2fdfbcf83cc02390ebe8afb1c5d6afc`。
- C05原episode：`/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v54_feedback_temperature_01/automatic_recovery_01/evaluations/jobs/step894_dev883_greedy_seed389_C05_draw20260928/shards/step894_dev883_greedy/generation/episodes/155b67c9809e658ebc5df764416276f94ac005e2819470c95749dff629778b94/episode.json`；SHA256：`2ce479da5fb8cd74f5a5dd268d7989af43aff036b6ed5874aafade8755025fd5`。

### 5. finqa/AON/2011/page_134.pdf-1：I→R

原native：C1=I、C05=R；模型turn数2/2、既有工具事件数1/2（均按C1/C05顺序）。停止原因为 `no_tool_call` / `final_answer`。无效侧原native理由：`missing_or_invalid_submission`。

实际原文与事件：双方第一轮原文相同，并都运行 `subtract(6817, 6423), divide(#0, 6423)`，返回 `0.06134`。C1第二轮只有普通文本 `Program: submit_program(subtract(6817, 6423), divide(#0, 6423))`，没有工具调用封套。C05第二轮虽然同样说明要提交，但额外具有实际的封套和JSON调用，既有事件确认提交了相同DSL程序。

有限解释：可见差异是“描述一种提交写法”与“实际发出原合同允许的提交调用”。没有修复C1文本，也没有重算修复后的准确率；这不是对parser漏接合法调用的证据。

- 选择digest：`4ab212a72298ec5b045abe2087cea877dd7c779f65a022dd20968b0b47d403d6`。
- C1原episode：`/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v54_feedback_temperature_01/automatic_recovery_01/evaluations/jobs/step894_dev883_greedy_seed389_C1_draw20260928/shards/step894_dev883_greedy/generation/episodes/f955d232ac97a7cfafa657d37a057bc44384513c486de811f53a74c4acc44a29/episode.json`；SHA256：`9ce939f17228e03edf849a2545ef33277ace7d6215891878d92b358e4e64fdb3`。
- C05原episode：`/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v54_feedback_temperature_01/automatic_recovery_01/evaluations/jobs/step894_dev883_greedy_seed389_C05_draw20260928/shards/step894_dev883_greedy/generation/episodes/dc8ba446987eb3738a3b07a7dab79a61b48e8feadec12dfcd058a16aef6a2326/episode.json`；SHA256：`286c5f1f9484c991aa83ca54b9523f0b57bb6323034639b060ba433d6d73f8be`。

### 6. finqa/BLK/2012/page_160.pdf-3：I→R

原native：C1=I、C05=R；模型turn数1/2、既有工具事件数0/2（均按C1/C05顺序）。停止原因为 `no_tool_call` / `final_answer`。无效侧原native理由：`missing_or_invalid_submission`。

实际原文与事件：C1仅一轮，文字给出 `226/349`，结尾写 “I will submit the program `divide(226, 349)`.”，但无调用封套，既有工具事件为空，按 `no_tool_call` 停止。C05第一轮实际运行该程序，保存结果 `0.64756`；第二轮实际提交 `divide(226, 349)`，原native为R。

有限解释：本例C1甚至没有实际试算，不能把其文字程序视为已经执行或提交。可以记录两侧提出相同算式而行动轨迹不同，但不将未发生执行的C1授予反事实正确分数。

- 选择digest：`51f6849d52b29deaf41d193e51bdfc4de994219f00cce14efe897109017312c3`。
- C1原episode：`/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v54_feedback_temperature_01/automatic_recovery_01/evaluations/jobs/step894_dev883_greedy_seed389_C1_draw20260928/shards/step894_dev883_greedy/generation/episodes/bc9408f9b4140caaed37a0293ea14be6f02a31099359639ba9172616434d908a/episode.json`；SHA256：`4c7b07660129ad52cc6d0f94574edfcf38f26871c9661896ba708020135c13c3`。
- C05原episode：`/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v54_feedback_temperature_01/automatic_recovery_01/evaluations/jobs/step894_dev883_greedy_seed389_C05_draw20260928/shards/step894_dev883_greedy/generation/episodes/8fb2fc65700ac43b4f7497955e5714cbaa6182a5c08d7d3f9ca4063598558098/episode.json`；SHA256：`885e54338617b2007c71260b72dacf30e52d630719391f2d287899bac9739b7a`。

### 7. finqa/APTV/2014/page_49.pdf-2：R→I

原native：C1=R、C05=I；模型turn数2/2、既有工具事件数2/1（均按C1/C05顺序）。停止原因为 `final_answer` / `no_tool_call`。无效侧原native理由：`missing_or_invalid_submission`。

实际原文与事件：C1实际运行并提交 `divide(350.82, 100.00), subtract(#0, const_1)`，保存试算结果 `2.5082`。C05运行的是 `subtract(350.82, 100), divide(#0, 100)`，其已存试算结果同样为 `2.5082`；第二轮却只有 “Execution confirms the arithmetic; submit the program string.” 等文字，没有调用封套或提交事件，随后 `no_tool_call`。

有限解释：两侧程序字符串不同，但已有运行结果相同；不能把R→I直接解释成算术结果退化。本对可观察到的是C05在试算后没有真正完成提交，和前面的若干I→R例形成双向现象。

- 选择digest：`05ab53659747059c95728c137931babdab62a0a86efee45ebc7c8b50cc0aa6e9`。
- C1原episode：`/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v54_feedback_temperature_01/automatic_recovery_01/evaluations/jobs/step894_dev883_greedy_seed389_C1_draw20260928/shards/step894_dev883_greedy/generation/episodes/716ff6a300b4f75fbc706da6dcfe0bd438ed14e1df9f3801aaeecb5f7aaff7c9/episode.json`；SHA256：`0487a60857e9ecf91e26b562b8a45f1adea5f9a1151edf6211d45b2138962d67`。
- C05原episode：`/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v54_feedback_temperature_01/automatic_recovery_01/evaluations/jobs/step894_dev883_greedy_seed389_C05_draw20260928/shards/step894_dev883_greedy/generation/episodes/18906e4d40a8f755fe16aafb55a291e2c108a19ba777d28e13885a62e3fda647/episode.json`；SHA256：`6114cd3b05451de8afb324f9dde1b590b8a2e393a0a8c7d00191aa1395223e79`。

### 8. finqa/OKE/2008/page_86.pdf-1：R→I

原native：C1=R、C05=I；模型turn数2/2、既有工具事件数2/1（均按C1/C05顺序）。停止原因为 `final_answer` / `no_tool_call`。无效侧原native理由：`missing_or_invalid_submission`。

实际原文与事件：C1和C05都实际执行 `subtract(258800, 25171)`，保存结果均为 `233629.0`。C1第二轮在合法封套中提交同一程序。C05第二轮仅留下 `Program: submit_program subtract(258800, 25171)` 普通文本，事件里没有提交，停止原因为 `no_tool_call`。

有限解释：本对没有已存工具数值差异；工具名和程序出现在散文中仍不是合法提交。这一观察不支持“C05在所有父点/所有题目都改善原生交付”的推广结论。

- 选择digest：`0611009bcca9bdae229c459a88cff1bf90aa30f1e99aefac0c4403e7f0ed9e86`。
- C1原episode：`/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v54_feedback_temperature_01/automatic_recovery_01/evaluations/jobs/step894_dev883_greedy_seed389_C1_draw20260928/shards/step894_dev883_greedy/generation/episodes/dcfee2699f144c76bbee029ada5af7f87c8d33cdaf46e1eab74c645716c762a3/episode.json`；SHA256：`abfb5a0cb2d07866fbd92f6c3ffd44f782f8c59a0be3b1db2bfd7394723750db`。
- C05原episode：`/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v54_feedback_temperature_01/automatic_recovery_01/evaluations/jobs/step894_dev883_greedy_seed389_C05_draw20260928/shards/step894_dev883_greedy/generation/episodes/7d0c682a26db6cee134a31eb007cf4bf93a2e206c95c0cff7d86eae23ea1fecd/episode.json`；SHA256：`88a83ee052c707088659f95a3be23d9b0c6c9c099766ff0272d1c71da6dcc50a`。

### 9. finqa/PM/2014/page_67.pdf-3：R→I

原native：C1=R、C05=I；模型turn数3/2、既有工具事件数3/2（均按C1/C05顺序）。停止原因为 `final_answer` / `final_answer`。无效侧原native理由：`nonexecutable_submission`。

实际原文与事件：双方第一步都实际运行 `divide(20ac750, 1029)`，已有工具返回均为 `ToolInputError: FinQA program did not execute to a finite number or yes/no`。C1随后把实际操作数改为 `750`，运行 `divide(750, 1029)` 得到 `0.72886`，第三轮提交该程序；原native R。C05第二轮虽然在文字中承认 `20ac750` 不是数值，却反转比值并直接提交 `divide(1029, 20ac750)`，保留了这个非数值片段。

有限解释：C05的 `submit_program` 封套和JSON确实被接纳，事件保存 `submitted:true`，但原native为 `nonexecutable_submission`，因此I不是“没有工具调用”。这是可见的错误后程序修订与操作数处理差异；不能将工具层提交接收成功等同于原生程序可执行或正确，也没有进一步执行/修复这个提交。

- 选择digest：`0879366cb5f664f306d5ad683b31535d654618adc26c88a7889253e86940613b`。
- C1原episode：`/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v54_feedback_temperature_01/automatic_recovery_01/evaluations/jobs/step894_dev883_greedy_seed389_C1_draw20260928/shards/step894_dev883_greedy/generation/episodes/55733c1777a71f57c2ca15d2e58709b00f063d8aeecc6174e795f5ca0414ad56/episode.json`；SHA256：`126441b2bce3952df7efdaffdd009982eab11e987c2c7e9b5648ecab45df9fd3`。
- C05原episode：`/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v54_feedback_temperature_01/automatic_recovery_01/evaluations/jobs/step894_dev883_greedy_seed389_C05_draw20260928/shards/step894_dev883_greedy/generation/episodes/640d4d63bf1895603b4c5640a90b34c7e58288c01534f3ce551f507061ee4673/episode.json`；SHA256：`e404094668712ad8fd6fe50c51bc20bde4e294372c78f0c1385a875727973845`。

### 10. finqa/SPGI/2015/page_57.pdf-1：R→I

原native：C1=R、C05=I；模型turn数2/2、既有工具事件数2/1（均按C1/C05顺序）。停止原因为 `final_answer` / `no_tool_call`。无效侧原native理由：`missing_or_invalid_submission`。

实际原文与事件：双方都运行 `subtract(2378, 144)`，返回 `2234.0`。C1随后真实提交相同程序。C05第二轮只写 `Program: submit_program subtract(2378, 144)`，无调用封套，既有工具事件仅运行一次，终止为 `no_tool_call`。

有限解释：C05在文字中称程序已确认正确，并不等于实际提交或native正确。本例的可见变化是最终调用缺失，不是已经发生的试算返回值变化。

- 选择digest：`095485a86d52f0de36ecdc5683e4fe7ff282ff44d8c56d0451540c2f532db0b6`。
- C1原episode：`/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v54_feedback_temperature_01/automatic_recovery_01/evaluations/jobs/step894_dev883_greedy_seed389_C1_draw20260928/shards/step894_dev883_greedy/generation/episodes/8c6b243e19ff646d9d9cd61abb66ab8f333c661a55640d952a9c3b08ab27cc07/episode.json`；SHA256：`c02961cf905396e4313ff3e8c16ae48ca202de6ae95473660e0c84c0f7b94a45`。
- C05原episode：`/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v54_feedback_temperature_01/automatic_recovery_01/evaluations/jobs/step894_dev883_greedy_seed389_C05_draw20260928/shards/step894_dev883_greedy/generation/episodes/73f797d25f3cb869d8e376e1ee9d418c32703681412d760354c222cba0a68ab6/episode.json`；SHA256：`230b4c88fcc4a8a504ce0bc1982b3f13af0178dcbaabf843e87dcb4ca1edea49`。

### 11. finqa/CME/2017/page_97.pdf-3：R→I

原native：C1=R、C05=I；模型turn数2/1、既有工具事件数2/1（均按C1/C05顺序）。停止原因为 `final_answer` / `final_answer`。无效侧原native理由：`missing_or_invalid_submission`。

实际原文与事件：C1运行 `add(3, 2)`，工具返回 `5.0`，第二轮提交该程序，原native R。值得保留的是，C1的自然语言同时出现“3和2共5”和 “matching the stated six directors” 的冲突，不能因native R就称其所有解释句正确。C05仅一轮，自称无需计算并把“six directors”当作答案，实际调用 `submit_program`，但 `program` 字段直接是字符串 `"6"`。

有限解释：C05存在完整封套和被接收的提交事件，`submitted:true`，原native仍为 `missing_or_invalid_submission`。本对同时涉及文字数字选择和程序表示差异，而非单纯漏掉调用标记；没有把字符串6改造成DSL再评分，也没有另读原财报来重判题义。

- 选择digest：`098354692968d1bb95e264138932244a383024d444851c0cf95e7d0a588f2291`。
- C1原episode：`/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v54_feedback_temperature_01/automatic_recovery_01/evaluations/jobs/step894_dev883_greedy_seed389_C1_draw20260928/shards/step894_dev883_greedy/generation/episodes/6d10a21c7f29f28c251c3c02e95313c0aaebffb041b3af6cbd7183e7d9c4ca27/episode.json`；SHA256：`070cf56a1dbf8e54a1ab159be449b325f82df1df83c2ec554585ed647b3bf157`。
- C05原episode：`/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v54_feedback_temperature_01/automatic_recovery_01/evaluations/jobs/step894_dev883_greedy_seed389_C05_draw20260928/shards/step894_dev883_greedy/generation/episodes/16682f7ef80c3ca712a4feedcebc85c93816f23155a859dd015b18af1741ab1f/episode.json`；SHA256：`8c9201f60ed0133d1e562ce379ba4260bc6833e777a4030414c82151364d0b93`。

### 12. finqa/VNO/2012/page_84.pdf-2：R→I

原native：C1=R、C05=I；模型turn数2/1、既有工具事件数2/0（均按C1/C05顺序）。停止原因为 `final_answer` / `no_tool_call`。无效侧原native理由：`missing_or_invalid_submission`。

实际原文与事件：C1运行 `subtract(109, 100)` 得到 `9.0`，第二轮提交该程序，原native R。C05只有一轮，在整段原始输出中反复写 `Program: subtract(109, 100)`、结果为9以及“Submitting the program”之类说明，却从未输出 `<tool_call>`，既有工具事件为空。

有限解释：该C05返回耗尽2048个生成token，`finish_reason=length`、`actual_EOS=false`，episode以 `no_tool_call` 结束。这里是一次生成内部的重复文本，不是MRO例的32次工具错误反馈循环。不能推断增加token或继续生成就一定会完成提交；本次没有延长输出或重试。

- 选择digest：`0e0a46bc1087e9be7572b675a4ed72e44bbcdaf7407c5dd04951ff64a0cb47da`。
- C1原episode：`/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v54_feedback_temperature_01/automatic_recovery_01/evaluations/jobs/step894_dev883_greedy_seed389_C1_draw20260928/shards/step894_dev883_greedy/generation/episodes/15c9ac4407625fd635fa477bae57ad0cbf08452ac5708b7bd8d57842872bbb6f/episode.json`；SHA256：`aed463311606a4b8ebec81fca1181ff07a1b72cd7686501a9ed583eb98d96066`。
- C05原episode：`/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v54_feedback_temperature_01/automatic_recovery_01/evaluations/jobs/step894_dev883_greedy_seed389_C05_draw20260928/shards/step894_dev883_greedy/generation/episodes/4ada635c65956169e86ceb41cd23cd585767b6bcb0f8d85d97029c78aa361cc0/episode.json`；SHA256：`f6990777063f74641291b48412ea79843a9b73f80f1340ab756d7cfd3fd34327`。

## 有限总体结论

1. 这十二个固定转移样本中，九个无效侧缺少实际调用封套：I→R方向五例、R→I方向四例。其中七例已经成功运行程序，但未真正提交；另两例（BLK/2012的C1与VNO/2012的C05）完全没有工具事件。这是所选样本的描述，不是对全883题或全部invalid原因比例的估计。
2. 提交缺失同时出现在C1和C05：同一程序/同一试算返回后，一侧继续产生真实提交，另一侧只描述提交。不能据此认定低温单向改善或单向损害协议执行。
3. 其余三个无效侧不能统称为缺封套：MRO的32次调用被接纳但程序持续报错且最终未提交；PM的提交被接收但程序不可执行；CME直接提交裸数字字符串而原native无效。程序构造、操作数处理、错误后修订及最终提交是否发生，必须分开描述。
4. C1的PM轨迹实际从一次工具错误恢复至正确提交；C1的MRO则重复同一报错程序32次。这说明“存在工具错误”本身不足以决定最终I/R，不能把所有错误恢复笼统归为同一种原因。
5. VNO的单次length终止与MRO的max_steps终止不同；没有证据支持通过增加额度、修复文本或追加调用获得反事实准确率。
6. 这批样本按已知I↔R转移分层选择，旧结果此前已读过，属于事后解释，不是盲化、随机总体估计或独立人类审计。六正六负是选样合同，不代表温度效应平衡或统计等效。
7. 本次阅读不证明“推理改善而格式退化”等因果机制，不反推C/gJ或监督系数的实际梯度贡献；不改变原主面板、旧promotion、新b1实验预算或后续判据。

## 操作边界

本次新增内容只有本Markdown阅读记录。原reading packet、selection、episode、工具事件、原native指标和所有历史失败记录均不改写。没有修复后重评分、工具重执行、模型调用、新采样或进一步扩充定性样本。

