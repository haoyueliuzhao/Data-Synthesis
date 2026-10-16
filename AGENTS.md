# 项目协作约定

- 减少冗余校验，只做必要核验；优先并行处理并合理使用CPU、GPU资源。
- 工作完成后自动进行Git提交与远端推送，用户已授权，无需另行请求；保留不属于本次任务的修改。
- 每次较大改动编写说明文档。实验报告尽量详细、客观，明确区分实际结果、计划、估计与猜测。
- 项目实验可按任务需要使用API和GPU，实验数据可发送至DeepSeek，无需逐次请求；API key来自`.env`，不要在日志或回复中输出密钥。
- 优先实现新版设计，不为旧版兼容而偏离当前设计。

# GPU资源约束

本轮FinQA实验已按用户2026-10-08要求暂停。所有本轮GPU worker及调度器已退出，完整已提交训练状态和封存反馈保留在原目录；暂停证据位于 `four_gpu_release_01/experiment_pause_01/`。未经用户明确恢复授权，不得启动本轮训练、评价或自动恢复。未来恢复还必须验证原状态及同一feedback参数点，禁止裸用旧 `--resume` 触发新反馈目录或重采样。下列四卡白名单仅是未来运行范围，不构成恢复授权。

用户2026-10-09“参照审计修订并开展后续实验”授权独立的有界、零新采样回放性能验证，目录为 `v25_training_replication_01/replay_performance_01/`；不授权恢复原B块。该验证只用白名单中的完全空闲设备，同时最多1个worker；R0/R1/R2配对及后续完整cohort均绑定首次选定的同一物理GPU，累计资源等待最多24小时，失败不自动重试或回退。只有验证通过且用户另行明确授权后，才考虑恢复原复制实验。

上述V32已以 `STOPPED_NO_MATERIAL_SPEEDUP` 收口，最快R2为1.120428倍，未达1.20倍门槛。用户随后明确选择“另行登记一次有界优化对照”，仅授权新目录 `replay_performance_02/` 中的一次R0/R3对照。R3只增加固定16GiB非KV保存激活驻留预算，复用原数学；新鲜R0/R3共2次预热、8次正式响应回放，无新profiling。仍按原1.20倍准入门，合格才执行一次完整cohort、response16实际冷恢复及独立C与π验收；失败停止、不自动扩展优化轮次。此新授权不恢复原B，不改写V32原协议或结果，GPU范围和单worker限制不变。

V33后续实测四例达到1.375889倍，完成response16冷恢复和573条实际response回放，但于2026-10-09独立C与π复算后的最终显存资源门失败，终态为 `STOPPED_FAILURE_NO_RETRY`，不是整轮验收通过。最终 `response000573` 累计梯度已保留，CPU只读核验与原gJ逐位一致；证据见 `replay_performance_02/closeout_01/record.json`。不得直接重启旧控制器、放宽资源门或改写原失败记录；若需要显存修订或末段补验，应另行明确登记授权范围，原B仍保持暂停。

用户2026-10-09对“另行登记一次末段显存修订与补验：复用已保存梯度，不重采样、不重放573条、不放宽显存门，原B仍暂停”明确回复“授权”。V34使用独立 `replay_performance_03/`，固定同一物理GPU7、最多1个worker，仅补做一次类梯度与C、π复算；保存张量CPU卸载须保持原shape、stride和offset，不改数学。全worker allocated历史峰值仍限76GiB，规定边界free至少2GiB；模型加载计入峰值，阶段间不重置峰值。资源等待限24小时、运行限4小时，失败停止、不自动重试或扩轮；V33失败记录及原B暂停不改变。

用户随后补充“本轮实验可以占用额外的空闲显卡”。该许可属于本轮补验的资源授权，不增加回放或class pass次数、不恢复原B；当前已封存V34仍使用GPU7单worker，额外GPU未派发。启用其他空卡或多卡拆分须先明确工作范围并保持原数值合同，不能把资源许可当成扩展实验预算或改写冻结协议的许可；该补充见 `replay_performance_03/resource_authorization_01/record.json`。

V34已于2026-10-10在登记的4小时上限处停止，终态 `STOPPED_FAILURE_NO_RETRY`。完成3107/4974个有效类梯度训练行；已观测显存门全部通过，但未完成class pass及最终数值补验。3107行没有可恢复的部分class梯度断点，禁止直接从该计数宣称续跑；V33已保存的完整gJ仍保留。收口证据见 `replay_performance_03/closeout_01/record.json`。不得以额外空闲GPU许可为由自动重试、延长原限时或启动新轮；原B继续暂停。

用户2026-10-10提供完整任务分片审计并明确要求“参照审计修订并开展后续实验”。该新授权登记V35独立 `replay_performance_04/`：GPU3、4、5、7最多4个worker按完整任务分片，一次覆盖744题、1360状态、2468包、4974个有效行；每个完整任务实际CPU梯度原子封存。全部任务齐全且四分片进程退出后，由GPU7单协调器按原task/state/parameter序执行一次全局G、虚拟点、pullback、C与π复算。复用V33真实gJ，零新response回放、采样、评分和optimizer更新，原B不恢复，V32至V34失败不回写。总4小时从首worker派发起算，所有阶段共用，不逐阶段重置；停止宽限10分钟由活跃worker共享且不派新任务。显存门仍76GiB allocated历史峰值和2GiB边界free；分片RSS限160GiB、协调器192GiB，全机有效可用RAM至少96GiB余量。失败保留完整任务缓存和剩余名单，不自动追加pass、重试或从V34的3107行恢复。首次四卡资源准入需736GiB有效可用RAM；资源许可不构成预算或门槛扩展。

V35首轮于2026-10-10 12:12北京时间因控制器读取退出中worker的RSS失败而停止，保留674/744个完整任务、4494/4974行的实际梯度。用户随后明确“尝试恢复任务”：仅授权独立 `replay_performance_04/recovery_01/` 的一次恢复，修复进程退出观测竞态，原19文件数学实现与task binding保持不变。原674个缓存逐字校验后复制，不重算；GPU3分片186题已完整成功退出，不再启动；GPU4、5、7仅补各自剩余34、32、4题，然后GPU7一次全局复算。旧中断任务的未封存行可随完整任务重新计算，不称为零额外forward。继续沿用原2026-10-10 14:27:34.528971北京时间绝对截止时间，不重置4小时；显存、主存与同点数值门不放宽。原停止记录不改写，资源历史按旧、新进程分别核验。恢复再次失败或超时即停止，不自动重试；原B继续暂停。

上述恢复已于2026-10-10 12:49:53北京时间再次以 `STOPPED_FAILURE_NO_RETRY` 结束；GPU5完整分片写入成功后，身份读取返回None且两秒退出等待超时，控制器停止剩余GPU4任务。最终保留741/744题、4948/4974行完整梯度缓存，余3题共26行；其中任务739已观测7/8行但没有部分梯度断点，未来仍须完整计算8行。全局协调器、C与π验收未启动；全部本轮worker和控制器已退出。已有资源数值子条件通过不能改写整轮失败，未耗尽的原截止时间也不授权自动重试。收口见 `replay_performance_04/recovery_01/closeout_01/record.json`，报告见 `trusted_data_synthesis/docs/finqa_v35_task_sharding_and_recovery_report_20261010.md`；本次报告生成没有启动新实验，原B继续暂停。

