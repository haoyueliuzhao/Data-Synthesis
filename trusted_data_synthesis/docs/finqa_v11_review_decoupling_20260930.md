# V11 审阅损耗分解与前瞻解耦修订（2026-09-30）

## 本轮实测结论

**已完成一次5719包/11438侧的零API全量诊断、真实材料的条件数学核对，以及前瞻解耦合同的纯CPU控制。主导的已测损耗是A输出触顶和B精确引用坐标，而不是已能完整读取的A辅助span失败。**旧批0.9442%是双侧完整标注准入率，不是轨迹真实有效率。

A侧5246/5719份返回的finish_reason为length且completion达到上限，占91.73%；其中5115份发生在2048上限、131份发生在4096上限。B侧2303份首失败发生在process引用检查，其中2286份是指定原段内存在唯一精确quote、但start/end错误。A核心声明和证据可独立读取、仅被辅助结构/投影失败覆盖的可观察子集为5份，不能将此前源码反例泛化为本批主要损耗。

新合同减少重复定位元数据并拆开层间状态，已通过离线控制；**没有修补旧截断JSON、没有重新标记valid、没有新付费审阅或五臂训练，不能声称91.73%的截断已经解决或真实准入率已经提高。**

## 审计驱动的范围

本轮遵循用户提供的《V10审阅低准入率》审计：先用既有返回完成零API全量原因分解，再按实际损耗定点修订，不优先重映射44题，不再生成8000条，不调整C/N，不删除unknown或人为拆分同义状态来制造五臂自由度。

审计正文SHA256：`e387ec1a45df2253eecd4c33c9b39bbf32071ef8007d2fcf564711356f19f686`。正文所链接的ZIP和完整Markdown未实际附在本会话；本仓库新增的只读统计器是按已提供正文要求实现，不冒称运行了未取得的作者脚本。

本轮执行期间另收到补充审计，正文SHA256：`47fdc4c57ccccb0cfea631375c4568e61066c5e75e4efacbb1ac0c4e3613e4ff`。其服务器派生目录`/tmp/v10_review_readonly_audit_20260930_bhrxlws0/`确实可读，已与本轮诊断逐侧对照；下述补充对照未改变初始登记、原结果或付费边界。

正式离线登记：`v11_review_decoupling_01/registration/record.json`，ID `3fcf794e5832b31e78cb82e2b19f05b97db396cf3ac0e3c7a93a858e51c69886`。固定读取V10原1000题/8000槽中的5719个原生正确包及11438个最终审阅侧，优先使用原review seal指定的唯一终态，包含此前合法登记的attempt2；不得从尝试中挑更有利结果。

本轮不打开真实钱包，不使用API/GPU，不重评FinQA，不重新生成标签或训练材料。旧V10代码、54包/44题、所有失败与UNKNOWN预留、映射与材料阻塞结果全部保留。新增模块只用于只读诊断和前瞻纯CPU候选合同，未接入原生产管线。

## 需要区分的四层

| 层次 | 保存什么 | 不能混淆成什么 |
| --- | --- | --- |
| 原始过程声明 | 四项status及原始模型表述 | 金融真值、已经验证的valid |
| 关键证据绑定 | 每项必需证据是否能绑定真实原文/事件、绑定后的过程状态 | 辅助行为或监督坐标是否正确 |
| 辅助描述与监督投影 | 独立状态、错误位置、Host派生的坐标和可用监督 | 过程语义结论本身 |
| 训练准入 | 双侧过程、唯一A监督、完整映射/编码、非退化材料等全部后续条件 | 单次标注成功或CPU反例测试通过 |

V10合成反例与新的候选合同测试使用人工构造的公开轨迹，不是假称重新审阅真实FinQA。新合同即便显示某项过程检查通过，也不声称语义真值已证明或真实生产准入已生效。

## 零API全量诊断口径

