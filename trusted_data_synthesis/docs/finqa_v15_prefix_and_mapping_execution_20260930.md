# V15：无状态共同前缀与固定54题映射裁定并行（2026-09-30）

> 运行更新：36项新映射全部真实返回，30题通过、0新增UNKNOWN，完整分区现为738/744，余6题。共同前缀已经实际训练：三个seed的正式step1及真实保存/恢复均通过；北京时间13:27:42分别提交9、10、9步，继续向各298步推进。完整五臂仍未准入。实测来源、费用和停止边界见第9节。

## 1. 这次修订改变启动依赖，不改变研究总体与五臂目标

本轮依据用户提供的 V14 增补审计及“参照审计修订并开展后续实验”。原 V14 仍是全部监督/编码完成、690/744 题映射完整、54题阻塞完整五臂的历史结果；不改写原失败或伪造 V14 完整训练 binding。

新增两条并行路径：

```text
原全部744题 / 2468包 / 固定监督与编码
  ├─ 真正无状态Static先验前缀：seed11/29/47，各298步
  └─ 固定54题原返回定点复核：已派生18题，余36题各一次新判断
        ↓
  所有744题真实映射 + 完整绑定 + 实际非退化支持
        ↓
  原共同step298保存点零更新迁移 → 原五臂 / C-N机制 / dev883
```

前缀使用全部744题，不是已映射690题；不把未知包塞入临时状态，不创建临时χ或π，不追加Probe、反馈或dev。每seed到298步强制停止。若映射未齐，保存θ、Adam、RNG和游标后释放本任务GPU等待，不先跑Manual或自动臂。

本说明的登记/准备章节不声称CUDA、894步前缀或完整五臂已经完成；真实启动和首步验收应由后文执行补注记录。前缀loss下降不作为后继比较的准入条件，也不作为VTDO收益。

## 2. Static前缀为什么不需要状态分区

原频数先验和类内均匀核为 `r(z|x)=n_xz/n_x`、`K(P|x,z)=1/n_xz`。当π=r，每监督Token的系数精确消去状态计数：

`r(z|x)/(actual_B_j*n_xz*L_P) = 1/(actual_B_j*n_x*L_P)`。

新 `PrefixPool` 和 `PrefixDriver` 直接使用右侧，不含 `state_id`、`chi`、`prior`、`pi` 或伪造的 `_manifest`。它不是原完整五臂pool；`prefix_only_admitted=true` 与 `full_five_arm_admitted=false` 同时保存，旧完整训练入口不接受这个新prefix-only schema。

成立条件仍是原固定包损失、频数先验和均匀类内核。任意状态先验、已经更新的π或改变的监督目标不能套用此抵消。行顺序和浮点路径保持：按原任务日程的任务次序、原任务内包顺序、原响应行次序，Fraction化简后只转换一次float，调用原 `trajectory_consumer.execute_update` 的CE/backward/全局clip/单次AdamW热路径。

零目标行不额外forward，以免改变dropout RNG；其全部原历史仍保留在缓存和后续输入中。`material_order_id` 绑定全部原行SHA，包括零目标行。prefix与完成映射后的真实full pool必须逐项保持相同任务、包、行、目标、tokenizer/template及顺序，不能按状态重排后声称执行等价。

## 3. 固定54题的表示复核与来源划分

先完整保留原54份返回，以统一规则核对，而不是重新映射全部744题。690题既成立权威直接引用原record，分区、证据和χ不变；全部监督mask和V14编码不变。

### 3.1 缺summary的17题：复用原字段中已有的分类依据，不编summary

18个“首错状态仅缺semantic_summary”案例中，17个原返回都已在 `chi_reason` 明确陈述同题全部成员的共同程序/推导、观察解释及没有实质核验/修订差异，原χ均为0且interventions为空。主线程逐条阅读完整原声明及成员程序/证据覆盖，并登记一次有界来源解释；不只按same关键词或最终程序相同自动造类别。

该解释证书绑定17个精确原record、原arguments SHA、basis字段位置和原文SHA。来源标注为 `Codex_source_interpretation`：是在解释既有模型已经写出的依据，不是新模型调用、人工金标或独立金融真值认证。`semantic_summary` 继续为None，缺失事实保留；不补空串、不写新说明，不更改原χ或成员归属。

