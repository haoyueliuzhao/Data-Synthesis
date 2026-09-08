# Flash/high 主条件与 Pro/high 参照：自主公式执行比较

## 1. 本轮范围与模型选型记录

本轮依据审计 SHA-256 `94e08fbf14f90b8be27a628e30a592d5c707e125cc8d3a53ef9725ef64170e30`
实施。历史基线 `858f8a4ecb86f49c59c2d37ae769b6a3d4d68362` 的 Pro/off 十二会话及严格 10/12
不变，不重跑 E3，不修改旧响应或旧评分。新增实现、工件和本说明均位于独立命名空间。

此前 v26 主线将 Flash 设为主 Explorer、Pro 仅为可选。9 月 5 日的 Share 适配器在
`55fb6aab8…` 直接指定 Pro/off；9 月 6 日后又沿用该已登记条件。最初审计只要求冻结明确
模型，没有指定 Pro；这条新 QA 实验链没有提供同任务、同协议 Flash/Pro 对照来论证替换。
这是选型说明的遗漏，不能由“已冻结”补成必要性证明，也不因此判废已有 Pro 结果。
可核查 [原 Flash 定位](finance_v26_capability_heterogeneous_mainline.md)、
[首次 Pro 配置](../src/trusted_synthesis/experiments/qa_reasoning_share_model_pilot/models.py)、
[后续沿用](finance_qa_vnext_representative_model_execution_and_export.md)。

主问题：固定现有自主执行 Harness 和统一评价版本，Flash/high 能否产生可验证轨迹；
其有限质量、成本、稳定性与同样 Thinking/high 的 Pro 有何差异？Flash 是主条件，Pro
仅为本轮参照，不自动变为后续默认。比较不估计 Thinking 开关的独立效应，不追加两组 off。

## 2. 二十四会话与不变项

| 条件 | 请求模型 | Thinking／effort | 任务与重复 | 角色 |
| --- | --- | --- | --- | --- |
| F-Think | deepseek-v4-flash | enabled／high | 六题各两个新会话 | 主 Explorer 候选 |
| P-Think | deepseek-v4-pro | enabled／high | 六题各两个新会话 | 固定参照 |

六题为 C2 原农业产品占比、E1 利息罚款占比、E3 代 GE 现金占比、M3 三年煤炭收入占比、
J1 税后成本增长率、J2 年度期权总额差；均为既有开发任务，不是盲测。每个条件内任务权重
各 1/6，每题分母固定为 2；失败、未知、截断均不删除。总分母 24，不补样到成功。

两个固定重复波次，每波十二个独立进程并行。每题第一重复按 F/P 登记，第二重复按 P/F
登记；第一波全部结束后启动第二波，顺序不依赖答案或成功率。对照会话不共享消息、工具
结果或笔记；不把旧 Pro 响应当作 Flash 示例。模型标签不注入任务 system／user 材料。

完整原 FinQA 表格、前后文、原问题和统一全部数字索引保持相同。通用 SYSTEM 与前版逐字
一致；calculator、isolate 沿用原代码字节。三个工具、整式／中间量接口、连续完整公开历史、
首个 Final 立即终止均保持；没有 Formula Gate、accept、预选必要来源或在线正确性反馈。
缺少来源声明或财务含义错误但数值合法的表达式仍然执行；来源不按同值自动绑定。

## 3. Thinking 传输与记录适配

