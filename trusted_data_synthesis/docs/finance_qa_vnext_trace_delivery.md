# Flash/high 迁移诊断：自主求解与公开轨迹交付

## 1. 本轮问题、基线和范围

本轮依据审计 SHA-256 `65e04d26111844527256f1821eac93ba253cc5d750bf61b23fa2450c583b2325`
开展。基线为 `1282a57e255211ddf86ffc9bbfa016b23c573798`：原 Flash/high 为答案
9 PASS、2 FAIL、1 UNKNOWN、5 条完整轨迹；Pro/high 为 12 条答案 PASS、11 条完整
轨迹。该轮已通过限定审计，**不重跑、不回写历史、不再次做 Thinking 接入校准**。

本轮只检验：固定 Flash/high、已有自主执行器与数值评价 v2，在六个新的任务实例上，
明确“交付可核验的公开计算过程”，能否提高有效轨迹产量，同时保持答案质量和合理成本？
这是待检验假设，不预设指令必然有效，也不把工具调用增加直接解释成推理能力增强。

正确的直接 Final 仍是正确自主回答；若有公开推导但没有实际工具执行，不能说成“没有
公式／不会推理”。它只是未满足本轮可验证执行素材的定义。无筛选生成全部合格不是继续
研究或未来 VTDO 的必要前提；有效性筛选、任务边际、产量及完整成本需要分开记录。

本轮不增加 Pro 新参照，不混合历史 Pro 轨迹补齐 Flash，不做新商、Token 训练表示、
Student、GPU 或 VTDO。旧五条 Flash 及十一条 Pro 完整轨迹继续保留为各自条件的材料。

## 2. 唯一在线干预：固定 SYSTEM 追加

| 条件 | 模型 | 指令 | 会话数 |
| --- | --- | --- | ---: |
| A | deepseek-v4-flash，Thinking enabled／high | 原自主求解 SYSTEM，逐字保持 | 6 题 × 2 = 12 |
| T | 同上 | 同一 SYSTEM 后追加下列固定段落 | 6 题 × 2 = 12 |

T 的英文追加文本在所有任务、所有重复中相同：

```text
Your deliverable includes both the answer and an auditable public calculation.
Before a relevant calculation, or in the same calculation request, state the relationship you
chose, the meaning and source of its inputs, and any necessary unit handling. Use the calculate
tool to produce the result on which your final answer is based. You still choose the plan,
formula, evidence, calculation granularity, checks, and when to finish. No fixed sequence,
extra planning turn, lengthy explanation, or repeated calculation is required.
```

追加前隔两个换行；A SYSTEM 为 2,782 UTF-8 字节，T 为 3,313 字节。JSON 编码后，
相同初始材料的 T 请求比 A 多 538 字节。新增内容没有任务专属公式、数字组合、年度对应、
尺度因子或固定变量名，不要求计划提交回合。不能把 T 描述成“与 A 同一提示”。

实际执行代码保持更强的不变约束：prepare 从前轮冻结源码生成 A/T 两套 stdlib 执行
目录。worker.py、calculator.py、isolate.py、projection.py 两套均与前轮逐字相同；
A/common.py 也逐字相同，T/common.py 仅在末尾追加静态 SYSTEM 常量赋值。
没有根据 A/T 增加执行、验收或纠错分支。模型收到的题材料是同一文件；条件名不写进
题目、source IDs、公开数字目录或模型消息历史。

因此，T 不遵从交付要求时：没有 calculate 就 Final 仍立即结束；缺来源仍执行合法
算术；财务关系、符号、单位或答案错，不反馈重新生成。Host 不补公式、不补来源、不
代调用工具，不添加 Formula Gate、accept、强制 Schema 或额外催算回合。

## 3. 一次性固定的新任务面板

使用现有 `benchmarks/finqa/frozen/test.json`，完整文件 SHA-256：
`831dbfb2e785dbc227f895ce3f24046433467aec67b09db2bd6ac7692a8a30dc`。
以下六个原问题、原页面、全部前后文、表格与全数字索引不作改写或 relevance 预选。