用户随后提供三题收口与生命周期审计，并于2026-10-10明确要求“参照审计修订并开展后续实验”。本次V36仅授权独立 `replay_performance_04/recovery_02/`：只读继承741份父梯度缓存，GPU4的shard01读取并跳过183题，只补原索引739、741、743三题、26行；原GPU3、5、7完整分片不重派。GPU4真实退出后，由GPU7单协调器执行一次原序全局G、虚拟点、pullback、C与π验收，同时最多1个worker，CPU初始化和draining都计入名额。可信结果已封存但尚未退出时进入非阻塞draining，保留GPU锁；episode共享10分钟且不随轮询重置，真实退出码和原数值资源检查均通过才成功。继续沿用原14:27:34.528971北京时间绝对截止时间，不自动建立新四小时窗口。启动主存按实际单worker登记为分片256GiB、协调器288GiB；运行硬门仍为RSS160/192GiB、有效可用RAM至少96GiB、allocated历史峰值76GiB和边界free2GiB，不放宽。零新响应回放、采样、评分、API及optimizer更新，原B仍暂停；旧失败不改写，再次失败或到时即停止，不自动重试或扩轮。

V36已于2026-10-10 13:53:49北京时间以 `COMPLETE` 收口：固定三题26行补齐，744题、1360状态、2468包、4974行完整覆盖；协调器实际读取741父加3新Tensor，一次全局复算的八项数值/状态比较及最终资源门均通过。GPU4、7两个新worker退出码均为0，控制器已退出，截止时间未延长。结论只适用于seed137、C-only、step298固定点，不追认V33或V35历史失败，不作为其他outer通用缓存或新准确率/吞吐结论，也不授权恢复原B。收口见 `replay_performance_04/recovery_02/closeout_01/record.json`；原B仍需用户另行明确授权并核验各自状态与同点反馈。

用户于2026-10-10提供原B受控恢复审计，并明确要求“参照审计修订并开展后续实验”。本次V37新授权登记在 `v25_training_replication_01/production_resume_01/`，覆盖原B既定剩余九模型矩阵，不再重复step298参考补验。首先只接续C-only137的step1192未提交outer：按该真实完整参数状态生成任务缓存，重建G与虚拟点并匹配原point，之后只读原700条封存反馈及冻结奖励，R3完整response梯度回放，复算C与π，真实outer只提交一次，再执行一次真实SFT到1193；此生产接续通过且worker真实退出后才开放其余原队列。C-only137/Full137的1192与C-only251的894三个旧点必须同点复用2100条旧反馈；未来12点各首次采样700条，不减少原剩余5810次optimizer更新、15次outer或8029条终点回答。Static137/251已封存模型和回答只读复用，全九模型封存后统一评分，禁止提前查看两份Static准确率。

V37保留C-only的b_N=0与Full的b_N=0.2，以及原C指数、温度、历史锚、先验锚、完整轨迹logP和700分母；不得跨参数点复用V36缓存或V33参考gJ。四个逻辑任务分片按完整任务保存实际CPU梯度，四卡白名单仍3、4、5、7，最多4个总worker且每卡最多1个，CPU初始化及draining均占名额；同一物理卡被其他项目占用时只等待或用其余白名单空卡，不干预其他进程。GPU历史allocated峰值仍76GiB、规定边界free仍2GiB，模型加载计入且冷进程内不重置；分片RSS160GiB、其他阶段192GiB，全机有效可用RAM保留96GiB。阶段间保存实际值及绑定，不只保存完成布尔值；同点、数值、资源或进程失败即停止全池，不自动重试、重采样、换分支或放宽门槛。安全暂停保留完整任务、response累计梯度或SFT提交状态；历史暂停和V32至V36记录不回写。具体执行版本、资源等待及阶段时限以V37封存协议为准，不能裸用旧控制器或旧 `--resume` 恢复。

V37于2026-10-10 22:48北京时间以 `STOPPED_FAILURE_NO_RETRY` 停止：首点distribution派发后、CUDA初始化前，GPU4被其他项目占用；UUID未变。此前744题、4974行完整类梯度、虚拟点及527/527条实际response回放均完成并真实退出，反馈分母仍700；outer1192与SFT1193尚未提交。用户随后明确“修复问题，继续实验”，仅在独立 `production_resume_01/recovery_01/` 登记V38恢复。六个已完成阶段以原protocol/context只读继承，不重算、不重放、不重采样；新目录仅从distribution接续，真实outer只提交一次并SFT到1193，验收及worker真实退出后才开放原剩余矩阵。首次继承已用outer时间27219秒、distribution时间143秒及全局资源等待143秒，不重置24小时outer/资源等待或阶段预算。派发后仅尚未初始化CUDA的worker可因空卡竞争在同一进程中有界等待，保留GPU租约、worker名额及参数点锁，同时计入阶段/outer时限和全局等待；UUID、RAM、停止与截止时间门不放宽。白名单、数学、剂量、全九模型后评分及失败即停止全池不变；不得干预其他项目、裸启动旧控制器、自动重试CUDA后失败或回写V37失败记录。

V38首点已于2026-10-11 00:18:09北京时间通过实际生产验收：distribution保存原同点C、π且真实退出码0；outer1192恰好提交一次，真实SFT推进到1193，train worker也真实退出码0，资源与提交门均通过。首点零新增API、采样、评分及response重放；证据见 `production_resume_01/recovery_01/pilot_acceptance/record.json`。原剩余矩阵由同一冻结控制器继续调度，全部九模型尚未完成或统一评分；不得把首点通过表述为整轮完成，也不追认V37历史失败。既定白名单、时间与资源门、反馈复用/新采样剂量及失败即停且不自动重试的约束不变。

V38于2026-10-12 21:52北京时间再次停止：Full389、step298的R3回放收到SIGTERM，在完整response261边界封存累计梯度后抛出 `ReplayPaused`，总response为447，同点700条反馈已完整封存。信号发送来源未记录；已观测资源门及阶段deadline均通过，不能归因为显存不足、超时或GPU6交接。旧控制器以 `STOPPED_FAILURE_NO_RETRY` 收口，V39交接以 `STOPPED_NO_MIGRATION` 停止且没有启动新科学控制器；GPU6未用于该次交接。所有本轮进程已退出，原记录及实际断点保留。

