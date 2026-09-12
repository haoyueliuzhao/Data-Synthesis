# 同900个评测任务的受保护LLM表述版本

## 1. 用户追加的范围与授权

用户指出原180开发／720确认任务仅确定性模板＋实际期间合同，未启用评测改写。
本阶段补的是表述层，不是重建900个科学任务，不替代已完成的完整轨迹资格修复。
用户已明确批准：900题每题最多一次初始请求和一次合同修复，共≤1,800请求；
输入8,192＋输出1,536的单次保守预留，共≤17,510,400 Token，
并入原1,000,000,000 Token共同总账，不重置既有扣账。

直接科学父仍为原900题manifest
`manifest:90ebc575be3e1c825edb598a937677e0bd83c49cd43c29f35cfe67f543055407`；
来源／资格修复父为
`manifest:6f646a8e45e4e65bec53fe9b75e5bf04047baae0f4b92cfa307bae90b731b4ec`。
修复已实际得到255训练候选、70／70脚本符合预期、54有效正例及独立READY准入；
源码为`2f9ec92a95edf4468f1821c1c9b2ea5437eb544e`，结果发布为
`62a9fd2e58c0c97916fa78a1185111b6d89b0d8e`。
这些父产物不覆盖，也不再调用900题构造、旧70脚本或其CPU编码。

本阶段输出独立保存至`artifacts/qa_vnext_eval_surface/surface_20260912`，
独立审计在兄弟`surface_20260912_audits`。
以下为运行前登记的规则；实际接受率、请求和Token在生产后另行填写。

## 2. 科学任务身份与表述身份

保持900个canonical TaskID、原CIK／源、实际期间、数量／单位、私有参考和QA父链。
只修改question中第一段base，原双换行后的完整实际期间／运算说明逐字保留，
其他公开字段`source_document/quantity_contract/source_policy/tool_contract/period_contract`不变。
模板900＋后继900仍为900个科学目标，不称1800题。

新public／offline表述目录分别为`public_surface_catalog.json`和
`offline_surface_catalog.json`；每题保存新public_messages.json与surface.json。
生成登记用原科学manifest和原公共SHA，新的在线运行时identity则动态绑定已经封存的
新overlay manifest，避免自引用manifest，也不谎称旧manifest包含新问句。
原科学TaskBundle父另作明确引用。只有离线`OfflineOverlay.runtime_bundle()`
读取原private／QA父并叠加新public，派生新表述视图；不制造新QA Build或新QASample。
在线`PublicOverlay`只读取公开目录／消息，不读取私有TaskBundle或offline目录。

## 3. 改写模型只得到公开保护合同

`build_spec(public, identity)`不接私有TaskBundle、答案、正确峰值期或路线标签。
公司以公开CIK绑定，指标名称／定义角色、完整实际期间、输出要求本地保护成占位符。
Provider只发送spec中的固定`model_contract`，不发送整个spec、identity.family、
源数值、私有叶子、参考程序或endpoint／movement指导。
全部实际HTTP body_json、SHA、请求用途／注册身份和公开响应content及SHA保留。
私有reasoning文本不保存；wire哈希不能当作完整wire可重建的声明。

独立原900公共元数据预检得到：差额149、增长151、mean300、peak300。
本地canonical准备为900题都补齐了公开CIK、全日期或明确运算，因此都区别于原base；
这只是公开内容的确定性组织，绝不计为LLM改写。
所有900个spec均可通过本地保护模板验证，原合同和其他公开字段保持；
最大model_contract为1,580 UTF8字节。含最多8个最长合法修复错误码及固定开销的
最坏预检请求输入界为4,800，低于8,192；不是实测DeepSeek Token数。

## 4. 验证base自身，不能用后缀补救错误

已有期间校验及独立面板校验不能单独认证自由改写：开发内存反例中，
“加权平均”“只取首尾两期”“峰值后查前一期”均可能借正确后缀通过。
本阶段使用完整肯定句的有限英语语法，先解析base的完整目标，再恢复受保护字段。
未知／不完整语言形式失败关闭；不因关键词出现或数值答案碰巧相同而放行。

| 结构 | 保持的base语义 | 必须拒绝的代表性变化 |
| --- | --- | --- |
| 差额 | 当前减前期、同一指标及两实际期间、signed量 | 反向、绝对幅度、改成比值 |
| 增长率 | 同一方向、严格正前期分母、百分比换算 | 当前值分母、简单比值、漏乘100 |
| 均值 | 恰三指定实际年度的算术平均 | 加权／几何平均、漏中间期、额外期间或先增长再平均 |
| 峰值后查数 | 全三期按正确primary选最大，再查同一实际期间的secondary | 指标换位、按增长选峰、缺候选、查前期或只答峰值金额 |

