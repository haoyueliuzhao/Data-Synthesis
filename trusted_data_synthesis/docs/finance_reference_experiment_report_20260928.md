# R2／G2／H2 实验报告：可见引用修订与单次 Direct-DSL 对照

## 一、结论与完成状态

**本轮已完成固定480会话和全部原生评分，执行与调用结算完整，GPU4／5／7已释放。可见短句柄已在真实任务中被成功使用，但多轮工具收益取决于模型：Base在H1-R下观察到更高原生分数，旧Static没有同向结果，且H1-R成本显著更高。不能据此确认新的训练收益或完整语义轨迹资格。**

Base/H1-R execution为17/120（14.17%），高于Base/Direct-DSL的10/120（8.33%），净差+5.83个百分点；旧Static/H1-R为1/120（0.83%），低于旧Static/Direct-DSL的5/120（4.17%），净差−3.33个百分点。这是同一开发名册上的描述性对照，不是未见确认、等算力比较或工具使用的单因素因果识别。

G2的16次实际生成全部结算，16份同点严格回放全部通过；但四个合成实例均未满足事前规定的精确动作链。H2依据原登记的“CPU正控通过＋普通执行成立”条件启动，未事后放宽G2链路指标，也未补采。全部480条H2轨迹的完整语义支持仍为unknown。

本次只生成报告：没有修改harness、预测、评分规则或原始日志，没有重新评分、追加生成、调用API、收集训练材料或执行训练。

## 二、研究问题、数据与冻结协议

本轮承接 [R2/G2/H2事前登记与启动记录](finance_reference_revision_20260928.md)，针对上一轮已证实的call_id不可见问题，固定修订一次可见引用与通用程序说明，再比较有工具的H1-R和无工具的一次Direct-DSL。上一轮结果见 [原R/G/H报告](finance_research_experiment_report_20260928.md)，原480会话和4次G均未覆盖。

| 项目 | 本轮固定设置 |
|---|---|
| 数据 | 原FinQA 8281题快照中的同一120题calibration |
| 角色规划 | 1000 SFT／350 feedback／120 calibration保持不变 |
| 数据用途 | 这120题已经用于接口诊断，本轮称开发复测；不是未见测试集 |
| Base | Qwen2.5-7B-Instruct，零B LoRA表示的基座函数，固定seed11坐标 |
| Static | 旧Static seed11、step240；不是新FinQA训练模型 |
| H1-R | `bigfinance-derived-vtdo-v3`，可见rN句柄，原生工具调用，最多32次响应 |
| Direct-DSL | `finqa-direct-dsl-v1`，无工具、无已完成工具历史，一次完整JSON提交 |
| 公共合同 | 同一`finqa_program_v2`、原始公开表文、固定合成通用例子 |
| 解码 | 两侧greedy；每响应2048 token，上下文24576，无截断／修复／隐藏继续 |
| 分母 | 2模型×2条件×120题＝480会话；16个30题分片 |
| 调用上限 | H2：240×32＋240＝7920；G2另≤16，合计≤7936 |
| 评分 | 固定FinQA原生evaluator；正常缺失／非法预测记0，基础设施未知不记金融0 |

H1-R把短`result_handle`、`status`、`output`写入实际工具content；原输出、技术call_id、参数点摘要及run/episode/turn/attempt的独立invocation身份分别保存。`prev:rN.output.<path>`只读取本会话此前成功结果；失败、未知、未来及坏路径不猜测修复。

通用说明明确分开：variables中的完整引用、calculate的有限标量AST算式、Final中的线性FinQA DSL。合成Revenue120/90与无额外引号的行名例子不取自待评题gold；它们是说明，不是已为当前题执行的工具历史。实际金融题不强制list_sources或read_source。

Direct只接受一个完整对象，包含answer/program和可选scale；不剥围栏、不提取子串、不修程序、不由答案反造程序。它与H1-R最大调用预算不同，研究的是两种明确执行协议下的结果与代价，不是同计算量下的优劣。

- 执行源码：`88ca246abdba217f217afb5edd679d1e391a9d34`。
- 协议ID：`2c8fdc96d6c3cfae31cf8055bfb74737e00b441779a8b169bbd4cc33d14528d2`。
- FinQA snapshot：`451490cf732399ee79c689933b56eb698837ed5370219d6f47c75938ec04368f`。
- Base参数摘要：`7659b963dc0740351280b648764bd12f339d74bb7515b9429b4e8213776b434b`。
- Static参数摘要：`1846eb7b9089c1590d1bcd73493c7e7b2f996ec10dd0942ab3d97b6fb9791cb7`。
- FinQA原生evaluator版本：`0f16e2867befa6840783e58be38c9efb9229d742`，算法未改。