17题仍须通过完整成员恰好一次、全部引用定位、状态证据归属、χ等必要检查，实际全部通过。剩余的 HFC χ1 缺summary案例没有套入χ0解释规则，保留补注。案例、完整原声明与来源位于 `mapping_basis_candidates/`；该候选表自身仍标注未批准，真正解释许可另存在 `mapping_basis_interpretation/`，没有覆盖候选原件。

### 3.2 一题引用：已选unit内唯一，而不是整segment取第一次

23个quote问题统一按其已选原unit检查。NKE/2014/page_36.pdf-3的两个quote在整segment各重复4次，但在已明确选择的unit内部各自唯一，原unit边界能够确定唯一字符位置。因此新增派生视图使用“选中unit内唯一、逐字、原边界”的定位合同，保留原两个状态及χ0。

其余22个quote案例存在所选unit内找不到、重复或空quote等问题，不模糊匹配金额、不删除限定词、不自动取第一次，也不扩大引用范围。consequence越枚举、证据归属或χ支持不成立的其他案例不靠置χ0或伪单例解决。

### 3.3 正式冻结结果

| 固定范围 | 本轮处理 |
| --- | ---: |
| 原690个已完成任务 | 原权威直接保留，0新增调用 |
| 原54题统一复核 | 54份完整保留 |
| 缺summary但已有明确分类依据的派生 | 17题 |
| 已选unit内唯一精确引用的派生 | 1题 |
| 复核后仍需新判断 | **36题，各唯一新调用** |
| 复核后的已知完整任务 | 708/744，不作为新训练总体 |

17条有界解释、1条定位修订和36份新模型来源分别记录。新旧权威在训练和新返回前固定：新36项只认新来源，不与旧失败择优；新失败不自动重问。所有54题连同其215个原包继续存在于原全核。

## 4. 新36项API：只补映射，不动监督或训练数据

API固定 `deepseek-flash`，最多16并发，原显式 `127.0.0.1:7897` 代理、TLS、`trust_env=False`、零底层重试保持。新namespace `v15mapping:`、attempt1/turn0，不能用旧permit重发已调用项，不能借新许可重新生成、重审A/B或改监督投影。

每题仍输入全部原共同轨迹及实际工具交互。短包/动作/证据ID、一次成员表达、Host规范生成state ID保留。新wire用一个 `basis` 承担分类与χ依据，避免同一说明被要求在summary与chi_reason两个位置重复填写；原返回文本按真实来源单列，不伪装成旧模型原来就提供了summary。

输出容量按实际对象/输入事前准备：16384档6项、32768档18项、65536档12项。最大完整请求185316字节，总计3638645字节；36项全部准备完成，原输入不截断。上限不是本轮费用或实际输出，扩cap也不是本次修复方向。

所有请求的字节、精确名单、字段权威与代码hash在prefix binding之前登记。Mapping模块没有读取Student loss、梯度、checkpoint或dev结果的路径；后续不能根据训练表现调整这36题。

## 5. 共同前缀材料与真实计划剂量

原744题、2468包，固定504276监督Token＝reason325582＋tool88905＋final89789；原最高序列9698、上下文24576，不截历史。保留原Qwen2.5-7B-Instruct、全层q/v新LoRA（rank8、alpha16、dropout0.05、FP32可训）、BF16冻结base、seed11/29/47和AdamW（lr1e-4、β0.9/0.999、eps1e-8、weight_decay0、foreach/fused关闭）。

| 项目 | 登记计划，非已完成量 |
| --- | ---: |
| 每seed epoch数 / 步数 | 2 / 298 |
| 三seed物理更新 | 894 |
| 每seed监督Token呈现 | 1008552 |
| 三seed监督Token呈现 | 3025656 |
| 三seed原包呈现 | 14808 |
| 每epoch全部原响应行 / 实际正目标forward行 | 4978 / 4974 |
| 每epoch全部缓存序列Token | 21458048 |
| 每epoch实际forward序列Token | 21441553 |
| 每seed实际forward序列Token呈现 | 42883106 |
| 三seed实际forward序列Token呈现 | 128649318 |
| 新Probe / C反馈 / dev会话 | 0 / 0 / 0 |

4个零目标行不执行forward，其16495个序列Token仍在完整缓存统计中；不能混用“全部缓存”和“实际forward”分母。序列统计包含每个响应的完整历史前缀，不是唯一语料Token数，亦不是max9698乘包数的估计。每epoch149批，两个尾批各真实4题，按实际B归一化、不补假题。