| 键／类别 | 原 FinQA ID | 观察对象 | 私有精确目标／答案单位 |
| --- | --- | --- | --- |
| N1 比例尺度 | INTC/2015/page_41.pdf-4 | 全球租赁面积／总设施面积 | `405/28` percent |
| N2 比例尺度 | ETR/2004/page_281.pdf-1 | 2004 资金池现金占用／应收余额 | `531250/7699` percent |
| N3 多期汇总 | JPM/2010/page_273.pdf-2 | 两年 × 现金及证券四项合计 | `689/10` USD_billion |
| N4 多期汇总 | K/2006/page_52.pdf-2 | 三年公司定义 cash flow 平均 | `8923/10` USD_million |
| N5 复合金额变化 | AON/2007/page_175.pdf-2 | 2006 重组负债净变化 | `18` USD_million |
| N6 复合金额变化 | JPM/2009/page_175.pdf-5 | 2008 对 2007 两类交易资产总额增量 | `58665` USD_million |

三类各两题、六个公司年度报告组、五家公司（JPM 两个不同年度），每条件各题权重 1/6。
N3/N6 不是同页或同一个数据问题；不把不同年度的同公司样本宣称为完全独立公司抽样。

在基线提交 `1282a57…` 上，以六个完整 filename 页号做固定字符串检查：src、tests、
docs，以及 artifacts 中 registration／task／panel／context JSON、public JSON 和
已保存 HTTP 请求 body 均无命中；同时排除旧十二题开发面板和旧六题的同页、近重复。
选择代理先作限域候选检查，执行代理再读六题完整原文、独立核对并用固定 Git 基线复查。
细节在运行准备记录 `panel_selection.json` 中封存。

这支持“未发现用于当前提示／运行调试”的限域声明，不是训练集未见或正式盲测认证。
旧 FinQA census 曾机械扫描全部来源；本轮不重做 census，也未穷尽所有历史临时文件、
外部会话和模型训练数据。

### 3.1 来源语义、精度和等价路线在生成前固定

以下均为**私有离线评价说明**，不发送给模型：

- N1：全球 leased 8.1 与 total 56.0 均为百万平方英尺，比例乘 100。允许区域相加，
  或正确利用 owned + leased 身份，不强制 global 列路线。FinQA 原 answer 为粗略
  `14%`，但独立目标约为 14.4642857%；不把粗 gold 替代本轮精确参考或放宽 v2 的
  0.005 上限。表格与重复正文一致，没有另一种更精细的同量来源。
- N2：正文 q0 的资金池现金占用 42.5 million，除以表格 t2c0 的 61592 thousand；
  表格第一列就是 2004 数值列。问的是 use 的正幅度，不额外取负；不能错配 2003。
  千美元表头明确，按披露精度精确计算，不声称真实经济量没有舍入误差。
- N3：q16 明确 2010／2009 cash 25.0／24.0 billion，securities 9.7／10.2 billion。
  四项成员须齐全，可按年份、资产类别或一次整式求和。问题原文要求 in billions；页上
  无关所得税表的 millions 不能套到这四个量。没有另一份更精细的同量表格。
- N4：平均的是表内公司定义 cash flow 957.4、769.1、950.4，而不是经营现金流行或
  年增幅行。p20 定义 cash flow = CFO 减 property additions，允许用各年 CFO 加
  有符号负资本支出重建。三年和为 2676.9、平均为 892.3。原手写 steps[0].res
  `1276.5` 是中间注释错误：957.4 + 769.1 实为 1726.5；原 program 和最终答案与
  独立计算一致，因此不把该错误步骤当作目标或必经过程。
- N5：可采用 `155 + (-141) + 4`，也可采用期末 134 减期初 116。二者同样有效，
  不要求三项滚动明细路线或多次调用。2007 活动不是本题输入，`-141 (141)` 不是
  两个不同数，首行 OCR `$2014` 也不是本题期初余额。
- N6：两类 trading assets 的 2008 合计 505519 减 2007 合计 446854；不取 2009，
  不扣 trading liabilities。原文 p0 明确 annual average balances，不要重新命名成
  年末余额。原问指定百万美元，增量方向明确。

九条来源财务恒等式均作精确验证；N1 区域重组、N4 CFO 加有符号资本支出、N5 余额差
均经离线符号等价复核。它们不是在线菜单、选定必要来源或新商；缺少自动来源绑定仍由
有限公开语义复核判定，不以同值猜测绑定。

预先考虑但未登记的 BDX/2018/page_106.pdf-3 是三年其他收入平均，替代 N3 会重复
平均结构；CME/2010/page_69.pdf-2 的估计总额与细项存在舍入差，故优先 N2。DG/2005
期间与原注释成员不一致、GPN/2013 近似旧股票主题，未纳入。不得按新模型结果再替换题。