占位符必须恰好各出现一次，完整指标名不能漂移，例如cash与含restricted cash不互换。
模板回填后必须能够按原不可变角色精确反向遮蔽；不接受额外数字、实体或期间。
独立auditor不调用guard作为语义oracle，另以标准库从实际保存base解析完整肯定句，
再从原public字段重建角色与期间，核对原消息和新消息的不变部分。

这是有限语法内的语义准入，不是通用自然语言等价证明；被拒绝也不必然表示语言本身错误。
保留显式运算合同意味着本研究主要衡量明确任务定义下的来源获取、计算与完整交付，
LLM改写本身不证明自然语言任务理解泛化。

## 5. 首个语义合格即停止，然后分类

每次返回允许1或2个有序候选，只按原顺序检查。
首个语义合格候选立即终结该题的选择，然后判断是否真实措辞变化。
如果只是复述准备模板或大小写／标点／空白变化，记为`unchanged_or_format_only`，
最终逐字保留原公共消息；不跳后续变体或追加请求追求真实改写率。
只有相对canonical提示有实词变化、且最终base也不是原base的仅格式变化，
才记为`accepted_true_rewrite`并使用新公共版本。
本地补齐公开信息不算LLM语言多样化；unchanged可以保留选中候选证据，但明确未应用于最终消息。

一次初始请求无语义合格候选时，最多一次明确合同修复。
结构失败仅给固定公共错误码，语义失败仅给最多8个有界代码，不把自由文本或私有值塞入修复提示。
再次失败保留原模板，分别记录结构错误、语义拒绝、未变化与canonical fallback。
运输失败不作为合同修复机会；单题失败后继续其他已登记题。
全局模型／鉴权／计费／预算致命错误停止新请求，未请求目标仍留原模板且明确标注未请求，
不能把这种中断称为900题已完成LLM处理。

并发固定8，顺序在首模型输出前冻结，首请求前完整登记900个原TaskID与public spec SHA。
任务不会按改写接受率、后续Teacher产率或Student分数删除、替换或重排主版本选择。

## 6. 同一账本的第三用途

继续使用有限修订已经建立的同一SQLite，owner仍为
`readiness_revision_freeze:c2bf02ab9d7c70632073db2eeecf30bac9f3f97bf6c8927b045c7b68fa226af9`。
继承已知累计为232,357＝221,538历史＋10,819本次UNP，不另建新钱包或清零。
eval_freeze_id单独登记在评测用途元数据；原UNP的17题／34请求限制和原四个trigger不改。

新增独立eval_registry／eval_reservations，三用途预留共同纳入同一SQL事务：
历史＋UNP改写＋Teacher＋评测改写≤10亿。旧ResearchLedger实例也受新增跨三用途trigger约束。
未发送／在途／未知用量不回收预留；已发送请求的超额费用仍落账，再持久停用全局，
不因raise／rollback丢掉已经发生的费用。HTTP200缺失／不一致用量或错误模型视为致命合同错误。
普通超时或HTTP失败仅保守占额并结束该题，不自动重试。

reserve后若另一个线程导致全局停止，未发送的请求保留9728预留，
保存带request_id的NOT_SENT证据，不误记HTTP调用、也不对reserved状态伪造结算。
最终三用途快照单事务统计，不能使用仅含旧两用途的snapshot冒充共同累计。

900题完整终结且无在途请求时，写入一次性finalization并永久关闭本用途剩余次数，
未知终态费用仍保留，Teacher／UNP用途不因这个关闭而失效。
finalization绑定900个TaskID、registry SHA、新public目录ID和eval freeze；
独立题面审计和最终准入都核对它，防止在Student前后重新利用未花完的第二次改写。

## 7. 冻结、独立审计与正式A/B

先提交代码与本说明，再冻结全部当前依赖／新增控制、两个科学父、900个public specs、
共同账本前置状态与用途／发送器政策，随后才真实执行一次。
原父的SHA和已通过准入继续验证；不关闭旧hash检查，不重建900题或重新评价旧70。
独立审计重开实际request／response／receipt／账本、实际保存base及原public，
逐题重算首语义合格、分类、模板保留、原900集合和用途关闭。
整体失败时保留原始错误，不改PASS或重新发一轮来提高通过率。

所有Student臂、种子、材料池共享这一最终表述版本；旧模板仅作工程和来源对照，
不默认增加一整套Student评测。若研究模板／改写敏感性，必须另行事前登记，
不得看过分数后选择主版本。720题相对后续模型／方向选择固定，但内容并非从未审阅。

