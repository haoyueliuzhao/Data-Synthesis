# 原固定总体的预算修订、续采与正式训练

## 授权与修订性质

用户在查看writer recovery因预算预留停止后，明确要求“提高预算，完成完整采集，进行正式训练”，随后要求“减少冗余校验，尽快实验”。本修订提高预算并完成原未结束slot；它不是未经修订的原预注册实验，也不把旧STOP报告改成PASS。旧批闭合与发布提交为 `ce53a4bcf0b6668d8978b30eb40d1db88f3de930`。

原任务总体、10240-slot登记及其freeze ID、A/B池、train/sealed角色、公开P2/neutral请求、32响应/工具上限、方法与财务语义规则保持原样。9968个finished原样继承，其中181个transport终态及5次usage_unknown所对应的失败也保留；不筛掉失败、重选题、只保留成功或重复请求已经完成的slot。

## 精确续采范围与预算

续采清单只由原终态确定：121个budget_aborted与151个not_run，共272个slot。已有404次公开响应均已结算、已知用量且成功返回deepseek-flash，无failed/sent/usage_unknown请求混入可重放前缀。它们只在本地重放原响应与工具执行，逐步维持同一上下文，不重新发送；旧budget fatal attempt保留在原报告及派生lineage中，不伪装成成功调用。剩余最多8300次新HTTP（272×32−404）。

原前两批合并上限由250000000提高到350000000 Token，共同钱包1000000000上限不变。减去首批1269703与恢复批保守扣239706046后，新第七用途上限109024251 Token。恢复批的5个未知请求继续扣578560，不因这次授权退费。新上限是实际结算与在途保守预留共同受限的硬额度，不保证所有剩余8300请求同时按每次最大上下文/输出耗尽；不得将其描述成数学最坏情形足额保证。

第七用途独立 `kernel_completion_*` 表、注册、fatal与finalization元数据；不提高旧用途SQL cap、不删除旧停止标记、不重新开放旧表。原六用途行、SQL及原元数据保持字节/逻辑快照一致，新用途只允许冻结272-slot白名单。新请求attempt从原前缀长度+1起计，账本只为新增请求扣费。沿用优先级单写者队列，HTTP仍128路、评分24 CPU并行。

## 双重来源与材料闭合

原 `freeze.json`、`registry.json` 与population保留原件；`completion_freeze.json`另行绑定预算授权、续采manifest、当前代码与父闭合证据。保留原registration身份不代表声称未修订预算。新generation report同时列原freeze与completion freeze，旧FAIL报告仍在父工件中。

9968个已结束session/qualification原件按原SHA复制到新材料目录；不重新做财务语义评估、不把旧qualification改写为新assessor。每个继承slot有精确的session ID、qualification ID及原assessor code ID绑定，编码包同时如实记录当前编码器代码和原资格来源。272个续接会话单独评分，原前缀与新增后缀分别依据原/新账本及实际请求响应receipt验证。所有原始transport原件仍由已推送的父publication完整封存，新目录记录其manifest身份，不再解包重封同一历史原件。

全10240个slot闭合前不开始材料编码。闭合后24个spawn CPU worker各自加载同一冻结tokenizer，将每个原包只写一次到磁盘，回传小型索引；不通过进程间传输重复巨大token数组。既定全任务支持与S≥60、质量移动≥5%的门仍必须通过，finished不等于合格或正确。未通过则只封存失败事实，不启动Student。

## 正式训练与运行安排

门PASS后材料封存与Student准备并行；封存不是额外训练门。Student沿用Qwen、LoRA、优化器、三个种子、400次Full更新、A三臂9次训练及开发选择、有条件B最多6次训练与既定900题评价，不使用工程检查状态。最多占用当时空闲的8张A100，不抢占其他任务。只有实际执行报告完成后才封存正式结果与明确批准的最终LoRA。

本次没有重新运行349项全套、106项旧预算控制、560个脚本控制或GPU工程检查。只运行新增预算、前缀/材料谱系、组合分母和并行编码等价的针对性控制。旧tokenizer真实检查与GPU训练路径保持原证据意义，不重新计作本次测量。正式采集产率、支持S、训练时长与效用均待真实记录；本文不预判成功。

输出为 `artifacts/qa_vnext_fixed_kernel_value/study_20260914_budget_completion`，实时状态在 `runtime/fixed_kernel_completion_20260914/progress.json`。独立终态与发布清单采用同级workflow/publication目录，精确Git暂存使用 `--sparse --force`，推送始终为普通非强制push。