### 3.2 新单位接线不改变数值评价

N3 原问使用十亿美元，因此在生成前增加 USD_billion 的财务单位同义词（包括 billion
USD、billions of dollars 及该金融面板的 billion(s) 省略表述）；缺 unit 且原问题明确
`in billions` 时可从原问题推断。此举与既有按问题推断 percent／millions 的逻辑同类，
**不转换模型发布数值，不把 million 等同 billion**。

这是新任务的单位词典扩展，不声称 normalize_unit 与旧代码逐字相同。其余八个核心
数值／符号／引文／轨迹函数保持前轮原文字节，包括 answer_score、trace_checks 和
display_compatible；percent／USD_million 的旧映射与 v2 数值规则不变。

## 4. 执行、资源与隐私的不变项

两波固定重复，每波十二个独立进程并行；第一波按题登记 A/T，第二波按题登记 T/A，
第一波全部结束后启动第二波。不依据答案、工具率、未知或成本调整分配。每个会话只读
自己的完整源文件和执行胶囊，历史、笔记、工具结果不共享。

| 项目 | A/T 共同边界 |
| --- | --- |
| 新会话／每格重复 | 24／2 |
| 每会话模型请求、工具调用 | 分别最多 32，错误调用计数 |
| 全批模型请求上限 | 768，不重试、不补样 |
| completion 上限 | 16,384，含 Thinking 和公开输出 |
| 完整请求 body／响应接收／公开内容上限 | 98,304 字节／2 MiB／1 MiB |
| 连接／单请求总时限 | 30 秒／180 秒 |
| 单请求预留 allowance／全批上限 | 115,712／88,866,816，不是实测收费 Token |

六题 A/T 初始 body 字节分别为 N1 24702/25240、N2 21058/21596、N3 27807/28345、
N4 29031/29569、N5 12637/13175、N6 15958/16496；长历史仍按同一上限处理，绝不
自动压缩或扩大预算。不降低 Thinking、不改采样参数、不回退 Pro、不因直接 Final 追加
“请再计算”。temperature／top_p 仍省略；JSON 路由、三个工具、连续完整公开历史不变。

复用已验证的内存投影：HTTP body 只在内存解析，落盘前提取公开 content 与受限遥测；
不保存私有 reasoning_content、其摘要或原 HTTP body。公开 content 按原字节保存，
明确标记“投影而非原 HTTP 原文”。私有内容不作为公式证据、商状态或训练目标。

finish_reason=length 仍单列 generation_truncated_length，保留公开残片但不进入普通
工具 JSON 纠错循环。stop + 空公开内容仍为未知；不能用此前工具结果补 Final，也不
根据私有推理长度把空响应解释成金融失败。

继续采用 `/usr/bin/python3 -I -S -B`、Landlock、无 site／仓库 evaluator 模块、
禁用 core dump，以及实际私有目标／canary 读取拒绝探测。Key 只经匿名管道传入。
父进程可准备私有参考，但在线隔离进程不获得评价模块、正确答案或其它会话文件。

## 5. 固定评价与标签遮蔽

答案与完整轨迹各按每题每条件 `/2`、条件总体 `/12` 报告。直接 Final、过程不足、
答案错误、截断和未知都保留在登记总体，不删未知改分母，不合并称为“模型算错”。

主 value 优先，缺少 value 时只能从实际 Final 的明确答案引文提取；不能改取较有利
字段，也不从私有目标填数。十进制容差仍为
`min(0.005, max(半个词法末位单位, 1e-12))`，精确分数严格相等。
其它答案字段仍按各自展示精度对同一精确参考检查，保留前轮 secondary 比较未加 0.005
上限的规则。Final 的方向、期间、文字解释和单位另行检查。

新增**仅用于诊断**的字段内部展示区间重叠检查：两字段各按其展示精度构造区间，判断
是否重叠；它不参与答案或轨迹 PASS 判定。secondary 对参考不符另记
`secondary_answer_reference_mismatch`，避免把“来源真实但精度不同”误称为字段互相
矛盾。这个诊断拆分不改旧评分，也不增加在线实验。