原包/行执行身份为 `ad3c7301edbf3e1f1b590a86b87a12c8a84587bf438ff069d5309aa662508f82`。后继状态标签即使完成，也不能改变这个共同计算身份。

## 6. 正式第一步验收、保存与停止

每seed用首个预登记真实任务批执行正式step1。原consumer检查有限loss、全部可训梯度与有限clip norm、只做一次clip和一次AdamW step；随后检查θ/Adam有限，保存真实模型、Adam、RNG、任务游标与共同材料身份，并从该保存点实际restore比较状态。

成功后step1就是前缀第一步，不再跑一份“验证版”或从零重复。加载峰值显存与训练峰值分别记录；9698可编码、24576 MiB可用显存仅为准入启发，不保证CUDA成功或后继长反馈显存。

资源OOM、数值失败和保存/IO失败分开记录，未提交更新不算已完成步。每个成功提交点保留，恢复只从最后耐久提交继续，不截历史、换模型或改Loss。前缀driver没有外更新、反馈或dev入口，constructor/step/run_until/seed结果均限制原298边界。

调度只在GPU有足够实际余量时装载真实worker，不占位，最多三个GPU seed worker。映射子进程不占GPU worker名额；其停止或未齐不取消已经获准的全体先验前缀。若前缀到298而映射未齐，模型进程退出并释放本任务显存，保留保存点等待。

## 7. 完整映射后的显式迁移，不伪装新的“训练前决策”

在任何Student启动前，另登记 `continuation_intent`：只要相同全体材料完整、真实Dπ和题内χ对照成立，就按原探索性五臂推进；不以prefix loss或dev选择是否推进。这是事前条件，不是看到前缀效果再作研究范围决策。

后继收到完整mapping时生成新 `v15_prospective_condition_realization`，明确它可能晚于prefix执行，但只是在兑现原先冻结条件。原launcher新增窄接线验证该schema与真实pre-prefix intent、相同full/prefix binding，并核intent时点早于三个seed首次真实launch；不把它伪装成旧 `v9_pre_student_scale_decision`。

三个seed各唯一step298保存点通过以下核对后零更新迁移：全scope与mask不变、tokenizer相同、包/行顺序和正目标执行序相同、真实首步保存恢复验收成立、θ/Adam/RNG/游标保持。只有此时才加入已经完成的真实频数prior/pi字段，原无状态prefix记录仍不含π。

迁移后的标准shared保存点被原五臂resume入口读取，`run_until(298)`不重复更新；随后Static、Manual±、C-only、Full从同一共同点接续。C-only/Full仍要在298完成第一次真实700反馈/外更新后才可前进一步。

外更新298/596/894/1192、机制447/745、终点1490、350题×2反馈、15模型×883 dev保持；Full仍是唯一主候选，主比较Full−Static、次比较Full−C-only。全零反馈不补采、不用N制造移动。无test1147、无同时修改Loss，Exp4不声称动态Student闭环收敛，Exp5独立后置。

## 8. 费用、控制与来源

原钱包总额2000元、审阅/映射子额1300元、global258000/review25000调用上限及全部152个历史UNKNOWN预留不变。V14终点全局余402.459485元、子额余207.231248元、子额请求余380；新36项必须追加独立精确permit，不能从余额推导连续重试。894个GPU更新不由API余额保证。

必要新控制共34项：定点映射协议10项（0.49秒）、预算/provider/controller6项（6.87秒）、prefix训练8项（3.97秒）、依赖/绑定/停止门10项（1.62秒）。同一测试重跑不重复计数。不重跑旧全审、Base883或旧限定数学演示。

Prefix CPU对照从非空Adam及相同dropout RNG出发，比较三种合法分区下原先验系数与直接包均值，在5题和4题批次中loss、未clip/已clip梯度、θ、Adam及RNG逐位一致；还覆盖首步仅更新一次、恢复、全映射后迁移、首outer阻断和OOM/NaN分类。**这是合成CPU控制，不是生产Qwen/CUDA逐位对照**；生产须由真实首步另行记录。

正式根目录：`trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v15_prefix_completion_01/`。