- A/B各自分为saved valid、过程invalid、过程unknown、annotation_failed，形成4×4配对表，不假定两个审阅侧独立。
- 原始可完整解析JSON中的四项过程status与已保存inspection交叉报告；不通过正则拼补截断JSON，不把原声明valid计为被误拒的真实有效包。
- 分别定位首失败阶段及全部可观察引用问题，包括process关键证据、behavior、supervision的positive/context_only等；quote不存在、唯一精确quote但坐标错误、重复精确quote位置不明、segment不存在分列。
- 输出触顶/finish_reason=length独立报告，避免把由非正常工具完成包装出的JSON错误说成解析器故障。
- 固定在原注册顺序中取每类最多2个原件索引，不根据内容挑选有利案例。缺件、hash不符、分母或A/B/joint绑定不完整时，不发布“全量已经定位”的结论。
- 不重评分、不修补旧返回、不生成替代资格。诊断中的“定位表示问题”不证明原过程一定正确；存在的quote也不能自动证明其上下文含义正确。

## 前瞻引用与监督策略

Host提供从原文机械划分、可追溯回原segment的稳定单元ID，以及真实action_id/event_id。模型选择这些对象，而不再重复填写start/end和整段原参数长度；Host从已有原件派生坐标。原上下文保持完整，机械单元划分不是金融语义判断或新的参考DAG。

整单元引用只需稳定ID；必要的部分引用保留精确quote，必须唯一精确匹配。不得模糊匹配金额、拼接不连续文本、猜测重复位置或自动删除限定语。连续精确片段的存在本身不证明没有语义省略，不能把Host匹配结果宣传为金融语义审阅。

动作正向监督使用真实action_id，Host核对其事件、成功状态和完整原arguments。A仍是唯一监督来源，B只承担四项关键过程检查，不形成第二套mask。未经批准的内容默认不进入正向监督，不要求模型为每段context_only旁白重复生成精确字符坐标。

辅助behavior错误独立记录，不清除核心声明或已可绑定的核心结论。监督投影失败也单列，不能通过忽略失败直接开训；关键证据不足仍unknown，有依据的critical_error仍invalid。所有真实训练仍需另外完成正式版本登记、材料与非退化门控；本轮没有付费重审入口或自动续跑。

## 现有映射的条件性数学核对

核对的命题是：固定现有22项complete分区不变，且另外22题各只有一个包，只补齐这些缺项不能产生新的题内分布自由度。全部9个多包任务均已在complete部分，每题1个状态。

若这些单包题最终能完成合法映射，则每题仍只有1个状态，所以条件性D_pi上界为0。此结论不能改写原support中的null，也不表示22题的语义歧义已经解决；若输入基数或上述前提不成立，则不输出0。跨任务存在chi=0和chi=1，不构成同一任务内的Manual对照。

## 执行证据

全量扫描已在8个CPU进程下完成，用时31.589秒。所有5719对joint/最终A/B及独立请求、原返回、原Episode字节均通过绑定核对；最终侧来自11363个attempt1和原先唯一授权的75个attempt2，不择优。首失败重现与每份已保存inspection一致，最终交集准确复现54包/44题。没有打开钱包、重跑原生评分或发起模型请求。

全量结果目录为`v11_review_decoupling_01/funnel_audit_01/`，summary ID `d16e09629af7a5864e72ea270b1b1bf707317b711f1faa96feed5a13e1e6bd71`。`summary.json`给出频数和输入绑定，`sides.jsonl`保留11438侧逐条诊断，`pairs.jsonl`保留5719对联合索引，`cases.json`按固定顺序给每类最多2例，`manifest.json`绑定上述文件SHA和运行源版本。原API大体积返回继续留在V10目录，诊断行不是替代原API原件。

### A/B保存类别与完整交叉表

| 保存类别 | A（5719） | B（5719） |
| --- | ---: | ---: |
| valid | 125 | 3317 |
| 过程invalid | 5 | 25 |
| 过程unknown | 1 | 15 |
| annotation_failed | 5588 | 2362 |

| A ＼ B | valid | invalid | unknown | annotation_failed | A合计 |
| --- | ---: | ---: | ---: | ---: | ---: |
| valid | 54 | 1 | 1 | 69 | 125 |
| invalid | 0 | 1 | 0 | 4 | 5 |
| unknown | 0 | 0 | 0 | 1 | 1 |
| annotation_failed | 3263 | 23 | 14 | 2288 | 5588 |
| B合计 | 3317 | 25 | 15 | 2362 | 5719 |

5665个被旧联合规则排除的包中，5662个至少一侧annotation_failed；另外3个两侧标注都成功，但未形成valid/valid。这说明“标注成功”是当前巨大过滤环节，不证明这些5662个过程本来都正确。双方均有保存invalid的交集只有1包；这仍是模型审阅记录，不是独立金融真值裁判。