未执行FinQA test、TAT-QA、FinanceMath或MultiHiertt；不新增外部泛化结论。新API约束仍是deepseek-flash，本轮实际API调用为0。

## 三、完成时间、分母、资源和唯一调用身份

以下均为北京时间2026-09-28。

| 事件 | 实际记录 |
|---|---|
| G2开始 | 12:48:09 |
| G2完成／H2第一批开始 | 12:53:52 |
| 最后H2 worker完成 | 14:13:58 |
| 全部worker退出并全局封存 | 14:14:03 |
| 全部原生评分完成 | 14:14:41 |
| H2开始至全局封存 | 约1小时20分11秒 |
| 封存后CPU评分 | 约38秒 |
| H2真实模型调用 | 4822／7920 |
| G2真实模型调用 | 16／16 |
| 两阶段合计 | 4838／7936 |
| API／真实optimizer.step | 0／0 |

17个作业（G2＋16 H2）都只有attempt01，启动及完成记录完整，全部COMPLETE。480会话全部已结算；H2的4822次returned调用具有4822份实际回执和4822个唯一模型调用invocation身份，没有缺回执、未知调用或基础设施失败。分片全部完成、worker退出后才开始本轮参考评分。

技术call_id仅有4621个唯一字符串，内容寻址重复不等于执行重复；新独立invocation身份完整区分了4822次真实执行，不将重复字符串去重计费／计调用。

实际使用GPU4／5／7，其他项目GPU0–3和6未中断。此前GPU5／7各约50秒的用户授权占位已在正式worker驻留后释放，调用与优化步均为0；没有遗留空占位。14:33只读检查时，本项目worker均已退出，NVML也无本项目GPU进程。不能据此声称其他项目的GPU空闲。

GPU5／GPU4／GPU7上最后一个本项目worker完成记录分别为13:54:38、14:04:41、14:13:58；这些不是精确到毫秒的CUDA显存释放时刻，全局14:14:03封存确认全部退出。H2各worker的started→outcome墙钟和为12648.67秒（3.514进程小时），G2另342.32秒；这包含加载、运行、回放和进程内等待，不是CUDA内核忙时或能耗。

上一进度估计为14:20–14:45，实际生成比该窗口下界早约6分钟；该估计是条件耗时与固定队列外推，不是截止时间保证。

## 四、R2与G2：哪些验证成立，哪些没有成立

R2代码冻结前，304项CPU集成测试通过（12.15秒，无失败或跳过），包含真实Qwen模板可见句柄正控、错误／未来／跨会话引用反例、Direct严格提交、正常缺预测政策及先生成后评分屏障。这些测试不等于金融准确率或训练价值。

G2在旧Static真实点与明确的诊断虚拟点各运行normal/error_recovery合成例子，每例上限4次，T=1、top_p=1、top_k=0、输出上限256。虚拟点是零矩AdamW与固定小梯度数值诊断，不是FinQA总体梯度，不继续旧优化器状态，不执行真实更新。

| 参数点／样例 | 次数 | 终态 | 事前精确动作链 |
|---|---:|---|---|
| real／normal | 4 | final_answer | 失败：额外list_sources |
| real／error_recovery | 4 | no_tool_call | 失败：末次JSON封套非法，无Final |
| virtual／normal | 4 | final_answer | 失败：额外list_sources |
| virtual／error_recovery | 4 | max_steps | 失败：末次仍calculate，无Final |

16份实际输出的同点logP／可微回放全部通过，最大绝对误差均为0，保留原token及实际EOS，包括错误响应；仍用atol=1e-6／rtol=1e-5。真实参数、模式、RNG和优化器状态隔离检查通过。G2运行耗时340.57秒。

因此本轮明确区分：`scripted_controls_passed=true`、`eval_native_passed=true`、`feedback_replay_passed=true`，但`real_reference_chain_passed=false`（精确链0/4）。模型行为未满足诊断要求，没有换例、补采、增加第17次或放宽条件。H2按事前普通执行门槛开展开发复测，不是事后把精确链失败改成通过。