完整轨迹仍要求公开关系、输入含义与来源、必要单位处理在所选答案计算之前或同一请求
中可见，实际计算经独立复算，且最终发布一致正确。完整字面算式配明确公开角色、来源
注释可以接受，不强制命名变量 schema；只有裸数式而没有执行前对应说明，不能靠正确
答案或 Final 后补引文升级。来源自动绑定不成立不自动判财务错误，但不会静默补齐
机器来源 ID 或将数字相同当作模型声明。

准备时随机分配 R 编号，全部生成结束后才导出视图；其中只展示任务键、公开原话、计算
与终止记录，不展示 A/T、SYSTEM、成本或 usage。执行代理用实际引文作有限语义复核，
封存完整评价输入及 SHA 后才读取
条件映射、解码报告。行为风格可能透露交付指令，故仅称**条件标签遮蔽**，不称双盲、
独立人类专家评价或模型训练未见测试。引文核验只认证原话真实，不认证语义无偏。

## 6. 成本口径与有限结论

记录全部请求、失败、未知与截断费用；reasoning_tokens 缺失时未知，不补零，也不再
加到包含它的 completion 之上。报告缓存、输入／输出／推理 Token、公开字节、请求
时延分布与并行请求窗口，时延之和不是并行墙钟时间。

2026-09-09 再次核对 [官方人民币价格页](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)：
Flash 每百万 Token 的缓存命中／未命中／输出空闲费率为 0.05／1.5／4.5 元，高峰为
两倍。A/T 同为 Flash，不能沿用旧“不是 F 就乘 Pro 三倍”的分组费率分支。
按实际 cache hit/miss/completion 估算；没有账单接口，actual_billed_cost 保持 null。

条件全部会话费用除以完整轨迹数，才是单位有效轨迹成本；分母为零或费用缺失时不输出
有限估计。另列每答案 PASS 的成本。T 增加公开说明及工具使用可能增加费用，不预设
更省钱；有效轨迹产量提高才构成数据产出收益，成本取舍须一并披露。

若 T 在本面板提高完整轨迹产量且未观察到明确答案退化，可结合摊销成本将它选为后续
合成候选条件；不要求全部任务满分，也不把两次重复说成统计非劣性或稳定优越。
若只增加调用却无有效产出，接受该有限结果，不继续加 Schema、accept 或重试。
A/T 不事后混成一个生成分布，不拿新 T 对历史 Pro 作同期模型比较。

## 7. 冻结、局部检查与入口

新增接线、诊断与成本共 20 项零 Provider 控制，覆盖胶囊唯一差异、实际隔离执行、
首 Final、无来源算术仍可执行、请求参数与历史、公开字段白名单、旧 v2 数值函数不变、
billion 单位正反例、内部／参考一致性分离和零产出成本分母。另对六目标、九条财务
身份及主要替代路线独立复算。没有重跑旧全套控制或另作模型接口校准。

先完成新源码、任务、指令、评价与本设计的提交／远端冻结，再进行第一次正式调用。
source_snapshot 绑定全部已提交 Python 源码；准备、在线、评价、收口分别保存长度与
摘要清单。正式采集后不修改 evaluator 源码、选题或指令。

入口：`finance_qa_vnext_trace_delivery.stage` 的 collect、assess、closeout、verify。
`closeout --reviews` 读取完整 R 编号引证评价；不能覆盖已封存目录重跑。
新工件根为 `artifacts/qa_vnext_trace_delivery/flash_high_at_2rep_20260909`。

## 8. 正式结果：公开轨迹产量提高，代价须按有效产出比较

本节及后续为生成、遮蔽复核锁定和解码后追加，不修改前置设计、选择的六题或评分规则。
冻结提交 `fa81ce3b9da86e6231d32ca220b1bbca8bd2f538` 已在首次 Provider 调用前推送；
[design_at_freeze.md][frozen-design] 保留本说明前七节和结果占位的原字节。

**A 原指令为答案 9 PASS、3 UNDETERMINED、2 条完整轨迹；T 交付指令为 10 PASS、
2 UNDETERMINED、10 条完整轨迹，分母均为 12。** 两条件均无确定数值 FAIL，但这不
等于所有任务完成：五条 Final 没有可直接提取的预登记目标数字，必须保留未确定状态。

T 的完整轨迹产量由 A 的 2/12 提高到 10/12，增加 8 条、约 66.7 个百分点；答案 PASS
从 9/12 到 10/12。本次支持的结论是**公开过程交付指令在这个迁移面板上改善了符合
当前定义的数据产出**，不是模型内在推理能力提高或统计非劣性已经证明。