实际交集可分解为`54/5719 = (125/5719) × (54/125)`，其中B在A-valid子集内的valid比例为43.2%；不能用两侧独立概率相乘，也不能反推“两侧各约9.7%有效”。

### 原始status声明与保存结果

| 侧 | 原始四status可读后的描述性归约 | 保存valid | 保存invalid | 保存unknown | annotation_failed |
| --- | --- | ---: | ---: | ---: | ---: |
| A | valid声明 | 125 | 0 | 0 | 62 |
| A | invalid声明 | 0 | 5 | 0 | 2 |
| A | unknown声明 | 0 | 0 | 1 | 8 |
| A | 不完整/不合法status | 0 | 0 | 0 | 5516 |
| B | valid声明 | 3317 | 0 | 0 | 2210 |
| B | invalid声明 | 0 | 25 | 0 | 48 |
| B | unknown声明 | 0 | 0 | 15 | 48 |
| B | 不完整/不合法status | 0 | 0 | 0 | 56 |

完整JSON中的原status是可读的模型声明，不等于证据已通过；也不从截断文本正则拼出四项status。少量length终态的原JSON恰好可完整解析，仍保留length异常，不放行：A有5份、B有3份；其余length的JSON不可完整解析分别为5241、53份。

### 首失败位置与输出容量

| 首失败阶段 | A | B |
| --- | ---: | ---: |
| 非正常完成/JSON检查 | 5520 | 59 |
| schema | 14 | 0 |
| process证据检查 | 51 | 2303 |
| behavior证据检查 | 0 | 0 |
| supervision检查 | 3 | 0 |
| 无标注失败 | 131 | 3357 |

A的5520项第一类里，5246项是length后检查器按原规则收到空串所产生的包装错误；其余正常tool_calls里还有244项Extra data、28项重复JSON key、2项其他JSON错误。B对应56项length包装和3项Extra data。不能把所有这些包装错误解释为本地JSON解析器实现错误。

| 侧/原max_output_tokens | 请求数 | length且达到上限 |
| --- | ---: | ---: |
| A / 2048 | 5193 | 5115 |
| A / 4096 | 525 | 131 |
| A / 8192 | 1 | 0 |
| B / 2048 | 5718 | 56 |
| B / 4096 | 1 | 0 |

此前A容量公式`ceil(1.25 × (1024 + 原模型字符数/2 + 48×turns + 64×actions))`再取固定档位，令5193个任务落在2048档。其中5115个触顶，实测说明这项输出负载估计对原A合同严重不足。原合同需要重复生成原文quote、长ID、坐标和监督列表，其输出膨胀不能仅由原模型正文字符数的简单比例推定。

截断长度是右删失：知道“至少到达该上限”，不知道完整有效输出还需多少。2048/4096档对应的输入复杂度不同，并非随机对照；不能据这些数字宣布统一4096、8192或16384就足够。本轮没有拍定或投入生产新的固定上限，也不进行无上限续写。

### 引用表示问题与辅助耦合的证据边界

B的2303个process首失败中：唯一精确quote存在但offset错误2286、quote在指定原段不存在14、segment不存在3。跨全部可完整读取引用检查，共观察到B侧3912个“唯一quote但offset错误”的定位条目，分布在2290份侧记录；这两个数分别是条目数与有该问题的响应数，不能混为一类，也不认证其金融结论正确。

A侧原始关键过程结构可单独解析且其必要机械证据检查通过、首失败仅属于辅助层的可观察子集共5份，均为原valid声明：2份behavior额外字段错误、3份把source/observation选为监督目标。它们与B配对时，B valid有2份、B annotation_failed有3份。没有据此把任何一份旧unknown改成valid或补入共同核。

这5份不是“耦合影响只有5份”的总体证明：大量A输出已经截断，无法观察完整的后续注释。但它足以否定未经统计就把现有5588个A标注失败主要归因于辅助span坐标的说法。已测主导问题应优先按容量/序列化、引用表示处理，同时修正确实存在的层间耦合。

容量与配对补充原件：`capacity_diagnosis_01/record.json`，ID `5de77cb6119dcbae146bb798687b82542bec74e1e565d3e56a14cfd0431dc7c7`；来源为已发布完整`sides.jsonl`，没有重新读取原模型返回或重新判定。