新表述和既有来源／完整轨迹准入都实际通过后，新入口以EvaluationLedger调用原固定
collection.run与原Teacher Provider：训练目录仍255候选，不把900评测任务放进训练登记。
两池完整24,640会话、每双依据每池每指导32／控制24、并发8、32响应／32工具保持，
不进行小批试采或凑够八包提前停。Teacher仍用其原thinking-enabled/high、16,384输出合同，
不能将评测改写的thinking-disabled／1,536上限偷换给Teacher。

只有全固定采集完成，才用原真实响应物化和按原顺序选180–200共同A/B材料。
原包、失败历史、细类、八训练＋两封存、5题64包、alpha/(40L)、十遍及A开发/B确认规则不变。
未完成总体不得挑部分训练，不用本阶段改写Token代替真实训练Token预算。

## 8. 实际运行记录

冻结前最终258项新增控制通过（15.77秒）：保护问句／独立审计138，
三用途预算／发送器65，overlay19，执行器／最终准入36；Ruff通过。
全部为合成对象、临时账本和mock发送器，不是900次真实改写。
开发中两项峰值样例曾因测试只替换不存在的Calculate而仍是原句，
实际分类器正确判无变化；已改用登记的highest→largest真实变体，不放松生产规则。
共同账本只读前检仍为历史221,538＋UNP10,819＝232,357，
评测用途未登记、评测／Teacher请求均0；磁盘约1.4TB可用。

本阶段实际已执行。源码提交`01dde8afaa6a2987f4df26c6620665e106b49c17`先推送，
随后freeze再次执行同258项并通过（15.65秒）；不把两次相加成516项不同控制。
实际表述准备从2026-09-12 14:12:54.645561 UTC至14:16:01.481756 UTC，
约186.84秒，不含开发、freeze、后续独立审计与A/B时长。

## 9. 900题表述的实际结果

| Split | 运算 | 总题数 | 真实改写 | 未变化原样保留 | fallback |
| --- | --- | ---: | ---: | ---: | ---: |
| dev | 差额 | 30 | 7 | 23 | 0 |
| dev | 增长率 | 30 | 9 | 21 | 0 |
| dev | 三期算术平均 | 60 | 22 | 38 | 0 |
| dev | 选峰后同期间查询 | 60 | 30 | 21 | 9 |
| confirm | 差额 | 119 | 28 | 91 | 0 |
| confirm | 增长率 | 121 | 25 | 96 | 0 |
| confirm | 三期算术平均 | 240 | 94 | 146 | 0 |
| confirm | 选峰后同期间查询 | 240 | 117 | 106 | 17 |
| 总计 | — | 900 | 332 | 542 | 26 |

真实改写为332／900＝36.89%。542条未变化记录实际全部是首个语义合格模板与
model_contract中的canonical_template完全一致，不只是笼统的“格式变化”。
这542条和26条fallback最终都逐字复用原消息，共568条；没有跳第二个已返回候选追求变化率。
900个新surface ID不能写成900条真实措辞改写，也不能称900题全部获得语言多样性。

本地canonical准备900条都不同于原base；最终题面相对canonical_base也有900条词差异，
其中大量只是退回原模板造成，因此这个900不能用于衡量LLM贡献。
按“相对模型canonical有实词变化，并且最终base相对原题也有实词变化”的双重规则，
真正贡献为332；不把确定性CIK／日期补齐算成LLM改写。

全部900题的其他五个公开字段、完整期间后缀、科学TaskID、原bundle与QA引用保持，
新QA Build／QASample均0；新旧SHA分别由所属manifest认证。
独立题面审计实际重开900条原／新public、1,007条请求及其响应／收据／账本，
逐题重新核算首合格、分类、保留原字节、预算和用途永久关闭，结果`passed`、失败0。
原900题来源审计按原身份继承，没有重跑原900金融来源或读取私有答案来验证改写文字。
新统一输入准入为`READY_FOR_UNIFIED_EVALUATION_INPUT`，失败门为空。

## 10. 实际请求、费用与解释范围

900次初始＋107次合同修复＝1,007次，793题一次、107题两次；
全部响应模型为`deepseek-flash`，全部请求settled，用量已知，未知和全局停止均0。
输入511,532＋输出140,427＝651,959 Token。
共同账本在评测结束时为221,538历史＋10,819 UNP＋0 Teacher＋651,959评测＝884,316，
余额999,115,684。后续Teacher继续使用同一账本，这个余额是本阶段结束时状态，不是永远不变。

返回候选共1,867个；按原顺序实际检查1,136个，874个语义合格、262个被拒。
874＝332真实改写＋542无变化，不是874条新语言表达。另731个后续候选未被继续用于挑选。
5次返回存在结构失败；所有原公开返回内容和拒绝历史仍保留。
262个拒绝均落在有限肯定句式保护规则上，不应直接宣称262个金融语义错误；
26个fallback全属选峰查询，也不能推断底层26道金融题不成立。