### 8.1 每题、每条件的固定分母

| 任务 | A 答案 PASS | A 完整轨迹 | T 答案 PASS | T 完整轨迹 | 其它状态 |
| --- | ---: | ---: | ---: | ---: | --- |
| N1 全球租赁面积占比 | 2/2 | 1/2 | 2/2 | 2/2 | A 一条无实际计算 |
| N2 资金池现金占用占比 | 2/2 | 1/2 | 2/2 | 2/2 | A 一条无实际计算 |
| N3 两年隔离资产合计 | 0/2 | 0/2 | 0/2 | 0/2 | 两条件各两条未确定：仅给年度小计 |
| N4 三年 cash flow 平均 | 2/2 | 0/2 | 2/2 | 2/2 | A 两条无实际计算 |
| N5 重组负债净变化 | 1/2 | 0/2 | 2/2 | 2/2 | A 一条答案正确但无计算，一条 Final 无答案数字 |
| N6 交易资产年度增量 | 2/2 | 0/2 | 2/2 | 2/2 | A 两条无实际计算 |
| **合计** | **9/12** | **2/12** | **10/12** | **10/12** | 未删未知、未补样 |

全批 24 条均提交了 Final，最终答案为 19 PASS、5 UNDETERMINED，完整轨迹 12 条。
原始逐条判定在 [正式收口报告][closeout-report]；成本和行为的可复算加和在
[解码后描述性汇总][derived-summary]。A/T 仍是两个生成条件，不把通过样本混为同一分布。

### 8.2 N3：年度小计正确，但预登记跨年量未交付

四个 Final（A_N3_01／02、T_N3_01／02）均给出：

```text
2010: 25.0 + 9.7 = 34.7 billion
2009: 24.0 + 10.2 = 34.2 billion
```

它们的年度、资产类别配对、单位及这些小计均正确。但运行前登记的是四项跨年合计
68.9 billion；四条都没有发布这个数字。两个 T 会话各实际调用两次计算，分别得到
`347/10` 和 `171/5`，没有计算或公布二者合计。因此不选某个年度的 tool:1／tool:2
冒充目标计算，更不由 Host 离线补一次加法成为模型答案。[T 原公开轨迹][n3-trace]

按冻结缺数规则，主要 published_value 保持 null；Final 的完整目标一致性与完整目标
公式关系记 NOT_ESTABLISHED，任务为 UNDETERMINED，而不是把它们写成四条金融算错。
年度小计是两个不同语义量，不当成同一跨年答案的 secondary 字段逐个对 68.9 比较。
它们真实、正确的局部关系及工具执行仍完整保留。

**解释边界：**原问 “in 2010 and 2009 ... total fair value” 自然语言上也容许按年度
分别报告 total。模型输出与这种解读相容，这是目标聚合范围／问题解释差异的合理解释，
不是从私有 Thinking 得到的动机证据。运行前已锁定 FinQA 的跨年合计口径，不能在看到
四条年度回答后改口径使它们通过；但同样不能宣称该跨年口径已由本轮证明为唯一自然解读。
后续需要独立审阅这一题义边界，本轮不换题、不改问、不改分。

### 8.3 N5：对话中有正确数字，也不等于实际 Final 发布了答案

A_N5_02（R024）的第 0 条公开响应写出 `134 - 116 = 18 million`，带正确来源与单位，
但没有 final 或 tool 字段；执行器按既有规则记录普通公开消息。第 1 条响应仅为：

```json
{"final":"Task complete."}
```

按已冻结的 Final-only 数字提取规则，不把前一条公开消息里的 18 搬进 Final。因此
published_value 为 null、答案 UNDETERMINED、无完整轨迹。这不是缺少公开公式，也
不是模型在整个对话中从未给出正确答案，而是**终局提取边界未满足**。[完整公开记录][n5-no-final-number]

两个 T/N5 则自主选用了预先允许的更短路线：分别提交 `ending_2006 - ending_2005`
和 `closing_2006 - opening_2006`，变量绑定 134 与 116，真实计算 18 后提交 Final。
没有被迫使用 `155-141+4` 或多次计算，两个会话均为完整轨迹。[T 原计算请求][n5-short-route]

因此，A/T 的一条答案 PASS 差异涉及终局发布边界；不能据此推断模型算术能力提升。