用户随后明确“修复问题继续实验”，本次V40恢复独立登记在 `production_resume_01/recovery_02/`。仅对上述Full389回放从原实际response261断点接续，继承完整任务梯度、虚拟点、同点700条反馈和冻结奖励，不重算已完成class阶段、不重放前261条、不重采样；剩余186条按原序累计，447是累计总量而非新回放量。复算C、π后真实outer298仅提交一次，并真实SFT到299，验收及worker真实退出后才开放原剩余矩阵；原context和ID不改，299为原剂量内登记的安全分段，不重复旧C-only137验收。恢复前原剩余4143次optimizer更新、11次outer、五模型5735条终点回答不减少；Full389已生成未提交的700条反馈不能再次发放采样预算，未首次采样十点共7000条。四个已封存模型与回答只读复用，仍须全九模型后统一评分。

V40继承各outer已用时间（包括旧失败回放实际区间）、已起算phase的原绝对deadline及累计资源等待；旧V39交接墙钟和新初始化墙钟按登记口径保守计费，不重置24小时预算。唯一新增class时限例外见下一段，GPU范围以随后追加的全机授权为准；总并发4及原数值资源门不变，不得干预其他项目。旧V38及V39停止记录、冻结源码和协议不回写，不重启旧handoff或migrate。新入口只允许本次明确授权的一次接续；再次失败或超时停止、不自动重试。停止审计不伪造SIGTERM发送者，也不忽略合法停止信号；本次修订不能宣称已消除未知外部信号来源。具体协议和验收见 `trusted_data_synthesis/docs/finqa_v40_response_checkpoint_recovery_20261012.md`。

V40只读预检另发现C-only251 step1192的class阶段仅shard02已完整成功，186题缓存保留，其余shard00、01、03共558题从未派发。用户于2026-10-12对“只读保留186题、仅补558题，为该class另登记首次补片派发起最多4小时窗口，其他outer已用及全局等待不重置”的问题明确答复“授权该有界补齐并继续原矩阵”。仅该坐标允许以父186题只读缓存和新目录558题缓存组成完整原序梯度；禁止重新计算父任务、覆盖父缓存、补片集合变化或不完整零填充。新4小时由三补片共享，自首补真实派发起一次计时，不能按分片重置；这明确延长原2026-10-13 00:17:00.383北京时间class截止，不追溯改写旧记录。该outer原已用6784.417273秒仍继承，后续其他阶段和outer上限不放宽。首个Full389恢复验收通过后才开放这些补片及原剩余队列。

用户于2026-10-12进一步明确“扩大范围，在满足显存要求的GPU上运行即可”。本轮V40的新设备授权覆盖本机物理GPU0至7，取代此前本轮运行的四卡/五卡选择限制；原V38和V39冻结协议的历史范围不回写。新协议须独立绑定八卡UUID、CPU亲和、租约、worker准入及结果验收，旧GPU6交接记录不构成本轮实际派发证据。总并发仍最多4个worker，每卡最多1个，CPU初始化及draining计入名额；继续要求实时准入free至少72GiB及完全空闲、allocated历史峰值最多76GiB、规定边界free至少2GiB，原主存与时间门不变。调度优先原GPU3、4、5、7，再按实际资源选择GPU0、1、2、6；不得干预其他项目，资源未满足时有界等待，不以扩大设备范围为由自动重试或放宽显存门。

V40已于2026-10-12 23:32北京时间完成独立冻结登记，协议ID `8732c9297d5a08cda1cb3990622cc8ee1d0868714c4aaf4de2c252e4a0b97160`，43文件实施包绑定源提交 `e0e964e286c3503001a0b0001895a7a73affc6c4`。CPU依赖及原response261后端绑定核验通过；新控制器于23:40:15启动，PID3447623、birth `424400891`。23:43观察为 `WAITING_FOR_REGISTERED_RESOURCES`，0个worker已派发，八卡均未满足当时准入；首点恢复验收未完成，C251四小时补齐窗口未起算。不得重复启动已有V40入口，也不能把控制器等待视为GPU恢复或整轮完成。正式进度查看 `production_resume_01/recovery_02/`，原V38/V39停止记录仍保持原义。

用户于2026-10-13针对“完全空闲且free≥72GiB”明确要求“根据实际需求放宽”，并选择“保持满额，自然空队列时切换”。本次V41仅修订原矩阵的设备准入：GPU0至7、总worker最多4且每卡最多1不变，按已封存过程内reserved峰值及登记余量，class准入free至少28GiB、train 32GiB、replay_R3及终点generate 48GiB、复用反馈的virtual_point及distribution 24GiB、首次采样的virtual_point 32GiB；其他项目进程存在不再单独否决，不干预外部进程。原76GiB allocated历史峰值、2GiB边界free、主存、数学、剂量与时间门不变，经验阈值不代表未来峰值保证。新策略独立目录为 `production_resume_01/admission_relaxation_01/`，不得热改V40冻结协议。交接固定 `passive_all_or_none`：观察自然全局空队列，八卡租约不能全部取得时立即全释放，不逐卡扣留促排空，不信号worker；完整class、实际成功退出和原状态预检通过后才允许停止核验身份的旧控制器并单次接续。没有安全窗口就停止交接，不强制切换或自动重试；V40正常调度继续。实施与实际启动状态见 `trusted_data_synthesis/docs/finqa_v41_stage_memory_admission_20261013.md`，不能把代码或登记完成称为策略已生效。

用户于2026-10-08进一步要求“约束任务只在这四张卡上运行”；根据当时实际运行设备，固定白名单为GPU3、4、5、7。这覆盖10月7日的六卡上限及让出卡空闲时可重用的授权。