### 与补充审计的逐侧对齐及13份分类差额

补充审计和本轮统计在全部11438侧的保存类别、finish_reason、max_output_tokens及completion_tokens上完全一致，A/B边际、4×4交叉、5246个A length和5662个涉及标注失败的排除包也一致。

补充审计将A未触顶返回分为261份raw JSON parse failure和16份其他标注失败；本轮按冻结严格解码器的首失败规则得到274份JSON层失败、3份监督输入域失败。两组总数同为277，不是遗漏样本。定点读取28个duplicate-key原返回并保留SHA后查明：

- 13份原arguments可被普通`json.loads`读取，但冻结严格解码器拒绝重复键。补充审计将它们列入其他标注失败，本轮列入JSON层失败。
- 另15份既有重复键，也有普通解析器无法接受的语法/多余数据问题，因此补充审计已经把它们计入261份raw parse failure。
- 补充审计的16份其他失败 = 上述13份重复键 + 3份source/observation监督目标违规。其11份缺必填字段与3份其他schema问题合计14，与本轮schema首失败总数一致。

普通解析器对重复键的后值覆盖行为不能用来恢复valid，冻结检查也没有放宽。原始声明交叉中，补充审计的A“all_nonnegative_NOT_verified”200份与本轮严格可读的187份差13，同样来自这些重复键；两者都不是经过金融真值验证的有效包数。

补充审计给出的未触顶A仍有342/473=72.30%标注失败，也与本轮一致。因此新方案不能只扩Token上限；同时需要紧凑输出、可靠引用和分层失败记录。这一问题属于DeepSeek审阅器的输出合同，不是Student的24576上下文或GPU不足。

补充对齐原件：`supplement_reconciliation_01/record.json`，ID `2ef4ccd9f5a2c8af7fd7bf11572605efd8ecf6d095cbe6c8d83c3e7a6d392fab`，含逐项duplicate-key索引、两种解析口径及来源hash，不改写两份原审计。

### 原冻结V10的5项合成复现

直接调用与冻结`f9cc690929`字节一致的`v10_process_review.py`，使用仓库既有合成轨迹夹具，实际得到：

| 仅改变的字段/条件 | 原过程声明 | V10保存结果 |
| --- | --- | --- |
| 原始基线 | valid声明 | annotation_succeeded / valid |
| context_only监督end加1 | 同一valid声明 | annotation_failed / unknown，parsed清空 |
| behavior证据end加1 | 同一valid声明 | annotation_failed / unknown，parsed清空 |
| 关键检查critical_error且引用正确 | invalid声明 | annotation_succeeded / invalid |
| 同一critical_error另加context_only end错误 | 同一invalid声明 | annotation_failed / unknown，parsed清空 |

最后一例说明此耦合不只隐藏潜在valid，也会隐藏原本可读取的invalid判断。因此实际全量诊断必须同时报告raw声明与保存标签，不得把所有表示失败统称为“有效轨迹被误拒”。以上5例不涉及真实轨迹重审、API或钱包。

原件：`v11_review_decoupling_01/v10_counterexamples_01/record.json`，ID `4bb407d4e89b50b235807855837ade2d133eb7c2df5cf4f6aa8114833170c936`。

### 真实54包的条件性结构证明已完成

数学核对读取47份原件并校验记录ID、SHA与原映射成员对应关系：44题/54包，其中22题complete覆盖32包，22题unknown各1包；全部9个多包任务均已complete且每题单状态。上述固定分区前提全部成立，诊断输出`CONDITIONAL_ZERO_BOUND_PROVED`、条件性`D_pi`上界0，而原support的`D_pi`仍为null。

这比“映射尚未完成，所以暂不知道能否形成非平凡分布”更具体：在不改变已有complete分区、只补另外22项的前提下，不能形成题内π自由度。此命题不批准重新拆分现有状态，也不声称未完成题已通过语义映射。

必要合成控制4项通过，包含未知题有多包/已完成题有多状态时不证明0、原件SHA被改变时拒绝，以及不改写原null。真实诊断原件`mapping_bound_01/record.json`，ID `1476cdec12f4726a43e894823776ea7b16c50bdec3cf42a325e7f88b783c607e`；执行绑定ID `127b77c055193153e265748e904f4567be98f6a032b96c9811c1717321d30d8a`。