## 9. 实际行为：不把工具率当作全部收益

### 9.1 请求与动作闭合

```text
44 次模型请求
= 16 次真实 calculate 请求
+ 24 次 Final
+ 3 次进入工具执行之前的 JSON 接口错误
+ 1 次无工具、非 Final 的公开消息
```

| 实际行为 | A | T |
| --- | ---: | ---: |
| 模型请求 | 16 | 28 |
| 首条响应直接 Final | 8 | 0 |
| 会话终止时无任何成功计算 | 10 | 0 |
| 答案 PASS 但无实际计算 | 7 | 0 |
| 真实 calculate | 2 | 14 |
| 真实计算独立复算正确 | 2/2 | 14/14 |
| 其中完整目标的已验证轨迹 | 2 | 10 |
| JSON 接口错误 | 1 | 2 |
| 算术工具错误 | 0 | 0 |

报告中的 `direct_final_without_calculation` 沿用“Final 时无计算”的宽计数，其 A=10
**不是十条首轮直接 Final**：其中八条首轮结束，另有 A_N3_02 先遇 JSON 错误和
A_N5_02 先发表普通公开消息。描述性汇总已另列准确的首轮 Final 计数，未回写冻结报告。

T 不只是多调用了工具：N1、N2、N4、N5、N6 的十条都留下了执行前关系／输入对应／
必要单位、真实计算及正确发布。N3 四次工具计算则只得年度小计，仍不计完整目标产出。
这两种情况分开统计，才构成对“可用轨迹产量”的测量。

三个 JSON 错误发生在 T_N1_01[0]、T_N6_01[0]、A_N3_02[0]，对应原文分别包含
未加引号的 `81/10`、JSON 数值位置的 `384102+121417` 等表达式，以及不完整 JSON。
三次均没有进入 calculate、没有产生算术结果；下一请求收到的只是实际 parser
interface_error，没有正确公式或答案提示。

T_N1_01 随后把变量值改为合法的 8.1；T_N6_01 将算术移入 expression，二者各执行
一次原先意图的关系并正确结束。A_N3_02 则转为发布年度小计。这是两次成功的**接口
格式修订**和一条转入 Final 的记录，不是财务方法失败后的自主重新规划；也不是网络重试
或批次补采样。[N1 格式修订轨迹][json-repair]

没有调用 read_source 或 notebook，没有跨计算 result_id 复用。T/N3 的两次加法均是
直接取源的独立计算，不构成中间工具结果复用。全批 33 个表达式运算节点不是 33 次旧
原子动作。本轮不据此宣称复杂检索、一般规划或财务纠错能力成立。

### 9.2 来源认证与有限语义复核保持分开

| 证据 | A | T | 边界 |
| --- | ---: | ---: | --- |
| 完整目标公式适用性 PASS | 9/12 | 10/12 | 含仅公开文字、未执行的正确关系 |
| 有限变量／来源对应 PASS | 11/12 | 12/12 | N3 的正确年度输入对应也保留，不等于完整目标完成 |
| 有限单位处理 PASS | 11/12 | 12/12 | 与实际 Final 是否交付目标分别检查 |
| 自动 source_symbolic_target_match | 0/2 | 3/14 | 以实际计算为分母，不把非匹配都判错 |
| 实际消费命名变量的计算 | 0 | 5 | 其它是字面算式，可能带未消费的来源注释 |
| 执行—完整发布对应 PASS | 2/12 | 10/12 | 不能由正确答案反推真实执行 |

T 的十条完整轨迹并非十条全部自动来源认证：大量正确字面算式仍依赖公开文字和原文
的有限语义核查。反过来，N3 的年度计算有正确来源绑定却不匹配跨年目标，不能据此
判为输入捏造或算术错误。

A_N5_01 的 Final 只有 `18 million`，答案可以通过，但公式、输入对应与输入单位处理
未建立。与之不同，其余多条无工具回答已经包含正确公开推导。A_N1_02 和 A_N4_02
还将 public_document／task 标识放进 result_id；这些不是实际工具结果，执行—发布
对应 FAIL，但数字答案是否正确继续单独评分。

### 9.3 标签遮蔽与判定封存