精确序列检查会提前返回，G2中初始化的`observed_prev_reference_used=false`及局部可见性false不能直接解释为真实“从未使用／看不见引用”。独立局部观察：real/normal虽多一次list_sources，但实际2881-token输入可见r2，变量prev:r2成功算出30，实际3008-token输入可见r3，并通过prev:r3提交Final；原token往返一致。real/error_recovery虽纠正了错误读取，但可执行计算封套使用的是字面120/90，不能因输出前缀提到prev就认定使用了引用。保留这些描述与原严格判定，不回写旧字段。

## 五、固定分母下的官方结果

四条件均为完整120/120可评分，未出现unsupported或参考矛盾。native status=scored是“预测程序可以执行”的数量，不是主指标分母；正常非法预测也有合法零分。

| 条件 | Execution accuracy | Program accuracy | 显式Final | 可执行程序 | 精确Final诊断 |
|---|---:|---:|---:|---:|---:|
| Base／Direct-DSL | 10/120（8.33%） | 7/120（5.83%） | 118 | 28 | 12/120（10.00%） |
| Base／H1-R | 17/120（14.17%） | 12/120（10.00%） | 71 | 36 | 20/120（16.67%） |
| 旧Static／Direct-DSL | 5/120（4.17%） | 4/120（3.33%） | 119 | 17 | 13/120（10.83%） |
| 旧Static／H1-R | 1/120（0.83%） | 0/120（0%） | 6 | 2 | 2/120（1.67%） |

官方execution检验预测程序的执行结果，不自动验证单独answer字段是否正确；program检验程序等价性。精确Final是项目派生诊断，不能替代官方指标，也不自动归一化单位、scale或百分号。显式Final只代表提交终态，不代表金融任务完成。

### 同题配对比较

以下方向均为H1-R减Direct-DSL；只是完成后的描述性配对，没有事后增加显著性检验、多重比较择优或因果声明。

| 模型／指标 | 共同正确 | 仅Direct正确 | 仅H1-R正确 | 共同错误 | 净差（百分点） |
|---|---:|---:|---:|---:|---:|
| Base execution | 6 | 4 | 11 | 99 | +5.83 |
| Base program | 4 | 3 | 8 | 105 | +4.17 |
| Static execution | 0 | 5 | 1 | 114 | −3.33 |
| Static program | 0 | 4 | 0 | 116 | −3.33 |

Base在本设置中增加7个execution正例净数，但并不是Direct正确题全部保留再新增：4题Direct独对、11题H1-R独对。Static方向相反，不能合并两模型宣称工具统一有益。Base和Static是两个固定参数点，不是多个训练种子；本轮没有新训练，不确认VTDO、C/N、Novelty或训练分布优化收益。

## 六、失败漏斗与程序表达

| 正常模型结果类别 | Base Direct | Base H1-R | Static Direct | Static H1-R |
|---|---:|---:|---:|---:|
| 无合法Final | 2 | 49 | 1 | 114 |
| 程序容器／结构非法 | 52 | 7 | 36 | 0 |
| 程序不能执行 | 38 | 28 | 66 | 4 |
| 程序可执行，交官方指标 | 28 | 36 | 17 | 2 |
| 合计 | 120 | 120 | 120 | 120 |

作为**运行漏斗而非统一benchmark分数**，480=166无Final＋314有Final；314=95结构非法＋136不可执行＋83可执行。工具负担消除后，Direct的Final率接近100%，但两个模型的可执行程序仍只有28/120和17/120，说明程序表达／执行语义问题并未自动解决。

Final与预测program的原始精确一致性：Base Direct为6一致／22不一致／92不可比；Base H1-R为32／4／84；Static Direct为6／11／103；Static H1-R为2／0／118。这是原始数值或字符串比较，不做事后尺度修复，不能把所有“不一致”都解释为金融矛盾。

## 七、真实调用成本与终止行为

| 条件 | 模型调用 | 平均调用／题 | Final | 达响应上限 | 无工具调用终止 | 工具错误／工具事件 |
|---|---:|---:|---:|---:|---:|---:|
| Base Direct | 120 | 1.00 | 118 | 2 | 0 | 0／0 |
| Base H1-R | 1792 | 14.93 | 71 | 39 | 10 | 1370／1782 |
| Static Direct | 120 | 1.00 | 119 | 1 | 0 | 0／0 |
| Static H1-R | 2790 | 23.25 | 6 | 84 | 30 | 2333／2760 |

Direct的max_steps是耗尽唯一响应的非法提交；H1-R的max_steps是耗尽32次响应，两者不能混称32轮失败。H1-R合计123/240（51.25%）到32响应上限；无工具调用终止不做JSON封套补救。Direct没有工具，0次工具错误不是它的金融能力更强的证据。