- 原V38冻结调度范围为物理GPU3、4、5、7，最多同时4个GPU worker、每卡最多一个本实验worker；CPU初始化及draining中的已派发worker也计入名额。
- 用户于2026-10-12明确“可以临时占用GPU6”，追加仅限本轮剩余工作的临时GPU6资源许可（UUID `GPU-6cf85ebf-ae89-905b-5d97-46f83b295526`），总并发上限仍为4，不扩展实验、pass、反馈或时间预算；使用前必须确认空闲，用户要求归还时按安全边界让渡。GPU0、1、2仍不得使用。
- 上述GPU6许可已记录，但不等于当前V38已接入GPU6。现有冻结控制器没有热增卡或仅停止派发后自然排空的接口；信号暂停会停止全池，可能中断未封存的首次反馈。因此本次授权登记不暂停、不重启现有实验，不改写冻结协议或源码，不启动旁路worker。实际接入须另行明确受控调度切换范围，并核验同点状态、已封存反馈、实际退出及原剩余预算；不得以资源许可为由重采样、自动重试或重置时限。登记见 `production_resume_01/recovery_01/resource_authorization_gpu6_20261012_01/record.json`。
- 用户随后对“让当前阶段完整封存后，换用支持GPU6的调度器，保留原状态、反馈和剩余预算”的受控切换明确回复“同意”。本次V39使用旧目录下独立 `controlled_handoff_gpu6_01/` 逐张接管自然释放的原GPU租约，全部旧worker成功封存并真实退出、全局队列新鲜且为空后，才允许对核验过身份的旧控制器发送暂停信号。新科学运行独立登记于 `production_resume_01/gpu6_resume_01/`，GPU3、4、5、6、7可选但总并发仍4；旧冻结文件、协议及结果不回写。只继承四个shard齐全的已开始class阶段，禁止未封存/失败阶段重试或部分反馈重采样；完全未派发context可从同一实际保存点重新登记。原计算、phase绝对时限和全局等待均继承，交接及CPU初始化墙钟保守计入全局等待。自然排空失败或预算耗尽不切换、不自动重试。GPU6实际启用以新launch为准，不把交接协调器启动称为切换完成；完整范围见 `trusted_data_synthesis/docs/finqa_v39_gpu6_safe_handoff_20261012.md`。
- V39交接协调器已于2026-10-12 15:22:22北京时间启动，PID2647387、birth `421413768`。15:27观察仍为 `DRAINING_NATURALLY`，仅持GPU3的本项目租约锁，旧GPU4/5/7 worker继续自然收口，未发送worker信号；GPU6尚未派发，新科学协议尚未初始化。交接绝对上限2026-10-13 02:50:19.905北京时间，不重置原阶段时限；达到切换条件后由该协调进程单次接续新控制器。后续查进度须同时检查 `recovery_01/controlled_handoff_gpu6_01/` 和 `gpu6_resume_01/`，不得重复启动已有handoff或migrate入口。
- 空卡可按登记方案使用同进程高显存缓存；非空卡按安全显存门槛运行并保留完整模型、Adam、RNG等断点。资源故障续跑必须验证同一状态，不丢弃或重采样未封存反馈。
- 让渡显卡时只处理本项目核验过PID/birth的进程，优先选择不含未封存反馈的安全断点；不干预其他项目或账户的进程。原实验协议和历史失败记录不回写。

V40首点恢复已于2026-10-13 03:42:41北京时间通过实际生产验收：Full389 step298继承261条实际response后仅新增186条、累计447条，outer仅提交一次，真实SFT推进到299，train真实exit 0；证据为 `recovery_02/pilot_acceptance/record.json`。原矩阵随后继续调度，不能再次执行该先导验收；这仍不代表全九模型完成。后续资源策略交接只继承该成功状态，任何新阶段实际失败仍按原规则停止，不借准入放宽授权自动重试。

V41已以源提交 `31accb1dd1` 完成独立准备，51文件实施包ID `3b2fae948fe19714e4ca69a118de432d5a80f7868c69c2cda88362e91f5bf585`，准备ID `2b0e6e060794b6801cf8ed2581f67cc9e6de94cb6fb35bf7cef136f2708576b0`；最终208项CPU/mock测试和冻结CPU实际依赖核验通过。被动观察器PID107401、birth `429115174` 已启动，10月13日12:46观察为 `WAITING_FOR_SAFE_NATURAL_BOUNDARY`、barrier_gpus为空，未向worker或旧controller发信号；旧V40三R3 worker继续运行。交接绝对上限为10月14日03:02:57.308361北京时间。新科学协议和新科学launch当时尚未创建，不能称新准入已生效。不得重复启动 `migrate`；进度同时查看 `recovery_02/controlled_admission_handoff_01/` 与 `admission_relaxation_01/`。首次未启动准备因引用结构假设被拒绝，完整保留于 `admission_relaxation_preparation_rejected_01/`；它未注册handoff、未发信号或启动科学worker，不能改写为实验资源失败，也不能借此重试任何科学阶段。

V41被动观察器已于2026-10-14 03:02:57北京时间以 `STOPPED_NO_MIGRATION` 到期退出，没有发送worker/controller信号或启动新科学控制器。旧V40随后因Full251 step894 distribution在CUDA前等待原准入超过两小时阶段期限，于10:08触发全池停止，10:19以 `PAUSED_DURABLE_BOUNDARY_NO_AUTO_RESUME` 收口，所有旧进程已退出。五个模型及终点回答已封存，实际剩2355次optimizer更新、7次outer和四模型4588题终点回答。C-only389 step894的virtual退出码为-9且无完整result；不能称全部反馈无损可续，也不能将V41已登记策略称为已生效。

用户2026-10-14明确“重启实验”，并对两项有界例外回复“批准”。V42仅在独立 `production_resume_01/recovery_03/` 恢复原矩阵，直接使用已授权的V41分阶段共享GPU准入，不能重启旧handoff/migrate或修改历史冻结文件。累计资源等待上限获准由24小时增至36小时，保守合并旧已用93466秒不归零，新初始化继续计费；Full251 step894 distribution另登记一次首次新派发起最多2小时窗口，只读继承完整class、700题反馈和474条已完成回放。其余阶段期限与24小时outer累计不变：C-only389 step894 virtual原截止为10月14日20:03:26.573293，Full389 step596 class原截止为10月14日18:25:29.408443，未授权自动延长。三个未提交outer分别继承45784、29611、10541秒已用计算时间。

本次批准的唯一反馈重新执行限C-only389 step894：draw0完整350题、draw1前100题合计450题及旧记录只读保留；draw1第101题只有step0调用意图、无返回断点，获准按原point/config/seed重新执行该请求一次，再首次执行余249题。旧未返回意图不能删除或伪装成从未调用，本次不能称零重采样；700题齐全后才首次执行原反馈评分。原已保存G/theta_bar只读恢复，不重做class或虚拟点数学。Full389 step596仅补未封存467题，父277份完整任务梯度（包括失败分片内已封存91题）只读复用；旧中断题未封存5行不算断点。已接受pilot与五个终点不重跑，全九模型后统一评分，失败停止不自动重试。细节和实际启动状态见 `trusted_data_synthesis/docs/finqa_v42_partial_feedback_recovery_20261014.md`；新授权或实现完成不等于已经实际派发。

V42于2026-10-14 12:26实际启动，GPU3、4、7分别派发distribution、virtual_point和shard01；这是分阶段共享GPU准入首次实际启用。12:28:32因新恢复guard错误地要求新旧临时审计UUID完全相同，在模型调用之前失败，12:29:45以 `STOPPED_FAILURE_NO_RETRY` 收口。三个worker退出码均为1，controller及worker均已退出；不是OOM或数值不一致。450题完整反馈及4262个继承文件哈希不变，新增provider调用、完整反馈、完整任务梯度、outer及optimizer提交均为0；Full389父277题保留，本次1个未封存行不能称梯度断点。收口见 `recovery_03/closeout_01/record.json`，原57文件冻结包保持不变。工作区已离线修正为科学请求严格相同、仅允许合法新审计身份，并通过36项CPU回归和真实原请求预调用验证；没有再次启动科学实验，下一次恢复仍需明确授权，不能用校验前失败作为自动重试许可。

V42停止后累计资源等待继承93720秒，上限仍129600秒；Full251894、C-only389894、Full389596的outer已用分别为45931、29728、10688秒。获准的新distribution两小时窗口已真实起算，截止2026-10-14 14:26:45.162290北京时间，不能随下一次恢复重置；class与virtual原截止仍分别为18:25:29.408443和20:03:26.573293。原唯一未返回请求尚未被V42重新调用，未来若获授权仍只限该请求一次及余249题首次执行，450题只读复用；不得覆盖旧悬空意图、本次失败或冻结实现。