执行代理完整阅读全部 R 视图后，于北京时间 2026-09-09 20:11:36 封存评价输入，
SHA-256 为 `13fc28577db56fdb61cb4f7154b96e4b4809ae2c6ef2300391b58791b8a6c126`。
全部逐字引文、Final-only 提取、主要 value 不替换、secondary 显示检查均已在解码前
验证。见 [评价锁][review-lock]、[完整评价输入][masked-reviews] 和 [编写记录][review-authoring]。

五条缺目标数字案例另请一个辅助代理在同样遮蔽条件下作有限边界检查，建议与最终
UNDETERMINED 判定一致；该代理曾参与 evaluator 接线，**不独立于实现工作，也不是
人类专家**。[边界检查说明][peer-check] 不作为自动语义认证。公开风格可能透露条件，
本轮没有保证真正双盲；所有语义判定在打开条件映射及实测成本前锁定，解码后未调整。

## 10. 全部成本、遥测与时延

### 10.1 真实用量

| 用量 | A | T | 合计 |
| --- | ---: | ---: | ---: |
| 输入 Token | 93,773 | 173,499 | 267,272 |
| 缓存命中 | 57,472 | 132,352 | 189,824 |
| 缓存未命中 | 36,301 | 41,147 | 77,448 |
| completion Token | 12,691 | 38,555 | 51,246 |
| 其中 reasoning Token | 11,160 | 34,794 | 45,954 |
| total Token | 106,464 | 212,054 | 318,518 |
| 原公开 content 字节 | 4,449 | 11,265 | 15,714 |
| 推理字符长度遥测 | 43,666 | 135,864 | 179,530 |

44 次 usage 的上述字段均有实测值，缺失次数 0；reasoning 已在 completion 内，不能
再次相加。更多推理 Token／字符数不代表更深的可观察规划，也没有保存对应私有文字。
两条件实际返回模型名均为 deepseek-v4-flash，全部观察到同一个 fingerprint；它仍不是
不可变模型权重或内部相同计算过程的证明。

全部 44 次 HTTP 200、finish_reason=stop、公开内容非空，传输未知与长度截断均为 0。
因此本批五条答案 UNDETERMINED 不应误写成五次服务故障。单请求最大 completion
为 A 2,364、T 8,254，均小于 16,384。

请求 body 总计 1,006,410 字节，单次最大 30,529；预留 allowance 为 5,091,328，
不是收费 Token。安全投影 49,419 字节；HTTP 原接收长度总计 224,679 字节仅为内存
计数，没有保存相应原响应 body 或私有推理摘要。

### 10.2 同一模型费率下，分母改变成本结论

| 按登记人民币费率估算 | A | T |
| --- | ---: | ---: |
| 全条件空闲时段成本 | ¥0.1144346 | ¥0.2418356 |
| 同用量假设全按高峰 | ¥0.2288692 | ¥0.4836712 |
| 全条件成本／答案 PASS | ¥0.0127150 | ¥0.0241836 |
| 全条件成本／完整轨迹 | ¥0.0572173 | ¥0.0241836 |
| 全部 Token／完整轨迹 | 53,232 | 21,205.4 |

实际请求在北京时间 19:48:51—19:50:53，按登记的 [官方价格规则][price-source] 属空闲
时段；两条件合计估算 ¥0.3562702。高峰一行只是费率敏感性参照，没有第二批采样；账户
账单未读取，实际扣款保持未知，不能称为已结算费用。

T 总成本约为 A 的 2.113 倍，按答案 PASS 摊销也更贵；但按完整轨迹摊销降低约
57.73%，全部 Token／完整轨迹也更低。分子包含所有未确定、接口错误、无效发布与
无轨迹会话，不只加成功会话费用。因此“更经济”在本批仅适用于**当前完整轨迹目标**，
不能泛化为回答普通问题更省钱或未来稳定费用预测。缓存比例、交互长度和小分母都会
影响这次估算。

### 10.3 时延

| 请求时延，秒 | A | T |
| --- | ---: | ---: |
| 请求耗时之和 | 100.620 | 281.948 |
| 每请求均值 | 6.289 | 10.070 |
| 每请求中位数 | 4.471 | 4.142 |
| 最慢单请求 | 16.700 | 59.901 |

T 的总耗时与均值更高，而中位数略低，说明不能只挑一个时延统计支持结论。按每次 UTC
开始时刻加单调时钟耗时推得，两个固定波次的请求窗口分别约 71.764 和 50.193 秒，
全批约 122.077 秒；不含准备、测试、复核与提交时间，不是各条件独占资源的墙钟基准。

