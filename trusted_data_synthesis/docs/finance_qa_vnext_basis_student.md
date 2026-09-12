# 固定真实材料上的三臂分布优化与Student执行闭环

## 1. 本轮目标与当前证据边界

依据2026-09-12新审计继续原实验，不新增小型效果试验。审计附件SHA-256为
`5d972ec199c2a2cacdc816a53b2fd8da606df1a843a3375dc7122ecfc22902d4`。
附件提到的独立Markdown/训练参考ZIP并未随本条消息提供，本实现依据已贴出的完整规范和
仓库既有接口自行接线；不声称运行了审计方的18项测试或使用了其未取得的ZIP。

本轮开发起点为发布提交`0b14b68c240fb197eff7cb0a9d71faee6dc04567`。
先在独立工作树`/tmp/data-synthesis-student-LTYRFR`开发，新包为
`trusted_synthesis.experiments.finance_qa_vnext_basis_student`。
旧采集提示、来源、期间、资格、目录、三用途预算及旧控制文件不改动；只新增后继实现。
900题受保护表述按`PASS_AS_SCOPED`收口，不重发改写、不提高接受率、不重评原70脚本。

本轮开发过程中，原24,640会话仍在运行。一个只读事务快照为
2026-09-12 15:33:25.725321 UTC：完成2,566、登记待执行22,066、运行8；
Teacher请求12,307 settled、8 sent、3 usage_unknown，全局停止标记为空。
该时点保守共同扣账为历史221,538＋UNP10,819＋Teacher40,266,123＋评测651,959
＝41,150,439，剩余958,849,561。未知请求按原账本保留扣账；这不是实时永恒余额。
没有从这2,566个排序前缀中计算方法产率、选择共同总体或改变实验设计。

当前实现完成与实际运行完成必须分开：CPU接线控制不等于Qwen训练，
后台等待入口已启动也不等于最终采集、物化、180–200共同任务或Student报告已经存在。
实际状态以原采集最终报告、材料manifest和本阶段运行报告为准。

## 2. 冻结父链与不可重开的阶段

训练候选保持255题：53 stock、54 annual、48公司定义、100控制；参考供给上限200不等于
实际共同可训练N。科学任务数保持900，开发180、确认720，不把表述版本计成新增科学任务。
后继统一表述manifest固定为
`manifest:f29dac61b36396baffd60916bf3b2bdca461a849f0e11bb2d519d54127d2c856`。
332真实改写、542未变化、26 fallback的最终公共字节不再选择或替换。

原固定A/B目录为`artifacts/qa_vnext_readiness_revision/fixed_AB_20260912`。
新代码没有再次调用collect的路径。监看只通过只读SQLite事务观察状态和三用途扣账，
不会构造新预算账本、修改registration或从中间财务/方法评分形成可训练总体。
Teacher仍是原32响应/32工具、8并发等配置；Student新配置不会回写Teacher。

只有原manifest存在、原报告为`COMPLETE_FIXED_COLLECTION`、报告全部计数24,640且
原registration全部finished、无study_fatal时才继续。单独完成计数够24,640也不算闭合。
有全局停止但尚未封存时，状态是`COLLECTION_STOPPING`，继续等原进程保存终局，
而不是重开采集。普通运输失败可以是合法会话终态，不要求全部财务有效。

## 3. 一次真实原包物化与实际共同总体

闭合后调用原`finance_qa_vnext_eval_surface.stage.materialize`，不另造第二套消费者。
该入口重核原采集manifest、全部注册分母、请求/收据、财务资格、细类和原始排序，
以原真实响应一次CPU tokenizer物化；24,576上限、原指导前缀、原完整历史不截断。
已存在但未完成的物化目录不会被覆盖或悄悄重跑。

每个池/任务/实际方法按原注册次序取前10个合格可消费包：8训练、2封存。
不按长度、NLL、文字风格或细类分数排序。三个双依据子组和控制的共同就绪数决定
`k=min(40,r1,r2,r3,floor(rc/2))`；k<36则接受输入终局，不补采、不降低配比。
否则N=5k，允许180/185/190/195/200。

新`train.validate_materials`检查实际manifest内容身份、源collection引用、全部层、
8+2原顺序、每个package SHA/内容ID/原row哈希/target mask/真实整包分母，
并按池计算实际训练Token。封存包只做表示完整性验证，不计算封存NLL或用来选择方向。
实际每池预算在首个Student前写入freeze：

* target预算＝10×该池所选训练整包target tokens之和。
* sequence预算＝10×该池所选训练原响应完整input长度之和。