用户于2026-10-14明确“授权修复版运行，当前资源紧张，取消截止时间限制，设置自动恢复”。V43使用独立 `production_resume_01/recovery_04/`，采用已离线修复的科学请求与审计身份分离校验；资源等待、阶段和outer不设截止，但继承所有历史已用统计，原失败与冻结源码不回写。自动恢复仅接续实际完整任务、response累计梯度或训练提交断点，独立保存每次尝试，不重复已提交outer、训练、完整反馈和终点。状态绑定、数值或未知未返回新反馈异常不能盲目重试；旧唯一悬空请求的单次重新执行额度不因自动恢复重置。明确停止监督器时必须停止自动拉起，不能忽略合法停止信号。GPU0至7、总并发最多4、每卡最多1及分阶段共享准入保持；76GiB allocated峰值、2GiB边界free、RSS与全机96GiB有效RAM余量保持，科学剂量和全九模型后统一评分不变。用户同时要求保留GPU0，短期占位及后续真实派发分别登记，不能把占位称为训练恢复。详细合同与实际状态见 `trusted_data_synthesis/docs/finqa_v43_automatic_durable_recovery_20261014.md`。

用户随后补充“gpu4也可以占用”。V43优先派发顺序登记为GPU0、4、3、5、7、1、2、6，仍从原授权八卡中选择且总并发最多4，不扩大科学剂量。GPU0及GPU4准备期各72GiB占位分别写入独立资源记录；只对核验过PID/birth的本项目占位进程交接，不能干预其他项目，也不能将占位当作科学运行。实际worker资源门与未知反馈停止条件不变。

V43于2026-10-14以源提交 `253602fd09a0d6dde04ae6308d2e21ab9066ded2` 冻结67文件，协议ID `93d74f870865e1ecd40b93c77155d8a2fb00d33ef47960cd33c99847af731d60`，119项CPU用例及正式冻结依赖核验通过。监督器于15:18实际启动，PID2068024、birth `438667686`；科学控制器PID2068036、birth `438667781`。GPU0、4占位均已释放并真实退出；首次科学worker派发至GPU0、4、3。15:25时Full251 distribution已真实exit0并在GPU0派发train，C-only389原450题加11题新完成共461题，获批的唯一重新执行已实际返回并完整封存，Full389新增4份完整任务梯度；已观测资源门通过。监督器仍在第一attempt运行，自动后继尚未实际触发，整轮及统一准确率评分未完成。启动证据见 `recovery_04/startup_verification/record.json`；进度看 `recovery_04/supervisor/queue/status.json` 与当前attempt的 `queue/status.json`，不得重复启动监督器、旧controller或migrate入口。

用户于2026-10-14在了解六worker的主存预留限制后明确选择“暂时增至五个”。V44独立登记在 `production_resume_01/concurrency_five_01/`，仅把本轮原九模型剩余工作的总worker上限改为5；每卡最多1、初始化与draining计入名额、原四个逻辑class分片、分阶段显存门、160/192GiB RSS上限、全机96GiB有效RAM余量及按RSS上限全额预留的启动主存公式均不变，不自动采用实测峰值准入，不以五并发为由扩展数学或采样剂量。新交接逐步取得自然释放的八卡项目GPU租约，不信号worker；全部已派worker成功封存并真实退出、全锁和新鲜空队列及同点预检通过后，才停止核验身份的旧监督器并确认监督器/控制器退出，单次启动新版本。未派发class分片可留到新目录，但原完整任务缓存只读复用。交接绑定的旧attempt/身份变化或旧失败即释放锁并停止，不自动追随。V43冻结源码和历史停止不回写，无截止与安全断点自动恢复继续，但明确停止不自动拉起。文档与实际生效状态见 `trusted_data_synthesis/docs/finqa_v44_five_worker_handoff_20261014.md`；准备或交接启动不能称五worker已经运行。

用户随后询问GPU5是否有待安排任务。V44将设备优先顺序登记为GPU0、4、5、2、3、7、1、6，优先使用当前显存余量较大的GPU5、2承接后续任务；不迁移正在运行的worker、不绕过主存门。22:27只读快照显示Full2511192四class分片未派发，GPU5空闲75.67GiB，但新增class需约808.99GiB有效RAM而当时仅约695.66GiB，因而没有侧路增派。新顺序只在新版本实际启动后生效，旧冻结V43顺序不回写。

V44已以源提交 `2c9d7a781149ef9e9c429e97b71e293b5a04d2c1` 冻结74文件，原V43的67文件逐字保留；实施包ID `91b1f5b0c5fb4e57e746f48128fdb67c0ddef5e30d84f41263d38505769a4256`，准备ID `218c1620fa3d0a5ac2ab547e95dad3ec36944eb455e110e933a7feef9a7eae87`。92项联合CPU/mock测试及正式冻结依赖核验通过。唯一 `finqa_v44_supervisor.py migrate` 入口于2026-10-14 22:48实际启动，PID2823865、birth `441367537`；成功交接后同进程转为V44监督器，不能再另启监督器。22:50:31观察为 `DRAINING_NATURALLY`，仅持GPU1、2、5、6、7的本项目租约锁，worker/旧监督器信号均0；旧GPU4 C389 R3、GPU0 Full389 R3、GPU3 Static389 train继续运行。新科学协议和launch尚未创建，五上限与GPU5新优先顺序尚未生效，不能称已运行五worker。进度看 `concurrency_five_01/handoff_01/status.json` 与旧 `recovery_04/queue/status.json`，实际后继运行以新supervisor/queue及launch为准；不得重复prepare/migrate或热改原冻结实现。启动证据见 `concurrency_five_01/handoff_started_verification/record.json`。

用户于2026-10-14针对809GiB主存准入质疑并明确要求“修改此问题”。本次V45在独立 `production_resume_01/host_memory_admission_01/` 修订启动预算，与160/192GiB运行RSS硬限分离，96GiB全机有效可用RAM余量不变。历史91个成功阶段表明完整class峰值124.536GiB，不能用V43约60.9GiB补片峰值代表完整分片；冻结预算为class160GiB、train/R3/generate48GiB、virtual/distribution64GiB，由历史峰值乘1.125加16GiB再向上取整到16GiB倍数取得。每个活跃进程按固定预算与实际VmHWM同式上浮的较大值减当前RSS预留，缺失读数拒绝本次派发，不伪造0或因退出观测竞态停止全池。总worker仍最多5、每卡最多1，原显存、状态绑定、数学剂量和安全自动恢复不变；不允许热改任何历史冻结协议或源码。V44尚未生效的迁移PID2823865已于23:20:26经完整身份核验后单次停止并真实退出，封存STOPPED_NO_MIGRATION；没有向科学worker或科学监督器/控制器发信号，V43继续运行。证据见 `concurrency_five_01/superseded_host_admission_01/record.json`，不得再次运行旧migrate。V45直接从V43安全自然边界交接，不虚构V44科学协议；详细证据和实际生效状态见 `trusted_data_synthesis/docs/finqa_v45_empirical_host_admission_20261014.md`，准备与交接启动不等于已启用主存新策略。