Base/H1-R约用Direct的14.93倍生成调用，获得+5.83个百分点execution观察差；旧Static/H1-R用23.25倍调用，分数反而低3.33个百分点。该比值是生成调用数比，不是FLOPs、费用、能耗或等预算效率比。每次prompt长度和输出长度不同，token与进程时间另列于机器汇总。

| 条件 | 输入token累计 | 输出token累计 | Worker墙钟和（秒） |
|---|---:|---:|---:|
| Base Direct | 466989 | 4974 | 383.81 |
| Base H1-R | 11477346 | 80161 | 4416.32 |
| Static Direct | 466989 | 4303 | 352.66 |
| Static H1-R | 18996217 | 139651 | 7495.87 |
| 执行量合计 | 31407541 | 229089 | 12648.67 |

Token取实际回执长度，每次重送的历史重复计入输入，不是去重数据集长度或API账单。H2没有任何响应达到2048输出token上限；当前主要消耗来自多轮失败／重复计算，不是普遍输出截断。上表合计仅是执行成本，不合并成跨模型金融总分。

每题执行耗时（不含worker加载，P95使用nearest-rank）：Base Direct平均2.04秒／中位1.96／P95 2.89；Base H1-R为35.53／17.96／88.18；Static Direct为1.79／1.71／2.63；Static H1-R为61.11／74.95／111.10。它们受本机并发负载和具体输入影响，不作为通用推理速度benchmark。

H1-R主要工具错误：Base有1165次把prev直接放入expression，117次不支持的算术语法／变量、34次非法十进制值（工具说明不自动清理单位或逗号）、32次路径不存在；Static相应为1333、108、668、194次。这里统计的是错误信息类别，不把所有非法十进制值都断言为同一数据原因。其他较少类别见机器汇总，不能把四个类别小计当作全部工具错误。

## 八、短句柄实际使用与局部失败实例

### 8.1 有成功引用，但没有自动获得完整轨迹资格

只统计真正会被解析的参数位置中的完整prev字符串，例如calculate.variables，不统计说明前缀、expression中的非法嵌入或Final.program里的普通提交文本。按此口径：

| H1-R模型 | 含引用变量的计算动作 | 成功工具动作 | 失败工具动作 | 有成功引用的独立会话 |
|---|---:|---:|---:|---:|
| Base | 297 | 12 | 285 | 10/120 |
| Static | 1604 | 70 | 1534 | 15/120 |

这不是内部解析器实际运行次数：有些动作先因expression非法被拒绝。82个成功calculate引用事件的解引用实参重建与记录一致，其中Base涉及25个引用字段，Static139个。本轮H2没有成功的Final.answer短句柄引用；program中出现prev不算成功引用。

独立CPU核对了这82次实际输入回执：解码后重新编码与原prompt_input_ids逐项一致，被引用的rN、status=ok及对应原输出均确实在输入中可见，Base12/12、Static70/70均通过。该实证范围是25个会话中的82次calculate动作，不是全部480条任务的完整语义验收，也不是修复后已掌握所有引用／算式／DSL语言的证明。

Static的70次成功引用集中在15题，其中两个任务分别重复成功24、27次；不能把70当成70道独立成功题。Base成功引用会话终态为8 Final＋2 no_tool_call；Static为2 Final＋11 max_steps＋2 no_tool_call。工具引用可以成功而任务仍不结束，工具执行成功也不能认证金融语义支持。

### 8.2 典型观察（选择用于解释，不替换分母）

- ETFC/2013/page_84.pdf-1，Base/H1-R已获得可见r2，但把`prev:r2.output.content...`仍嵌入expression，连续30次收到“把引用放在variables而不是expression”的错误并耗尽32轮。不能把该例描述为旧不透明ID缺陷仍然存在。
- 同题Base/Direct仍交多层嵌套的`table_sum(table_min(...))`形式，官方指标为0；没有多轮引用负担也不保证线性DSL表达正确。
- 同题Static/H1-R首响应缺少`</tool_call>`，按原严格规则no_tool_call，未修复、未重采。
- GS/2012/page_186.pdf-4，Base/Direct的预测程序`subtract(399928, 457027)`两项native正确，但answer也填了同一DSL字符串，而非数值，因此精确Final不正确。程序正确、Final字段正确与完整轨迹正确是不同判定。
- JPM/2012/page_157.pdf-2，Base/H1-R在4次调用后execution正确，但计算实际使用字面`8/261`，没有prev；这个正例不能充当实际引用链成功证据，也无需因为没有引用而否定原生分数。