评测改写用途已永久关闭剩余次数，未用的793次理论余量不会再投入提高接受率。
这仅关闭该用途，不关闭Teacher或改写共同账本的其他已授权消费者。
本阶段tokenizer／Student／GPU／新增源获取均0，未测量效用或自然语言泛化收益。
显式运算合同仍在，结论限于既有任务定义下的表述变化，不是去掉合同后的理解能力验证。

| 身份 | 实际值 |
| --- | --- |
| freeze | `evaluation_surface_freeze:219f5b9a4dbaf1d3eca92831fa070622125841cc5e8da982fa51954fbf09cbdc` |
| 科学表述manifest | `manifest:f29dac61b36396baffd60916bf3b2bdca461a849f0e11bb2d519d54127d2c856` |
| 独立审计manifest | `manifest:05a8c505721eb46b536da95a7cf46b270a800cb267154a0fa42bd6a51bfd782d` |
| 独立审计 | `evaluation_surface_independent_audit:05fc1e0bef90e2048735667f165a1ca19b8cbeeaf104f9f039341cab4852e53b` |
| 统一输入准入 | `evaluation_surface_admission:4314cb21e40b609ec2871ecffb9729ba81e2a154c60d08fbba324ed80fa428f7` |
| 运行报告 | `evaluation_surface_report:d4ae94888b6263dc8551149668b7a62e98521816afbdc3819e31965411bb3e4a` |

表述manifest含5,735成员、33,932,155字节，不含manifest本身；
最大成员1,574,080字节，无需超大文件传输压缩。旧大面板仍父引用，不重新复制或构建。

## 11. 直接启动的固定A/B批次

两级实际准入均通过后，已经直接调用新`stage collect`，使用EvaluationLedger及原
collection.run／Teacher Provider；没有小批试采、失败补采或八包提前停。
实际完整登记24,640个255候选的训练Teacher会话，900个评测目标不在该训练登记中。
批次目录为`artifacts/qa_vnext_readiness_revision/fixed_AB_20260912`。

启动后的一个只读中间快照为125个已完成会话：61个财务有效，40个MAPPED且表示候选合格，
85个PENDING_REVIEW；实际方法为55 endpoint、6 control、64未定。
这仅是固定排序前缀的中间观测，不能当作总体产率、臂比较、样本量选择或效用结果。
不按它修改来源、提示、资格或补采规则。完整批次仍在执行，尚未选出180–200共同材料。

在完整登记全部结束并核对真实响应前，不启动Student训练、不从前缀挑选总体，
也不把本阶段651,959改写Token用作训练材料Token预算。
后续以该批次最终report／共同材料报告为准；当前运行中状态不等于正式实验已经全部完成。

## 12. Student执行尚未完成的接线边界

采集期间只读盘点了既有源码，没有启动Student、加载Tokenizer或修改生产依赖。
当前不能把“原包消费者接口已登记”表述成“本研究Student训练驱动已经完成”。
后续必须先核对完整采集与共同材料总体，再以独立版本补齐以下三处接线：

1. `finance_qa_vnext_eval_readiness/materials.update_examples`已经返回五题64整包及
   `alpha/(40L)`，`finance_qa_vnext_basis_scale_preparation/design.task_batches`已经给出
   十遍调度，但尚无本研究训练driver消费它们。可复用`pq_student/loss.py`的底层损失与
   `pq_student/model.py`的模型组件；不能直接运行仍固定18／21包及整遍一次更新的
   `pq_student/train.py`或`source_class_utility/train.py`。新driver须完整五题累积后更新，
   不能另加微批、全局Token或样本数的二次平均。
2. 新`eval_surface/overlay.py`与`eval_readiness/runtime.generate`已提供统一公共输入和
   离线资格接口，但旧`source_class_utility/inference.LocalDecoder`仅接收一个参数并返回
   `content`，新callback接收`(messages, context)`并要求`raw_response`。还需接入完整原输出、
   checkpoint身份、终止状态及事前冻结的本研究解码额度；不能默认继承旧限额。
   旧`evaluate_model()`还绑定12／24题，不适用于新180／720题。
3. `basis_scale_preparation/design.select_direction`已经实现A池三臂三种子平均配对严格
   正收益选择，但仍需把真实训练报告、统一表述版本、完整轨迹结果与A开发选方向、B两臂、
   B主确认串成执行编排。旧`bidirectional_utility/study.py`不是本研究的新入口。

上述属于既定设计的实现缺口，不是根据中间Teacher产率重新选择设计的依据；
本次题面通过、正式采集运行中、Student执行尚未接通是三个不同状态。