用户进一步要求“GPU2，5应当都可派发任务，此轮修订尽量将这两张显卡利用起来”。V45在冻结前将派发优先序调整为GPU5、2、0、4、3、7、1、6，优先让5与2承接原队列待执行阶段；仅在实时主存、显存、租约与原状态门通过时派发，不新加科学任务填卡、不迁移或中断现有worker。新优先序与主存修订均以V45实际启动为生效依据，不能把准备期显卡可用称为已经派发。

V45已以源提交 `bdcad252f583e56e9a873503bc6b6d280a985531` 冻结81文件，原V44全部74文件逐字保留；实施包ID `c32c3a60ec4b3fa5c943bfa740cf53bdf985d7da7587f664c068ea8058857a6d`，准备ID `a027dd7eddd35524a3ed548d5c649e97ec1016b7bc69c94b23f4374a6af9ebd2`。100项不同CPU/mock用例、相关静态检查与正式冻结CPU依赖核验通过。唯一新migrate于2026-10-14 23:41:10启动，PID2911728、birth `441686539`；23:42为DRAINING_NATURALLY，持GPU1、2、5、6、7项目租约，worker及旧监督器信号均0。旧V43仍有GPU4 distribution、GPU0 R3、GPU3 train三个worker，V45科学protocol/launch尚未创建；新主存预算、五上限和GPU5/2优先序此时尚未生效。23:42快照中新class准入由旧820.05GiB降为假设新策略下404.05GiB，有效可用733.07GiB；这是公式对照，不是实际派发。启动证据在 `host_memory_admission_01/handoff_started_verification/record.json`。不得重复启动migrate或监督器，交接成功由同进程单次接续；进度查看新handoff及旧recovery_04队列，真实生效查看新supervisor/queue与launch。

用户于2026-10-15检查GPU4、5、7空闲仍有待派任务后明确要求“处理此问题”。V46仅在 `host_memory_admission_01/queued_handoff_01/` 独立登记交接补丁，复用V45未激活准备和81文件科学包，不热改、不复制新科学版本、不扩展数学或剂量。新协调器使用原项目锁inode及同一打开文件描述的CPU辅助进程持续阻塞等待；只有真实取得且辅助进程exit0后计为持锁，kernelqueued与held严格分开，不宣称flock严格FIFO。新协调器须先实际持有GPU3并核验另外七卡等待，才能单次pidfd停止身份核验的旧V45迁移PID2911728、birth `441686539`；若旧V45已先完成切换则退出补丁，不停止新科学监督器。旧迁移STOPPED_NO_MIGRATION记录保留，新替换和closeout写独立目录。仍须全八租约、取得后新鲜空队列、所有已派worker真实成功退出与原同点预检通过，才单次停止原V43监督器并验证真实退出，再以新真实receipt调用原冻结V45.initialize和Supervisor.run，不重跑旧migrate。科学worker不收信号，不SIGSTOP控制器，助手锁进程可取消且须回收，明确停止禁止自动继续科学启动。五worker、GPU5/2优先、实测主存预算及原硬门均不变。详细合同与实际状态见 `trusted_data_synthesis/docs/finqa_v46_queued_lease_handoff_20261015.md`。

V46独立三文件补丁已以提交 `13ea08271cd47bae8170034e8a1a786a4bc6c23f` 冻结并推送，实施包ID `15d54ff6e68f74db0f931be6a41c26ff06cf1f57b0608041e45e72d6eaf3113a`，协议ID `02792d37e10c3c33fa981a60824cb693dead1ebbac2b55b8c46d59112c124a69`。62项联合CPU测试和正式路径核验通过。唯一 `queued_handoff_01/implementation/finqa_v46_supervisor.py run` 于2026-10-15 09:07:52启动，PID3726919、birth `445086816`；09:09确认八个helper均真实kernelqueued，但新anchor尚未取得、旧迁移尚未信号，最后Full2511192 shard03已159/186任务。此入口成功交接后同进程调用原冻结V45监督器，不得重复run或migrate；状态看 `host_memory_admission_01/queued_handoff_01/status.json`，启动证据 `queued_startup_verification/record.json`。排队不是持锁，准备不是科学策略已生效。

用户随后明确“先占用空闲显卡等待交接”。本次只对复查完全空闲的GPU5、7各登记72GiB有界显存占位，GPU4有其他项目进程，不做大额占位或干预。资源根为 `host_memory_admission_01/queued_handoff_01/resource_reservation_01/`，最多15分钟；最后Full2511192 shard03达到183/186完整任务即提前释放，交接锚点/关闭记录、原worker或交接入口退出、明确停止也触发清理。占位不取得项目GPU租约、不构造模型、不增加科学worker或实验剂量；原holder的双空闲检查保持，失败不自动再抢。独立watcher仅信号自己创建且身份绑定的holder并核验实际退出，不更改已冻结的交接或科学源文件。实际占位与释放看reserved/released/actual_exit，不把资源保留称作训练恢复。

上述GPU5、7占位监督器于09:20:29以PID3744036、birth `445162514`启动后，在空闲检查处拒绝：两卡已被另一账户09:15:46启动的进程占用，各仅余4773MiB。资源记录为RESERVATION_FAILURE，children_launched=0、实际保留显存0，监督器已退出；没有干预外部进程或停止科学/交接进程。不把本次描述为占位成功或已释放占位，不自动重试。证据见 `queued_handoff_01/resource_reservation_01/closeout/record.json` 与 `verification/record.json`；后续派发必须重新观察GPU资源。

V46于2026-10-15 09:27:50以CLEAN_NATURAL_HANDOFF实际收口，ID `948c04f498038b9a1d34be54dbcb9cb1e278b507fa6367ed65ca07881565d345`。最后Full2511192 shard03于09:26:40真实exit0，随后新GPU3锚点取得、旧V45迁移09:26:43真实退出、八锁09:26:45齐全；29个已派阶段成功退出预检后仅停止旧V43监督器，科学worker信号0。09:27:59新V45科学协议创建，ID `920ff2da160a3bbf055c6c3a5b0e9b3a080ca421deb90efce950959f17f735bf`；09:28:04控制器PID3752585、birth `445207631`启动，监督器仍为V46入口PID3726919。09:29已真实派发5个worker：GPU2 Full2511192 virtual、GPU4 Static389 generate、GPU0/3/6 C-only3891192 shard00/01/02，五份派发RAM/GPU准入通过。V45的原81文件、主存预算和数学不变，新预算/五上限已生效，不再描述为等待切换；GPU5/7本次因外部占用未派发。激活证据见 `queued_handoff_01/activation_verification/record.json`。原矩阵仍未全部完成或统一评分；新监督器已运行，禁止再启动任何旧migrate、queued run或重复新监督器。