### V11前瞻合同与整池反例已执行

新合同policy ID：`bde67ad13b2cdf7db3dc8660e7c788472cbdbd596ee9827b396e579a0740bc62`。同一合成公开轨迹和核心声明的实际对照：

| V11合成条件 | 原始声明 | 核心绑定后的过程状态 | 监督投影 | 实际生产准入 |
| --- | --- | --- | --- | --- |
| 完整基线 | valid | valid | complete | false |
| behavior引用错误 | valid | valid | complete，behavior独立failed | false |
| context_only引用错误 | valid | valid | failed | false |
| 关键证据引用错误 | valid | unknown | complete | false |
| 有据critical_error | invalid | invalid | complete | false |
| 有据critical_error另有辅助错误 | invalid | invalid | failed | false |

整体坏JSON仍为unknown并保留raw，不解析补齐或追溯修复旧length。投影未完成时其正向字符数/all-masked为null，不伪记为已确认零监督；B完全不提供投影。共同过程候选中的投影失败包保留在整池并形成blocked_slot_ids，阻塞整个候选池，不筛掉后用好包继续。reason0及空正向列表的单包不新增淘汰，后续实际编码/全池监督门另行负责。

必要CPU控制合计25项通过：全量统计器10、条件上界4、前瞻合同11；静态检查通过。另保存了上述合成运行表和原V10反例表便于审计，重叠场景不能作为额外独立金融样本计数。最终整池保留及null传播经过独立只读复核。新合同源SHA256：`bdd2cd7cd56f8d83980349d5e77c20b724bed5154fc85f599691a612f7928b93`。

前瞻运行原件`v11_counterexamples_01/record.json`，ID `e768ce44e12e61719f82d7279201c1940450fde5f8838a6f4f29ba3e710739b3`。这些结果不构成新的真实FinQA资格、mask、N或训练成绩。

## 已实施与后续边界

已实施的是只读归因工具、条件性结构证明、Host稳定引用及分层检查的离线候选实现；所有V10生产源码及原件未改写。未重映射44题、未新增8000条、未修改C/N、未人工拆状态、未开启任何API/GPU或训练队列。

数据支持的下一步优先级是：先完成A精简响应合同与工作负载相符的输出容量设计，同时减少B的重复坐标生成；保留过程/关键证据/投影分层和全共同池门控。单个JSON内部的分层检查不能让被截断的整个JSON恢复可读；如需物理分开过程与投影返回，必须在新生产协议中登记调用范围、容量、费用和来源绑定，而不是热改旧批。

该顺序与补充审计一致：A输出义务/容量 → B引用表示及失败分层 → 重新确认经验支持 → 检查真实题内分布差异。现诊断已将原finish/usage、`raw_JSON_error`、`first_failure`和监督层错误分开保存；后续生产需保留`OUTPUT_LIMIT_REACHED`、`RAW_JSON_PARSE_FAILED`、`LOCATOR_UNRESOLVED`、`SUPERVISION_REPRESENTATION_FAILED`等明确原因，不能再次只留下通用unknown或空串JSON错误。

本轮按审计明确要求停在零API原因分解和前瞻CPU修订。新生产审阅的输出容量、费用/请求数前检及正式登记尚未完成，真实准入率和五臂可区分性仍未验证；不将候选实现冒充生产问题已解除，不自动重发旧审阅或启动训练。

## 复算入口

从本仓库实现目录，使用已有venv与`PYTHONPATH=trusted_data_synthesis/src`：

```text
python -m trusted_synthesis.finance_research.v11_review_funnel_audit --root <V10原件根> --out <新的诊断目录> --workers 8 --expected-review-seal-id 0bf1566b086edc823e9c67b9e2838bcb1c788f6e47d608363dcf84fed7648844 --registration <V11登记record.json>
python -m trusted_synthesis.finance_research.v11_mapping_bound --root <V10原件根>
```

全量扫描已执行成功，无需为日常查看进度重复扫描；直接读取发布的summary/manifest/逐侧诊断即可。测试临时目录按AGENTS使用`trusted_data_synthesis/artifacts/test_tmp/`下独立mktemp子目录。