2026-09-09 核对官方 [Thinking 指南](https://api-docs.deepseek.com/guides/thinking_mode/) 与
[API 字段](https://api-docs.deepseek.com/api/create-chat-completion/) 后，两组显式设置
thinking enabled、reasoning_effort high。temperature、top_p **省略而非继续声称 0.7/1 控制
采样**，因为它们在此模式下不生效。仍为 JSON object、非流式、不传原生 tools 参数；这个
JSON 路由下不需要回传 reasoning_content，因此继续保留完整公开历史，不传私有推理。

请求模型分别固定 Flash／Pro，允许实际响应标识为本名或对应的 -0731／-0813 版本名。
它们是服务返回名称，不是不可变权重的证明；high 是明确请求配置，不能由遥测认证服务端
实际使用了何种内部推理算法。

核心变更是**投影先于任何磁盘持久化**：

```text
HTTP 字节仅在进程内存中接收／解析
  → allowlist 提取公开 content 与受限身份、结束原因、usage
  → 推理内容只派生“存在、非空、字符数、UTF-8 字节数”
  → 保存 response_projection.json；公开 content 另按原 UTF-8 字节保存
```

不保存原 HTTP 响应体、reasoning_content、其摘要或私有 logprobs；没有“先写盘再删”的
中间文件。解析失败／HTTP 错误只保存安全投影、状态、字节计数和错误类型，不存错误原文。
禁用 worker core dump；不宣称生产级内存清除／沙箱证明。公开内容仍保持原样，来源证据
是受信接收程序的字段投影与 TLS 请求记录，**不冒称完整未修改 HTTP 原响应**。

reasoning_tokens 来自 completion_tokens_details；缺失保持未知，不能按字符数推断，也
不能再加到已经包含它的 completion 总数上。推理内容不成为公开公式证据、商状态或训练目标。

finish_reason=length 单列为 generation_truncated_length。公开残片（若有）原样保存，但
不作为普通工具 JSON 解析，不返回“公式错误”让模型修订，不延长预算或降低 effort 重试。
身份或结构异常仍作为相应未知条件问题保留，不用截断状态覆盖身份不符。

## 4. 统一的发布评价 v2

沿用 value 优先；缺少 value 时仅从实际 Final 引文提取明确答案数字，不从参考目标填值。
十进制容差登记为：

```text
tau = min(0.005, max(半个词法末位单位, 1e-12))
```

单位是原答案单位（percent 表示百分点数值、J2 为百万美元）。精确分数仍严格相等。
1e-12 是本次前置登记的表示误差下限，不是通用最优金融标准；0.005 上限仍保留。
它不能修复百分数尺度、单位、符号、年份或公式错误。

Final 的其它答案数值通过原 Final 引文列入 secondary_answer_values，按各自展示精度
对同一个精确答案量核验，从而检查与主要 value 的相容性；日期、来源定位和解释中的输入数字不冒充另一个答案。
方向及文字语义仍单独复核。没有 value 的自由文字答案允许引证提取，不强制新的在线字段。

旧批全部十二条仅生成一次正式的零 Provider **评价侧表**：固定原已发布值／单位和既有
Final 一致性复核，只修改数值容差，不重标其它语义。新表与旧表并列，不能称为新增十二条
成功或将旧严格 10/12 改成另一个数字。局部测试对此表的复算不是新的模型实验。

## 5. 模型标签遮蔽的有限语义复核

方法仍分为：公式适用性、变量／来源对应、单位／口径、独立真实计算、发布一致性。
独立 SymPy 数值 walker 不调用在线 Fraction 计算器；原文字关系与实际执行表达式分开。
源码不自动把字面数绑成参考来源，也不把符号来源图不匹配直接判为财务错误。

准备器随机分配 R001—R024，映射单独保存在私有准备目录。采集输出只显示这些编号；全部
生成结束后产出 blinded 视图，仅含原公共消息、任务键、计算记录和终止情况，不含模型名、
成本或条件标签。执行代理只阅读此视图填写评价；封存评价输入后才在 closeout 解码条件。
原文若自报模型身份不能被删改以制造盲态。本设计是**模型标签遮蔽的执行代理复核**，不是
独立专家或双盲研究；代理知道参考任务、先前结果，也可能从风格推测模型。

PASS／FAIL 语义字段必须引证实际公开响应。公式、数据、单位证据必须出现在所选答案计算
之前或同一请求中；仅在 Final 补公式、仅存在私有 Thinking、直接答数但无实际计算，都不能
升级为公式驱动已验证。允许未定替代依据，不由 Host 补写模型步骤。每题每模型只两次，
不能据此证明稳定优劣或统计非劣性。

## 6. 资源、成本及隔离

| 项目 | 两条件共同边界 |
| --- | --- |
| 每会话模型请求／工具调用 | 各最多 32；错误调用同样计数 |
| 新会话／全批请求上限 | 24／768 |
| 单请求 completion 上限 | 16,384，Thinking 与公开输出共用 |
| 完整请求 body 上限 | 98,304 字节，包含全部连续公开历史 |
| HTTP 响应接收上限／公开 content 上限 | 2 MiB／1 MiB |
| 连接／单次总时限 | 30 秒／180 秒 |
| 单请求预算 allowance | 98,304 + 1,024 + 16,384 = 115,712 |
| 全批 allowance | 88,866,816，非实际分词或收费 Token |

无网络重试、替换、跨模型 fallback、Thinking 降级、提示改写或自动压缩历史。completion
16K 是本次新资源条件，不把它称为与旧 Pro/off 8K 等价。保留全部请求和失败成本，真实
usage 缺失则未知；请求耗时之和不是并行墙钟时间。截断与财务错误分别报告。

费用依据为同日核对的 [官方人民币价格页](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)。
Flash 每百万缓存命中／未命中／输出空闲费率为 0.05／1.5／4.5 元，Pro 为其三倍；高峰费率
为相应空闲费率两倍。按实际 cache hit、miss、completion 给出空闲／高峰估算范围，**不称为
已结算账单或账户实际扣款**。网页旧英文缓存价格可能不同，不混用美元旧快照计算。

继续用独立 /usr/bin/python3 -I -S -B 与 Landlock：五个纯公开执行代码文件、单任务公共
材料和单会话输出；私有目标、标签映射、其它会话、旧结果均不可读。每个 worker 首次请求
前实际探测私有目标和 canary 的读取拒绝；Key 仅匿名管道传入，认证头不保存。不是只通过
提示要求“别看答案”。父进程可以准备旧侧表，但新会话评分必须等全部进程结束、在线封存。

## 7. 局部检查、冻结与入口

本轮 32 项控制覆盖原自主接口、精确计算及复用、隔离、错误 Final
终止、新精度及多字段一致性、私有内容投影、截断分类、两模型配置公平性、遮蔽视图持久化和旧侧表不回写。
还会在准备阶段记录同一测试结果与源码摘要。Ruff 通过后提交并推送冻结版本，再采集。

命令入口是 finance_qa_vnext_thinking_comparison.stage，模式 collect、assess、closeout、
verify；closeout 需要 --reviews 指向 R 编号的逐字引证评价 JSON。正式根目录为
artifacts/qa_vnext_thinking_comparison/flash_pro_high_2rep_20260909。准备、在线、评价、收口
各自封存所有文件的长度和 SHA-256；源代码必须保持首次调用前的 Git 字节。

本轮不开展新商、旧 Token 包再物化、Student、GPU 或 VTDO。使用 CPU 隔离进程和远程教师
并行完成有限诊断；新的错误不触发额外预选菜单或强制格式协议。完整记录后收口，不补满分。

## 8. 正式结果与结论

本节及后续章节为生成、遮蔽评价封存和模型标签解码后追加，**不改变前置登记或原始评分**。
首次调用前已提交并推送的冻结实现为 `cd317baa2d2c18b1817966cb8bf4125e79a341b3`。
前置设计原字节保存在 [design_at_freeze.md][frozen-design]，与本结果追加版区分。

**本轮观察：Flash/high 答案通过 9/12、完整公式驱动轨迹 5/12；Pro/high 分别为 12/12、
11/12。** Flash 确实产生了有效自主轨迹，但本批还观察到四次直接 Final、一次发布尺度
错误、一次低精度来源选择引起的发布失败，以及一次空公开响应。不能据此声称 Flash 已
满足无筛选批量轨迹合成要求，也不能把这个小样本差异升级成一般模型能力排名。

### 8.1 固定分母下的逐题结果

| 任务 | Flash 答案 | Flash 完整轨迹 | Pro 答案 | Pro 完整轨迹 | 未通过完整轨迹的主要原因 |
| --- | ---: | ---: | ---: | ---: | --- |
| C2 农业产品占比 | 1/2 | 1/2 | 2/2 | 1/2 | Flash 一条无 Final；Pro 一条只有裸算式，来源到 Final 才出现 |
| E1 利息罚款占比 | 1/2 | 1/2 | 2/2 | 2/2 | Flash 一条选择正文 139.5 million，未用表格 139.549 million |
| E3 代 GE 现金占比 | 2/2 | 1/2 | 2/2 | 2/2 | Flash 一条直接 Final，无实际计算 |
| M3 三年煤炭收入占比 | 1/2 | 1/2 | 2/2 | 2/2 | Flash 一条正确计算后把 fraction 数值标成 percent |
| J1 税后成本增长率 | 2/2 | 1/2 | 2/2 | 2/2 | Flash 一条直接 Final，且 result_id 指向原文而非计算结果 |
| J2 年度期权总额差 | 2/2 | 0/2 | 2/2 | 2/2 | Flash 两条均直接 Final，无实际计算 |
| **合计** | **9/12** | **5/12** | **12/12** | **11/12** | 不删除未知，不补充成功样本 |

Flash 的答案计数为 PASS 9、FAIL 2、UNDETERMINED 1；Pro 为 PASS 12。
合计 23 条 Final、21 条答案 PASS、2 条 FAIL、1 条未知、16 条完整轨迹。表中的“答案”
允许没有工具计算的正确 Final；“完整轨迹”要求公开关系、数据／单位对应、真实执行及
正确发布同时成立。不能把二者互换。

完整逐会话结果见 [正式收口报告][closeout-report]；按模型加和的成本、遥测、执行统计见
[零 Provider 描述性汇总][derived-summary]。后者在解码后生成，不修改冻结 evaluator 或评价输入。

### 8.2 三类失败／未知的具体证据

**Flash / M3_01（R017）：终局百分数尺度错误。** 实际 calculate 表达式为
`(2440 + 3237 + 4127) / (19941 + 21813 + 23988) * 100`，结果精确等于
`163400/10957`，即约 14.912841%。Final 同时包含：

```json
{"answer":"14.91284%","value":0.14912841106142192,"unit":"percent"}
```

公式、三年汇总、代入数据与实际单位处理均可复核；错在把比例小数发布为百分点数值。
保留 value 优先，发布一致性 FAIL、任务 FAIL，不用正确 answer 字符串覆盖它。不存在
工具计算错误，也没有模型收到错误反馈后自主修订的过程。[原公开 Final][m3-failure]

**Flash / E1_02（R003）：真实但已舍入的分母选择，与精确参考发布不等价。** 模型在
执行前明确选取原正文 q0 的 139.5 million，与 q2 的 15.3 million 同尺度相除。公式
`15.3 / 139.5 * 100` 的实际结果为 `340/31`；Final value 为 `10.96774193548387`，
answer 为 `10.97%`。这两者内部相容，引用的科目、期间及原文数值也真实存在，因此不
把它描述为来源捏造或千／百万尺度错误。[原始计算请求][e1-request]

登记参考使用更精细的表格余额 139549 thousand，精确答案为 `1530000/139549`，约
10.963890819712072%。两种计算结果相差约 0.003851115772 个百分点：对主要长小数
value 的 1e-12 容差不合格；10.97 的误差约 0.00610918，又超出该展示精度的半末位
0.005。故任务 FAIL。**这不是 E3 式的 1e-15 表示误差**，不能由新增表示误差下限修复。

这里有一个应明确披露的测量命名限制：自动 reason 字符串为
`inconsistent_final_numeric_fields`，因为 secondary 答案对同一精确参考未通过；但本条
人工 `final_answer_consistency` 为 PASS，表示模型自己的数值字段彼此相容。
不能把该自动 reason 误读成“模型的 answer 与 value 自相矛盾”。任务的精确参考失败
不回写；其研究解释是**公开来源精度选择／发布政策敏感性**，不是公式或单位推断失败。

**Flash / C2_02（R014）：空公开响应，保留未知。** 首次 calculate 正确执行
`3581/21813*100`。第二次 HTTP 状态 200，模型名匹配，finish_reason 为 stop，但
公开 content 是空字符串；completion 58、reasoning_tokens 58。worker 记录
`provider_envelope_or_condition_failure`，无 Final，终止为 unknown_transport_or_condition。
不能填入前一工具的正确结果，也不能把它说成超时或 finish_reason=length 截断；仅凭
投影无法进一步定位服务端为何未返回公开内容。本轮不重试。[安全响应投影][empty-projection]

### 8.3 答对但公开轨迹不完整

Flash 的 E3_02、J1_01、J2_01、J2_02 共四条直接提交 Final，全部数字答案通过。公开
文字确实有相应算式、年度配对或单位转换，但实际 calculate 调用数均为零。私有 Thinking
的存在和长度不能补成工具轨迹。其中 J1_01 的 result_id 是 `public_document:…`，不是
实际工具结果，因此其 publication_alignment 为 FAIL；这项执行引用缺陷与数字答案正确
分别保留，不通过 Host 生成 tool:1 修复。

Pro 的 C2_02（R021）实际请求只有 `3581 / 21813 * 100` 与空 variables，无执行前角色、
来源或单位声明；Final 才列出正确 source IDs。算术及答案都正确，但本次有限语义复核把
执行前变量对应、单位处理记为 NOT_ESTABLISHED，故不计完整轨迹。**这是证据可见性边界，
不是判断两个字面数本身算错。**[裸算式原请求][bare-request]

这一边界不是要求每个变量强制满足某个新在线 schema：例如 Pro / J2_02 虽然也用字面
算式、没有 message，但同一次请求中的未消费变量注释已经公开了年度、股份数、价格和
单位，足以进行有限语义复核。J1_02 的分数形式亦有执行前财务关系和年度说明。上述区别
在模型标签遮蔽状态下已写入逐条评价，没有解码后为某个模型调整标准。

## 9. 实际行为与来源绑定：成立的范围

全批 44 次真实模型请求可以核对为：

```text
44 = 20 次 calculate 请求 + 23 次 Final + 1 次空公开响应
```

Flash 为 20 次请求、8 次实际计算；Pro 为 24 次请求、12 次实际计算。20 次计算的独立
SymPy 复算全部与实际工具输出一致；**这是执行算术正确，不是说所有表达式都等于财务
参考答案**。全部计算都是单次完整表达式；80 个表达式运算节点不是 80 次旧原子动作。
实际跨计算 result_id 复用为 0，没有调用 read_source 或 notebook，没有工具错误，也没有
失败方法后的自主修订。最多两个模型响应便终止；不宣称复杂规划、搜索或纠错已建立。

| 分开统计的证据 | Flash | Pro | 解释范围 |
| --- | ---: | ---: | --- |
| 有实际执行前表达式的会话 | 8/12 | 12/12 | 不把仅在 Final 出现的算式算入 |
| 独立算术复算通过 | 8/8 | 12/12 | 校验实际执行的表达式，不等于任务全通过 |
| 自动 source_symbolic_target_match | 1/8 | 6/12 | 仅实际计算为分母；其余不自动判财务错误 |
| 有限公式适用性复核 PASS | 12/12 | 12/12 | 包含仅 Final 可见的关系，不代表执行前轨迹 |
| 有限变量／来源对应 PASS | 12/12 | 11/12 | Flash 的 E1 舍入来源真实但精度不同；Pro 一条执行前未建立 |
| 有限单位处理 PASS | 12/12 | 11/12 | 评价关系本身／执行前单位；M3 的后续发布尺度错误另记 |
| 执行—发布对应 PASS | 6/12 | 12/12 | Flash 另有 2 FAIL、4 NOT_ESTABLISHED |
| 正确发布且完整公式轨迹 | 5/12 | 11/12 | 最终联合条件，才是本轮有效轨迹产量 |

20 次计算中，8 次实际消费命名变量、12 次消费字面算式。Pro / E1_01 使用了
`source:t6c1` 而非数字跨度 `source:t6c1n0`；自动系统保持该输入为未链接数值常量，
没有替模型补 n0。但它的执行前公开文字及 cell 定位明确指向 139549 的期末余额，因此
有限语义对应 PASS。其它字面算式即使带了未使用的 source／variables 注释，也不因此
获得机器绑定认证。

E1 三条选择表格精细余额的会话都作了相容尺度转换，其中千美元尺度主要由相邻 139.5
million 正文和 139549 表格共同支持；抽取表格本身没有显式千美元表头。不要把“执行了
合理尺度转换”扩写成已经观测到完整单位推断过程。

遮蔽过程：执行代理阅读全部 R001—R024 公开视图和原题材料，完成引证后于北京时间
2026-09-09 02:30:54 封存输入；其 SHA-256 为
`56421672b9b3a61efbfb93e3bc2a3665939803b5e8fdeadd3377646236d06cca`。
随后才调用解码收口、读取模型报告与成本；收口复制与锁定输入逐字相同。
见 [评价锁][review-lock]、[遮蔽评价输入][masked-reviews] 和 [评价编写记录][review-authoring]。
原公开内容中未观察到自报模型名称；仍不声称风格完全不可猜测、独立专家复核或第三方
盲态认证。逐字引文检查保证原文真实性，不保证语义判断客观无偏。

## 10. 成本、时延与 Thinking 遥测

### 10.1 全部分母下的原始用量

| 实测项目 | Flash/high | Pro/high | 合计 |
| --- | ---: | ---: | ---: |
| 注册会话 | 12 | 12 | 24 |
| 模型请求／已记录 outcome | 20 | 24 | 44 |
| 输入 Token | 118,516 | 139,340 | 257,856 |
| 其中缓存命中 | 81,536 | 99,840 | 181,376 |
| 其中缓存未命中 | 36,980 | 39,500 | 76,480 |
| completion Token | 59,848 | 24,938 | 84,786 |
| 其中 reasoning Token | 56,906 | 21,131 | 78,037 |
| total Token | 178,364 | 164,278 | 342,642 |
| 实际计算 | 8 | 12 | 20 |
| 工具错误 | 0 | 0 | 0 |
| 收到非空公开 content | 19 | 24 | 43 |
| 非空私有推理存在遥测 | 20 | 24 | 44 |

44 次请求的所有上述 usage 字段均有实测值，缺失次数为 0；空公开响应的 58 个输出 Token
也已计入。每次满足 cache hit + miss = prompt、prompt + completion = total、reasoning
不大于 completion。**78,037 不再加到 342,642 上。** Flash 在本批消耗的 Thinking Token
更多，但不能把跨模型的 Token／字符长度解释为可比较的推理深度或质量。

Flash 与 Pro 的私有推理字符长度遥测分别为 224,509 和 78,786，总计 303,295；只是
接收时的存在、长度统计，未保存文本或其摘要。原公开 content 合计 19,267 字节；安全响应
投影合计 53,664 字节。HTTP 接收长度合计 354,445 字节是内存接收计数，不是某个保存着
私有内容的原响应文件大小。

全部响应返回本名 deepseek-v4-flash／deepseek-v4-pro，各自观察到一个 fingerprint；
正式 44 次 finish_reason 均为 stop，generation_truncated_length 为 0。单请求最大
completion 分别为 13,921 和 3,418，均小于 16,384。没有通过延长预算消除失败。
全批实际预留 allowance 5,091,328，44 次请求 body 合计 982,267 字节，单次最大 27,075
字节；这些资源计数不冒充收费 Token。

### 10.2 费用：整批更便宜不等于有效轨迹更便宜

| 人民币官方费率估算 | Flash/high | Pro/high |
| --- | ---: | ---: |
| 本批空闲时段估算 | ¥0.3288628 | ¥0.5293890 |
| 若同用量均按高峰费率 | ¥0.6577256 | ¥1.0587780 |
| 空闲估算／全部注册会话 | ¥0.0274052 | ¥0.0441158 |
| 空闲估算／答案 PASS | ¥0.0365403 | ¥0.0441158 |
| 空闲估算／完整轨迹 | ¥0.0657726 | ¥0.0481263 |

公式为 `(cache_hit × 命中价 + cache_miss × 未命中价 + completion × 输出价) / 1e6`。
本批请求处于北京时间 02:15—02:19，按同日 [官方价格规则][price-source] 属空闲时段；
相应合计估算为 ¥0.8582518。高峰一行是相同用量的费率敏感性参照，不是第二张实际账单。
账户结算账单没有接入，actual_billed_cost 均为 null，不能称为已扣款。

后两行将**整个条件的成本**除以通过数，包括失败、未知、直接 Final 和不完整轨迹的
费用，不是只加成功会话的成本。Flash 整批空闲估算比 Pro 低约 37.9%，但每条完整轨迹
成本高约 36.7%。这只是 12 会话／条件和本次缓存状态下的描述，不是稳定的单位成本预测。
两模型运行交错、第二波缓存命中更多；不能由价格或延迟差异单独推导计算效率因果结论。

### 10.3 时延和稳定性

| 请求耗时，秒 | Flash/high | Pro/high |
| --- | ---: | ---: |
| 全部请求耗时之和 | 443.771 | 471.086 |
| 每请求均值 | 22.189 | 19.629 |
| 每请求中位数 | 3.712 | 14.357 |
| 最慢单请求 | 96.327 | 64.776 |

Flash / E1_01 两次请求合计 163.952 秒、completion 23,552、reasoning 23,215，是本批
明显长尾；该 23,552 是两次之和，不是单请求突破 16K。Flash 的低中位数与较高均值可以
同时成立，不能只报告其中一个。

按请求开始 UTC 加实测单调时钟耗时推得，第一波请求窗口约 163.965 秒，第二波约
81.401 秒，互不重叠；全批请求窗口约 245.506 秒。它包括固定波次间隙，不包括准备、
测试、离线评价和提交时间，也不是两个条件分别占用独立服务器的墙钟基准。
没有超时、HTTP 非 200 或长度截断；唯一未知为前述 stop + 空公开内容。

## 11. 历史侧表、核验与工件索引

旧 Pro/off 十二条仅按新数值规则形成 [历史评价侧表][historical-side-table]：旧严格计数
仍为 10 PASS、2 FAIL，新版本侧表为 12 PASS。变化仅是原 E3 两条末位误差，**没有新的
Provider 会话、没有重标旧公式语义、没有把旧 10/12 覆盖成 12/12，也不计入本批 24 条**。

本轮核验记录如下：

- 新命名空间的 32 项控制在冻结前、准备时和收口检查中通过；收口重跑为 32 passed in
  1.92s。Ruff 检查新正式源码与测试通过；没有声称重跑整个历史仓库测试。
- preparation、online、assessment、closeout 四份清单的全部成员长度、摘要及身份核验
  通过；全仓冻结 Python 源码、冻结测试均未在正式生成之后改变。
- 24 个独立 worker 全部记录 Landlock ABI 4、isolated/no-site、无仓库 evaluator 模块、
  禁用 core dump；48 次私有目标／canary 读取探测都在请求前被拒绝。
- 44 份投影检查通过；公开 content 与各自 assistant.raw 字节相同，包含那个空字符串；
  没有保存 `*_http_response.body`。记录已明确标注投影，不声称具有原 HTTP 原文的取证强度。
- 当前 API Key 字节未出现在发布工件；没有输出 Key 或保存其摘要。这是发布扫描，不是
  对任何未来未知 Provider 字段的全能安全证明。
- 旧基线 `858f8a4…` 覆盖的历史文件保持不变；新旧 SYSTEM、calculator、isolate
  字节相同；评价锁中的输入与编写记录摘要保持不变。核验详情在 [描述性汇总][derived-summary]。

复核入口（`closeout` 已执行，不能在同一目录覆盖重做；`verify` 可重复执行）：

```bash
PYTHONPATH=trusted_data_synthesis/src trusted_data_synthesis/.venv/bin/python \
  -m trusted_synthesis.experiments.finance_qa_vnext_thinking_comparison.stage verify
```

原始采集、投影、来源材料、隔离记录及逐次 usage 在新工件根目录下完整保留。
`review/blinded_review_authoring.py` 是生成结束后、解码前写定的有限复核编写记录，不是
前置冻结的自动评价器；`analysis/post_generation_summary.py` 仅在解码后作加和、核验与
描述性整理，不新增模型调用，也不替换任何语义判定。

## 12. 本轮收口与后续选型边界

结论分成三层：

1. **工程适配完成。** 固定自主 Harness 已支持两模型 Thinking/high、投影先于落盘、
   真实推理用量和独立截断分类；没有恢复 accept、在线答案反馈或强制公式阶段。
2. **Flash 有有限正证据，也有明确缺口。** 5 条完整轨迹证明它能在现接口自主完成有效
   公式执行；但 9/12 答案、5/12 轨迹和本批单位有效轨迹费用，尚不足以确认无筛选合成
   默认配置就绪。保留 Flash 为主研究候选，不因 12 个样本直接否定整条 Flash 路线。
3. **Pro 仍只是本轮参照。** 它本批 12/12 答案、11/12 轨迹的表现更完整，但不是替换
   主 Explorer 的普遍必要性证明；本轮没有改写其它模型适配器为 Pro，也没有以 Pro
   的答案补成 Flash 成功。

若继续，优先在新的、未用于上述开发的任务上确认公开轨迹产量，并把正文舍入分母、
终局百分数尺度、空公开响应、缺执行证据分别作为离线误差类别。此处只是后续研究建议，
本轮不追加采样、不补满分、不导出训练目标或启动 Student／GPU／VTDO，不重建强制协议。
Thinking 的独立增益、广泛稳定优劣、复杂自主规划与训练收益均仍未测量。

[frozen-design]: ../artifacts/qa_vnext_thinking_comparison/flash_pro_high_2rep_20260909/preparation/design_at_freeze.md
[closeout-report]: ../artifacts/qa_vnext_thinking_comparison/flash_pro_high_2rep_20260909/closeout/report.json
[derived-summary]: ../artifacts/qa_vnext_thinking_comparison/flash_pro_high_2rep_20260909/analysis/summary.json
[m3-failure]: ../artifacts/qa_vnext_thinking_comparison/flash_pro_high_2rep_20260909/online/sessions/F_M3_01/turns/001_assistant.raw
[e1-request]: ../artifacts/qa_vnext_thinking_comparison/flash_pro_high_2rep_20260909/online/sessions/F_E1_02/turns/000_assistant.raw
[empty-projection]: ../artifacts/qa_vnext_thinking_comparison/flash_pro_high_2rep_20260909/online/sessions/F_C2_02/turns/001_response_projection.json
[bare-request]: ../artifacts/qa_vnext_thinking_comparison/flash_pro_high_2rep_20260909/online/sessions/P_C2_02/turns/000_assistant.raw
[review-lock]: ../artifacts/qa_vnext_thinking_comparison/flash_pro_high_2rep_20260909/review/review_lock.json
[masked-reviews]: ../artifacts/qa_vnext_thinking_comparison/flash_pro_high_2rep_20260909/review/masked_reviews.json
[review-authoring]: ../artifacts/qa_vnext_thinking_comparison/flash_pro_high_2rep_20260909/review/blinded_review_authoring.py
[historical-side-table]: ../artifacts/qa_vnext_thinking_comparison/flash_pro_high_2rep_20260909/preparation/historical_evaluation_side_table.json
[price-source]: https://api-docs.deepseek.com/zh-cn/quick_start/pricing/