V45于2026-10-15 21:21:50以 `STOPPED_FAILURE_NO_RETRY` 停止，监督器随后以 `STOPPED_UNSAFE_FOR_AUTOMATIC_RECOVERY` 退出。触发项为C-only389 step1192 R3内部KV及非KV驻留预算不足，不是已记录的CUDA OOM；已观测外层显存与主存硬门通过，旧分类未识别该内部资源错误。该点日志观察到251/419，但实际可恢复前缀仅240；Full389 step894于全池停止时封存133/540。Full251 step1192的outer已真实提交一次，SFT断点已到1213，不能因train整体失败而重复outer。父 `actual_final_progress/record.json` 记载实际剩1171次optimizer更新、3次outer和三个模型3441条终点回答，六个终点已封存。旧controller和supervisor均已退出，旧失败及冻结包不得回写。

用户于2026-10-15明确要求“恢复任务，后续设置更安全的占用策略保证任务运行，申请固定高显存占用”，随后补充“资源紧张，开放限制，采取更激进的任务分配占用策略”和“取消任务并发数限制”。V47独立目录为 `production_resume_01/fixed_gpu_reservation_01/`：不要求整卡空闲或每卡固定72GiB，按阶段真实需求共享GPU，并在科学worker同进程尽早建立可复用显存预留；取消独立总worker上限，保留已授权GPU0至7及每卡最多一个本实验worker，初始化与draining仍占该卡租约，四个逻辑class分片不变。设备数、任务依赖和实时资源决定实际并发；不得把取消总上限解释为可绕过物理显存、主存或状态门，也不得干预其他项目。

V47初始恢复只读继承上述两个真实R3前缀240/133、同点class及反馈，Full251从step1213后继续；C-only389未封存的11条观测须重算，不能称零重放。两个旧未提交outer共1400题反馈复用，未来Full389 step1192原剂量内首次700题采样保留，六个终点不重跑，仍全九模型后统一评分。原76GiB allocated历史峰值、2GiB规定边界free、160/192GiB RSS硬限和全机96GiB有效主存余量不变；V45经验主存准入继续使用。无截止和安全断点自动恢复继续，但未知反馈、状态绑定或数值错误不得盲目重试，明确停止不自动拉起。新准备、预留小试和源码完成不等于科学任务已实际派发；真实状态以新目录协议、launch、supervisor及worker记录为准，禁止重复启动任何旧入口。详细合同和实际启动结果见 `trusted_data_synthesis/docs/finqa_v47_shared_gpu_reservation_recovery_20261015.md`。

V47首次以源提交 `8b24d9e09c` 冻结89文件并实际启动，但于2026-10-15 22:29因新准入心跳schema与继承控制器仍要求的旧schema不一致而停止。GPU2 Full251 train已真实预留31GiB，但在模型加载前因合法停止标记退出；不是OOM。自动分类还漏审控制器根因，误放行第二attempt；它在GPU2为C-only389 R3预留70GiB，加载模型并实际恢复父response240，随后仍在240暂停，没有新增response。助手于22:32:33身份核验后pidfd停止监督器以阻断attempt3；第二worker自己的SIGTERM记录早于此操作，发送者不作伪造归因。监督器、两个控制器及两个worker均已退出。九arm实际checkpoint完全不变，新增API、反馈、response forward、optimizer、outer及终点回答均为0，剩余仍1171次更新、3次outer、3441条回答。第一轮失败、错误allowed=true判断和89文件冻结包保持原样；收口见 `fixed_gpu_reservation_01/closeout_01/record.json`，终态 `STOPPED_IMPLEMENTATION_FAILURE_NO_SCIENTIFIC_PROGRESS`，不称整轮或数学验收完成。

用户获知上述两项实现错误后明确回复“授权修复后重新启动”。仅在独立 `production_resume_01/fixed_gpu_reservation_02/` 重新登记修复版；新的心跳捕获器保持所有身份、阈值及时间检查，自动恢复必须先确认控制器根因和实际资源主失败，合法停止后果不能单独放行。原V45数学81文件不改，旧fixed01冻结和失败不改；实际父为fixed01的attempt0002，继承其最新真实断点与累计phase、outer及资源等待，不重置计时。C-only389实际重存的response240与原Tensor逐字相同但record ID不同，不伪造旧记录；Full389133、Full2511213及原剩余剂量不变。继续取消独立总worker上限，保留八卡每卡一个本实验worker、共享分阶段准入、预留与原硬门；新登记和代码修复不等于已经启动，新科学launch和验收另行记录。禁止重启任何fixed01入口或把旧错误自动恢复决定作为新授权。

V47修复版已以源提交 `f4c57232bdf39bb9a32ac9e4142d476aa75d81a6` 冻结89文件，实施包ID `d8313eee822ba047c1feb6cd34b88defd88e498021516ada7413468ad2725fb5`，协议ID `fcd1b4b5cfb2dab3a9a758c377cc4334fe3e2bd9dd23473a50777a5c4b9131f3`；173项联合CPU/mock与正式冻结依赖核验通过。唯一监督器于2026-10-15 23:01:39启动，PID2143408、birth450089459。GPU3第一train实际预留26GiB并从1213提交到1215；随后规定边界物理free跌至1.615GiB，原2GiB门正确停止该worker。其资源主因及实际退出被新版分类核验后，监督器已经自动创建 `fixed_gpu_reservation_02/attempts/attempt0002/`，没有重启旧attempt。23:10:47在GPU4派发train PID2163413、birth450144285，真实预留28GiB并从1215接续；23:14已观察到step1216保存，资源子门通过，整段及全矩阵尚未完成。真实自动恢复证据见 `fixed_gpu_reservation_02/resource_recovery_verification/record.json`。查看进度先读该根的supervisor/queue指向当前attempt，不能只看初始根的已封存失败；不得重复启动监督器。共享GPU的物理free仍可能变化，不能把预留或这次成功接续表述为今后不会发生资源中断。

V47修复版于2026-10-16 02:45:20北京时间结束attempt0004，监督器为 `STOPPED_UNSAFE_FOR_AUTOMATIC_RECOVERY`。触发项是Full251 step1237 train在模型加载前的 `ReservationAdmissionError: physical boundary reserve exhausted`；常规资源monitor尚未构造，旧分类没有资源观测而拒绝自动恢复，不是已记录的CUDA OOM。该检查没有保存当时free字节数，不得补造。旧监督器、控制器和三个worker均已退出；实际Full251已提交至1237，C-only389与Full389回放前缀仍240/419及133/540。剩1147次optimizer更新、3次outer和三个模型3441条终点回答，六个终点已封存；1400条旧待提交反馈只读复用，原未来首次采样仅700条，不能沿用通用进度快照的2100条推测重新发预算。父收口见 `fixed_gpu_reservation_02/closeout_01/record.json`，历史失败和冻结源码不改写。

