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

## 8. 正式结果（生成和遮蔽复核后追加）

冻结本设计时尚未启动本批正式 Provider 调用。