## 11. 核验、发布范围与后续决定

本轮闭合检查包括：

- 新 20 项局部控制收口重跑通过（1.45 秒），新正式源码／测试的 Ruff 检查通过。
  不是重跑旧全套控制或新的 Provider 校准。
- 四阶段清单全部通过，preparation、online、assessment、closeout 分别含
  30、450、50、26 个成员，另逐一核对 24 个会话清单。
- 全部 1,036 个冻结源码成员、新测试与两套执行胶囊字节未变；旧基线 `1282a57…`
  覆盖的历史文件保持不变。评价锁的三个文件及收口评价副本字节相符。
- 24 个 worker 的隔离记录与 48 次私有读取拒绝检查通过；44 份公开投影白名单、
  assistant.raw 字节及 usage 算术检查通过。没有原 HTTP 响应 body 文件；发布工件
  扫描未发现当前 Key 字节，未输出 Key 或其摘要。
- 辅助代理独立重加了计数并复核接口错误和 N5 真实短路线；这是代码／工件交叉核验，
  不把它升级成独立人类语义审查。量化核验见 [描述性汇总][derived-summary]。

**后续指令候选选择 T，模型继续固定 Flash/high。** 理由是在本面板上完整轨迹明显
更多、未观察到明确答案质量退化，且包含所有支出的单位有效轨迹费率估算更低。选择
记录保存在描述性汇总的 `next_condition_decision`；本轮没有静默修改其它适配器或
全局模型默认配置，也没有新增下一批采样。

这个决定仍有两条约束：其一，保留离线有效性筛选，不要求先达到无筛选全通过；其二，
T 的十条有效轨迹只覆盖 N1、N2、N4、N5、N6，N3 的预登记目标支持为零。**不能删去
N3 后仍声称有效训练材料保持六任务各 1/6 边际**，也不能用 A、旧 Pro 或 Host 补算
填补该支持。对 N3 题义和目标口径的后续修订应独立审阅、另行登记，不回写本批。

本轮至此收口：新指令改善了限定面板上的公开可验证数据产出；模型内在能力提高、
稳定统计优势、复杂财务纠错、新商分布、Token 训练表示及 Student／VTDO 效用仍未证明。
下一阶段若继续，应在固定 T／Flash/high 和明确任务边际下开展所需测量，不混合 A/T
分布、不把私有 Thinking 物化为训练目标。

只读复核入口：

```bash
PYTHONPATH=trusted_data_synthesis/src trusted_data_synthesis/.venv/bin/python \
  -m trusted_synthesis.experiments.finance_qa_vnext_trace_delivery.stage verify
```

[frozen-design]: ../artifacts/qa_vnext_trace_delivery/flash_high_at_2rep_20260909/preparation/design_at_freeze.md
[closeout-report]: ../artifacts/qa_vnext_trace_delivery/flash_high_at_2rep_20260909/closeout/report.json
[derived-summary]: ../artifacts/qa_vnext_trace_delivery/flash_high_at_2rep_20260909/analysis/summary.json
[n3-trace]: ../artifacts/qa_vnext_trace_delivery/flash_high_at_2rep_20260909/assessment/blinded/R016.json
[n5-no-final-number]: ../artifacts/qa_vnext_trace_delivery/flash_high_at_2rep_20260909/assessment/blinded/R024.json
[n5-short-route]: ../artifacts/qa_vnext_trace_delivery/flash_high_at_2rep_20260909/online/sessions/T_N5_01/turns/000_assistant.raw
[json-repair]: ../artifacts/qa_vnext_trace_delivery/flash_high_at_2rep_20260909/assessment/blinded/R005.json
[review-lock]: ../artifacts/qa_vnext_trace_delivery/flash_high_at_2rep_20260909/review/review_lock.json
[masked-reviews]: ../artifacts/qa_vnext_trace_delivery/flash_high_at_2rep_20260909/review/masked_reviews.json
[review-authoring]: ../artifacts/qa_vnext_trace_delivery/flash_high_at_2rep_20260909/review/blinded_review_authoring.py
[peer-check]: ../artifacts/qa_vnext_trace_delivery/flash_high_at_2rep_20260909/review/boundary_peer_check.md
[price-source]: https://api-docs.deepseek.com/zh-cn/quick_start/pricing/