用户于2026-10-16明确要求“修复问题，自动恢复应当覆盖此类问题，或者此类问题不应该阻塞任务池的派发”。V48仅在独立 `production_resume_01/resource_deferral_recovery_01/` 登记修复与继续运行。模型加载前有真实观测的显存不足转为同进程等待，保留该worker预留和GPU租约，控制器仍可派发其他GPU；等待不称为科学阶段通过，也不允许在资源门未恢复时加载模型。原GPU0至7每卡一个本实验worker、无独立总并发上限、无截止、安全断点自动恢复及显存主存硬门保持；状态、数值、未知反馈或非法allocator错误不作资源不足放行。后模型资源失败仍依实际断点恢复，不回滚或重试已提交训练与完整反馈。旧V47所有入口不得重启，实际新启动须看新协议、唯一监督器launch和队列，不把修订准备称作已经派发。详细合同与验证见 `trusted_data_synthesis/docs/finqa_v48_pre_model_resource_wait_20261016.md`。

V48已以源提交 `b4c66b1f141fd68e81c99d8debca1d17f584a701` 冻结89文件，原81数学文件逐字不变，实施包ID `759e627fdebf81711ecc3b969742fe99128726b9d2bd90f34615d7a5413597ed`，协议ID `7a297ae7f2436393aaa929427f0f950995f5d27631111bd8b963e07be1da714e`；167项CPU/mock联合测试和正式冻结CPU依赖核验通过。唯一新监督器于2026-10-16 09:41:42北京时间启动，PID712457、birth453929692，控制器PID712490、birth453929831。09:43:08实际核验为监督器RUNNING、attempt1，控制器 `WAITING_FOR_REGISTERED_RESOURCES`、0个worker；GPU6 free约8.73GiB及其他设备当时均不满足待执行train/R3准入，新增训练、回放及API调用均为0。自动等待与调度已运行，不称科学训练已推进；后续资源满足由现有监督器/控制器接续，不需也不得重复run、initialize或旧入口。证据见 `resource_deferral_recovery_01/startup_verification/record.json`；进度先读新supervisor/queue指向当前attempt。剩余1147更新、3outer和3441终点回答及全九模型后评分不变。

用户于2026-10-16明确要求“当前进度，此外约束并发上限为4”。本次V49独立登记于 `production_resume_01/concurrency_four_01/`，仅将本轮原矩阵总worker硬上限设为4，包含CPU初始化、CUDA前等待、模型加载前资源等待及draining，每卡仍最多一个本实验worker。GPU0至7范围、原数学、剂量及显存主存硬门不变。旧V48冻结源码不热改；交接先在八个原项目GPU租约排队，实际持有至少四锁后才可称旧运行已受≤4约束，排队不等于持锁。正常科学worker不信号；全部八锁、新鲜空队列和实际成功退出等条件通过后，才停止身份核验的旧监督器并确认控制器退出，按届时真实保存点一次接续新内置四上限版本。管理与监护进程共同保锁，单个管理进程失效不能先放锁使旧无上限运行继续；异常保护只处理核验身份的本项目进程，不干预其他项目。无截止与安全断点自动恢复继续，自动后继也受四上限约束。不得把新代码、准备或排队当成限制已经生效，也不得重复启动任何旧、新入口。细节和实际生效证据见 `trusted_data_synthesis/docs/finqa_v49_four_worker_limit_20261016.md`。

V49已以源提交 `fdc4ffe3f17325b2928b18d22bc3d1bd408303d8` 冻结90文件（原数学81文件不变），实施包ID `2d6e8da1d252690b0b2b93f027caeb2d95f0829c6e99a1818561a2952a315f69`，交接协议ID `36f4eedfb9f6e1a7777c55fcdf7ed2a35602f1b92b97290041e32536e948f9c8`；104项CPU联合测试及冻结准备期核验通过。唯一交接进程于2026-10-16 12:18:42北京时间启动，PID1451212、birth454871719，监护进程PID1451246、birth454871787。12:18:44已真实持有GPU2、3、4、6、7五个原项目锁，交接期至多保留原GPU0、1、5三个科学worker，故≤4约束已生效；不是仅排队或仅源码修改。12:20:17核验两个持锁者均存活且打开原八锁inode，旧三worker继续，科学worker/旧监督器信号均0，状态 `DRAINING_NATURALLY`。新科学protocol和新supervisor尚未创建，旧V48仍运行且其冻结上限字段仍为null；有效过渡限制依据真实租约，不热改旧字段。核验见 `concurrency_four_01/cap_activation_verification/record.json`，进度看 `handoff/status.json`、锁持有者存活及旧V48当前attempt；正常条件满足后由该唯一交接进程接续新四上限监督器，禁止重复run、手动initialize或释放仍保护旧运行的租约。单一持有者故障时按登记保护先停止本项目旧运行再放锁，不能关闭辅助管理后任由旧无上限自动派发继续。12:20实际Full251为1279，Full389回放持久前缀160/540，C-only389仍为240/419，余1105更新、3outer及3441终点回答；实际交接必须读取届时新保存点，不固定于该快照。

# 本地测试临时文件

- CPU/mock/pytest 的临时运行目录统一放在已被Git忽略的 `trusted_data_synthesis/artifacts/test_tmp/` 下；使用 `mktemp -d` 创建独立子目录，再作为 `--basetemp`。不要把 `.test-*`、`.v10-*-cpu-*` 等临时目录建在仓库根目录。
- 测试夹具、模拟账本与模拟训练结果不作为正式实验产物提交。需要保留时归档在 `trusted_data_synthesis/artifacts/local_test_archive_*` 下；正式实验和必要审计记录仍按原要求单独保留、提交。
- 整理未跟踪目录前先核对其用途和是否仍被进程使用，优先采用可恢复归档，不覆盖或删除用户数据。

# API 模型约束

用户于 2026-09-27 明确要求：“本次实验继续，后续实验 api 调用模型固定为 deepseek-flash”。

- 后续所有新实验的 API 调用统一使用 `deepseek-flash`，包括数据生成、数据处理、辅助审核、裁定、能力小试和排障试验。
- 不得因限流、响应格式、效果、默认配置或所谓独立性，自行改用 `deepseek-v4-pro`、reasoner、视觉模型或其他模型；不得设置模型回退。变更模型需要用户明确另行授权。
- 新实验协议必须显式登记模型名；新增或修改的 API 调用入口须在发出请求之前检查 `model == "deepseek-flash"`，不依赖服务端默认模型。
- 本轮已登记的跨市场校准主线按用户“本次实验继续”的要求，保留原协议中的 `deepseek-v4-pro` 继续完成，以免在同轮混合模型或重写已有结果。这是仅限当前轮次的例外，不得沿用于后续新实验。
- 此约束针对 API 调用，不改变本轮九个固定 Student 保存点、GPU 评价条件或历史实验记录。

详细适用范围见 `trusted_data_synthesis/docs/api_model_policy_20260927.md`。