## 九、与上一轮的关系及研究边界

同一120题上，旧H1→H1-R的Base execution从2到17，Static从1到1；这是联合修订后的开发观察。新版本同时改变了可见输出、引用合同及三语言公共说明，不能把全部差异归因于“仅补一个ID”。上一轮H0也不是本轮Direct-DSL，不将两者混同为同一baseline。

本轮已经回答了一部分问题：工具路径在真实调用中可用，并且Base的有工具协议下观察到更高程序主指标；但使用收益不是模型无关的，成本与循环失败仍突出。Direct使高Final率与低程序可执行率的区别更清楚。数据不支持“所有金融计算都错了”“修好ID就解决程序表达”“开源BigFinance整体无效”或“新训练已经有收益”等结论。

**480条H2轨迹的complete_semantic_support仍全部为unknown。** 原生正例、正常结算、成功引用或G2数值回放都不能自动成为CompletePass，也不能直接将本轮轨迹投入新的SFT材料池。没有分布更新、真实optimizer.step或新Static/Delayed-C对照，不改变旧B确认尚未确认正向效应的结论。

后续建议（未执行、未自动登记训练预算）：

1. 保持原题与内核，固定有限资格及Mapper规则；优先解决已观察到的共同工具／DSL格式适配，不继续无限提示调优或单纯扩大到64轮。
2. 若开展学习，所有π条件应获得相同工具／格式适配或共同Static前缀，再比较训练分布；不能只给候选臂额外示范。旧Static只作迁移诊断，不能充当新FinQA正式训练baseline。
3. 不要求基座先有很高准确率才允许学习，但训练材料的语义资格、失败／unknown保留及API Probe／Student编码／真实反馈回执分离仍须满足；不把正确程序反造为真实完整工具轨迹。
4. 后续在这120题上的调整继续标为开发复测。冻结候选方案后再登记独立确认；不反复打开test或外部集择优，也不把未来新QA结果回填旧实验。

## 十、可审计交付与复现

原运行目录：`/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/reference_revision_01`，约2.2GB，保留在服务器，不将全量逐轮长文本推入Git。

- [机器汇总与证据清单](../artifacts/finance_research_20260928/public/reference_revision_report_01/summary.json)：四条件结果、配对、分片时间、成本、调用身份、引用统计、G2记录和原文件摘要。
- [480会话逐题指标](../artifacts/finance_research_20260928/public/reference_revision_report_01/per_task.tsv)：固定分母、原生原因、终态、实际调用与token、会话hash。
- [报告脚本](../scripts/report_finance_reference_revision_20260928.py)：读取已有sealed episode和原评分，零模型调用、不打开private.references、不重新评分；不改旧报告脚本或旧运行源码。
- [报告辅助测试](../tests/test_finance_reference_report.py)：3项小测试通过，Ruff检查通过；正式实盘汇总与独立只读统计一致，没有重复运行模型或原生评分。

机器汇总ID：`cb1149fe42ed79cbb64df0d518dccd580c1d067a952567d89e8bce3e674dc7ed`。报告脚本SHA-256：`36220a350a690da1fa51882db5bf7af34124d76511e8afc8d5f8dae3f9b27afb`；所复用且未修改的旧报告帮助函数脚本SHA-256：`27618360549996b8257f6073d92032659e4a8a07226bd823984e64d27cf038f7`。逐题TSV为480行数据加1行表头。

协议文件SHA-256：`b1663cc181789509db4728debfe86a7b0ac1cde93093e04538cdd907f3ebcb0c`。G2结果文件SHA-256：`ef920aa86272dc5cd1866941908a5b7b0ac23b190abcf665217f62de369554ae`。其余原始记录及480会话摘要在机器汇总中列出。

复现命令（使用新的输出目录）：

```bash
PYTHONPATH=trusted_data_synthesis/scripts \
/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/.venv/bin/python \
  trusted_data_synthesis/scripts/report_finance_reference_revision_20260928.py \
  --run /data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/finance_research_20260928/reference_revision_01 \
  --output /tmp/finance-reference-report-reproduction-20260928
```

本报告采用完成后的描述性汇总，没有事后增加显著性检验、按结果删题、选择成功分母或更改原生评分。任何进一步实验均需新的明确登记，本次未启动。