| 已发生的零模型记录 | ID |
| --- | --- |
| 17项有界解释候选表，原表未覆盖 | `71c74c088d2bef57c37a8abdb5ecb76290263202cd5d54bdd308eafca6840059` |
| 原声明解释证书 | `1610150179607cd7ad1a7d7cd10d6e789d0184f41dac8e14f62a5f01e399f9a6` |
| 固定54原件复核summary | `ac7899917c07a532c926f2871099b0d7d5ce2a22878c2328bcbaf881a6dd2c7c` |
| 新精确范围definition | `7ca1100e2c0f98715f9bd38e8cbe0df4faec72f12a149412624ad402589f1f93` |
| 完整36请求preparation | `c617c93fae8bc8c76585556dff8ebbcac3140753252b7a96a2d3d060bdf280f2` |
| 新映射矩阵registration | `92e12ababef3143bf94a5e1e80ef9259909f7488bafb3630c9d64a6fcffcab8c` |
| 独立prefix-only binding | `7cf8cca1d6ba08130587a3f38a00432e7d880b49fdf2c3e56a8dcbc8684ea0fa` |

原V14返回、690个成立权威、2468包原轨迹/监督/编码均以hash引用，不覆盖。定点解释在 `mapping_review/`、新请求在 `requests/`、真实新返回在 `annotations/`；prefix材料在 `prefix_material/`，真实训练与保存点在 `prefix_training/seed*/`；完整状态绑定仍需后续 `material/binding/`。

prefix实现细节见[专门训练说明](finqa_v15_state_free_prefix_training_20260930.md)。所有计划步数、费用预留、表示解释与实际训练结果分别记录，不把支持域非退化或prefix损失变化写成VTDO训练价值确认。

## 9. 已真实启动：三个共同前缀首步通过，完整映射仍余6题

### 9.1 冻结、许可与启动身份

执行源码固定在提交 `c0e339cf9e993515deac6d0f60d1cdf504705c1e`，独立目录 `.codex-worktrees/finqa-v15-prefix-20260930`。目录只检出实际代码、脚本、测试和文档，原数据/缓存仍引用canonical绝对路径。首次稀疏检出未初始化index，实际启动前已正确填充并显式核对模块 `__file__` 属于该冻结目录；在此之前无新API和GPU装载。

| 实际登记 / 执行证据 | ID |
| --- | --- |
| prefix launcher | `d6841ca11342a991a02ac6f12b70c934cbc5702b05d34e1e4799f93a5ba5cc0c` |
| Student前的continuation intent | `cd508f367ef232ca18931181793ff675e3b28c4a1c4485fac6b3d061e6805b9e` |
| 并行workflow登记 | `c91e2562b380fddc28a998cd75865852dcdc7a6ea78ed58cf958c1b1716e35d1` |
| 原钱包新精确permit | `b2399f87ed15e3fa0f82a2255b95f61282e7c61bc9073684573cc06734b5945b` |
| 钱包部署收据 | `bd78c1aa8853bfa9b70b82e0b746d201ff02ea373864aad7b55cfdf2de2d078d` |
| 实际workflow launch | `fd108b57598a43fa684904d4ab37047368f7cd1be5c480092c20c16d98322027` |

真实启动为北京时间 **13:17:26.286**，父PID3964243。按当时实际余量，seed11/29/47分别分配GPU6/1/2，PID3964272/3964273/3964274；并非预占设备或仅完成代码。初始前缀许可时没有Student结果，mapping全部请求已准备；后继映射审计人员未访问Student loss、梯度、checkpoint或评价。

### 9.2 API侧已经完成，未隐式重试

36项首派发13:17:28.354，末结算13:17:51.696，API完成心跳13:17:52.189；全部真实返回，用时约23.34秒，逻辑峰值16。新映射完整30，6份不可用，UNKNOWN0；原始36份都声称complete，不表示校验全部通过。

| 6份剩余首因 | 数量 | 实际细分 |
| --- | ---: | --- |
| 状态对象缺字段 | 3 | 1份缺members；2份缺members与partial_evidence，无extra字段 |
| consequence超出typed enum | 2 | 原选择未改为近似ID或χ0 |
| complete与非空ambiguity_notes合同冲突 | 1 | 成员已覆盖，但原说明非空，未删除后放行 |

这次首因不再是summary/basis缺失。完整原件及首因保留，不能推断未执行的后续检查都无误。所有返回以tool_calls结束，length及触cap均0；completion P50/P95/P99/max为655/1094/2074/2074，没有扩大cap的证据依据。

完整分区由690旧权威＋18派生＋30新模型构成，共 **738/744**；剩6题仍在完整分母，不影响全部原包参与Static先验前缀，但阻断五臂和反馈。`material/result`明确为 `BLOCKED_MAPPING`，`material/binding`不存在；这个完整训练门没有被prefix-only许可改成true。