不使用评测改写651,959 Token、旧脚本Token或历史小实验Token代替这些实际量。
A/B是同一共同任务的两套独立轨迹材料，不是两倍独立任务。

## 4. 五题64包内层训练

复用原`materials.update_examples`与`design.task_batches`。每次任务调度恰含三个不同
双依据子组各一题、控制两题，合计64个原训练包。方法质量保持：alpha0的movement为1/2、
plus为2/3、minus为1/3；所有臂共用同池物理材料、原包/行顺序以及配对初始化。

每个target token系数是`alpha(method|task)/(40*whole_package_target_tokens)`，
控制是`1/(40L)`。已包含五题均值、八包均值和整包Token均值；不再除64、微批、N或总Token。
每个更新先全部检查输入，再zero_grad一次，逐原响应完整history forward/backward，
因果位置t使用t-1 logits，64包全部完成后clip一次、optimizer.step一次。
任何非有限loss/梯度/优化器状态或缺包，在step前拒绝；途中失败保留已发生事件。

| 项目 | 新运行固定配置 |
| --- | --- |
| 模型 | 已有本地Qwen2.5-7B-Instruct，实际四分片/配置/软件内容绑定，无下载 |
| 基础权重 | BF16，冻结 |
| LoRA | 全部q/v，FP32，rank8、alpha16、dropout0.05 |
| AdamW | lr1e-4，betas0.9/0.999，eps1e-8，weight decay0 |
| 梯度 | 完整五题累计后范数裁剪1，无额外平均 |
| 调度 | seeds11/29/47；十遍；N=180–200对应360–400次更新 |
| 检查点 | 唯一最终adapter；实际保存并恢复校验参数digest，不选择中间版本 |

旧模型模块仅复用冻结基座、q/v适配器和save/load底层组件；新配置显式传给adapter安装。
不调用旧18/21包训练入口，不沿用旧整遍一次更新的行政记录。
新driver逐更新保存64包ID、系数、原行hash、每行backward事件、梯度范数及一次step，
逐遍验证全部所选训练包恰访问一次，最终核实实际Token和更新总量。
同seed跨臂/池的初始化digest与task schedule再次独立比较。

## 5. 公共生成与离线评分的进程分离

生成worker只接收封闭公开交接对象：model identity、实际基座/Tokenizer资产、最终adapter、
decoder配置、surface目录/manifest、split和输出目录。不会打开study freeze、material
manifest正文、训练报告正文或私有fixture。父编排先核真实最终训练报告、检查点字节再交接。
在线只构造`PublicOverlay`；不同PID的评分进程才构造`OfflineOverlay`。

新decoder callback为`(messages,context)->{raw_response,receipt}`。事前新协议是：
greedy、单beam、repetition penalty1、每响应最多2,048新Token、完整上下文24,576，
32响应/32工具、neutral指导。EOS/pad/bos/模板从实际已绑定资产取得，不猜测常量。
上下文+完整输出预留不足时不生成、不截断、不动态缩减；保留该固定任务分母。
仅剥实际终止EOS，保留原始Token和文字；JSON错误/长度终止交原runtime处理，不宿主修复或续写。

逐回调收据区分callback尝试、Tokenizer调用、实际model.generate、上下文拒绝、
已生成Token及GPU API调用；模型载入、最终adapter恢复、Tokenizer载入另计。
原runtime的零GPU字段只描述其模块自身，不覆盖本地模型进程实际资源消耗。
模型/硬件实现异常与正常上下文拒绝分开，保存原件并停止该模型后续任务，不假作全量有效评测。

生成文件与decoder收据共同封存。离线先逐项核manifest、原request/receipt/raw output/token、
实际资源计数和checkpoint身份，再打开私有参考评分。mock或CPU合成记录不可冒充实际模型。
主指标使用三组等权的完整财务轨迹资格；未知、错误、无Final留在原固定分母。
细类PENDING不自动否定已经成立的财务资格，但同类记录不能进入要求细类映射的训练层。

## 6. A选方向、B主确认

| 阶段 | 固定对象 | 最大实际规模 |
| --- | --- | ---: |
| A训练 | 三臂×三种子 | 9训练 |
| A开发 | 9最终模型×180题 | 1,620会话 |
| 选择 | 完整A开发结果，平均配对严格正收益 | 1次 |
| B训练 | 仅基线与唯一入选方向×三种子 | 6训练 |
| 确认 | A/B、基线/唯一方向、三种子×720题 | 8,640会话 |