已解析738题含2444包、1349状态。在这些已成立分区与χ不变的条件下，`611≤D_pi≤629`、多状态任务224–230、χ灵活任务82–88；完整support的Dπ等仍为null。已知任务对固定744题边际的TV贡献分别为 `324361/20623680`、`585613/38301120`，不是准确率或完整干预剂量。

### 9.3 首次真实CUDA/保存恢复验收通过

三个seed都已完成正式首批forward/backward、有限梯度clip、一次AdamW更新，并从自己的step0001保存点实际恢复。三份acceptance均为 `CUDA_acceptance=true`、`same_actual_state=true`，恢复前后状态摘要一致；`additional_optimizer_steps=0`、`repeat_first_update=false`，未重新训练一遍“验证首步”。暂无该观测窗口内的数值、资源或执行失败。

| seed / GPU | 模型加载peak allocated | 首步验收peak allocated / reserved |
| --- | ---: | ---: |
| 11 / 6 | 14.20 GiB | 16.89 / 20.82 GiB |
| 29 / 1 | 14.20 GiB | 16.77 / 19.77 GiB |
| 47 / 2 | 14.20 GiB | 17.56 / 22.04 GiB |

这些是实际加载与首步窗口的测量，不是后续所有批次或长历史反馈的显存上界，也不是预先证明24GiB一定足够。首步证据保存在各 `prefix_training/seed*/shared/first_step_acceptance/record.json`。

北京时间 **13:27:42** 的只读快照：seed11已提交 **9/298**、seed29 **10/298**、seed47 **9/298**，三worker和父工作流仍存活。完整范围仍是744题/2468包；没有因6题分区未齐而缩成738题训练。该快照只读取已保存record，不加载state.pt，也不增加模型更新。

本轮当前已有真实训练保存点，但还没有298步完成、五臂分叉、C/N机制、dev883成绩或训练价值确认。到298时若6题仍未解决，程序会保存并释放本任务GPU等待，不靠继续Static超出原前缀来消耗资源。

### 9.4 费用收尾与预算边界

本批已知usage账本结算 **3.003354元**，新增UNKNOWN预留0。输入1416697 Token（hit18432、miss1398265），输出25760，总1442457。使用原历史峰值费率、逐请求微元向上取整，不是供应商账单核验。

最终全局已知结算1268.079741元、保留332.464128元、风险余量 **399.456131元**；审阅子额已知结算908.142538元、保留187.629568元、余 **204.227894元**。子额请求24656/25000，名义余344次不自动授权新一轮补问。历史UNKNOWN总152及保留额在部署前、终态和只读账本计数中守恒；本次未再逐条重hash历史152行。

CPU映射测量已经收口，GPU共同前缀继续运行。没有追加新API来补这6题，没有修改既有690权威、监督mask、模型或Loss。后续定点修订需保留上述来源和前缀等价边界；不能把运行中的Student表现反馈给映射判定。

### 9.5 收尾及运行快照原件

| 证据 | ID |
| --- | --- |
| completion_seal | `196b39ddfaafb3ad94f09ed3bd5f6b45f38a0760794026a9b40b11ff5501799a` |
| 完整材料阻塞结果 | `c97f506954473dad014092db997c1681364452583489d5ec6b798b31ab4491a1` |
| `report_run_01/mapping_annotations/record.json` | `157574211bdc5cbfaabb823ce0b4e86b6af0b351fd40737b37ae08c77500f35d` |
| `report_run_01/mapping_runtime/record.json` | `471d0ee2321d2885a821b105d7eb27639baab94b2ec1f8ff3334196e7deda564` |
| `report_run_01/prefix_progress_01/record.json` | `af22926859a578b6de9b5d12f61bd6f7348e33aa92fc3e95c601dbb49197f13d` |

只读进度入口为 `scripts/observe_finqa_v15_prefix.py --output <正式根目录>`，按真实提交目录与出生身份观测，不控制或重启进程。模型/Adam/RNG的state.pt只保留本地，不推送Git；报告与首次验收JSON可归档审计。

收尾版本对canonical映射控制器仅作括号排版修正，以通过仓库format检查；已经完成的API及仍在运行的prefix均继续使用上述冻结c0e339cf9e源码，不迁移任务、不关闭完整性校验、不改已有请求或保存点。