同分顺序alpha0、plus、minus，不要求每个seed都正，也不用NLL或方法产率破同分。
若保留alpha0就停止候选确认，不重复相同基线；若选择方向，确认失败不再测试第二名。
B开发为0。真实decision绑定9个训练报告、9个完整开发评分、材料、surface和运行配置；
不是把`prospective_not_executed`数学记录直接改称已执行。

最多15训练和10,260会话；不额外运行旧模板完整面板，不把dev/confirm合成900独立确认。

## 7. 事前统计与解释限定

固定10,000次CIK簇配对bootstrap、95% percentile区间、PCG64 seed20260912，NumPy版本入freeze。
每次对全部确认来源簇等概率有放回抽K个簇，同一个簇multiplicity同时作用所有臂、seed、池和组。
每组按任务加权求均值再三组等权，不改成公司等权目标。空组整次重抽，最多1,000,000次尝试；
达不到完整10,000就失败且不提供部分区间。所有尝试和空组拒绝次数记录。
区间端点按预定15位小数表示，零与5pp边界不靠临时浮点修正选择结果。

B是主结果，A为辅助。B区间跨零不能称确认；上界仍≥5pp则不能声称已排除至少5pp收益。
正区间仅支持当前共同可消费总体、材料核和固定协议下的正效应。
该区间刻画固定训练结果条件下的来源抽样不确定性，不能当成三个seed/两个池已覆盖全部训练随机性。
12个开发CIK、71个确认CIK及既有来源集中继续披露，不再据此追加事后公司配额硬门槛。
显式运算合同仍保留，本研究不是去合同的自然语言理解泛化验证，也不是完整多轮VTDO/Novelty算法。

## 8. 持续执行、资源与故障

入口：

```bash
PYTHONPATH=raw_financial_data_lake:trusted_data_synthesis/src \
trusted_data_synthesis/.venv/bin/python -m \
trusted_synthesis.experiments.finance_qa_vnext_basis_student.stage follow
```

follow只登记一次，每30秒保存只读观察，等待原批次实际封存后自动推进上述闭环。
监看记录位于`artifacts/qa_vnext_basis_student/runtime_20260912`，不纳入科学manifest。
科学运行目录为`artifacts/qa_vnext_basis_student/study_20260912`。
`status`仅查询；不要再次调用旧collect，也不要并发重开follow、materialize或run。

物化前模型/GPU操作为0。满足材料门后，最多8个独立GPU worker、每GPU一进程，按实际空闲
物理index分配并记录UUID；至少76,000MiB空闲且GPU utilization0才启动。
资源不足等待，不降模型、序列、batch或改变seed。不会终止其他用户的GPU进程。
某worker失败后停止发新worker，保留已在途的工作和所有日志；不自动重训、换seed或换长度。
故障记录与研究无正收益、共同材料不足等科学终局分开。

已闭合的采集/材料/研究阶段按用户授权自动提交并推送指定远端main；拒绝未封存范围、
运行账本、密钥、符号链接、大于Git单文件限制的原件以及不相关暂存改动。
发布检查不重写科学字节；若发布失败，另存运行日志，不作为改变科学材料或重跑实验的理由。

## 9. 验证记录与尚未产生的结果

开发阶段已分别完成：五题内核/训练驱动36项CPU控制、解码/分进程评分24项mock控制、
真实报告形状的选择/统计32项控制、编排入口29项控制、受限发布29项临时Git控制。
最终版本联合150项全部通过（57.65秒），Ruff全通过；不把中间复跑次数加成不同控制数量。
含微型CPU模型360次五题更新、每遍精确访问、保存/恢复adapter、禁止二次平均、
混池/缺包/封存误用/错误分母/非有限量反例，以及公开worker只读交接对象测试。
这些记录都明确synthetic，不能用于估计Teacher产率、实际Qwen效用或宣称GPU训练已执行。

集成开发发现并修正过三处新接线问题：公开CIK字段应从period_contract取得；decoder收据
必须放进同一generation manifest；静态清理移除仅外部使用的SURFACES导出后改成显式常量。
它们在正式Student前被控制捕获，没有据此修改旧900题或旧Teacher采集合同。
随后只读检查真实900公共登记，确认180/720、三组60/240与12/71 CIK，未加载私有参考。

截至上述开发快照，尚无最终采集报告、实际共同材料N、正式Student检查点或A/B效用。
后续不能用本文件中的最大规模、合成测试通过数或已存在函数替代这些真实证据。
