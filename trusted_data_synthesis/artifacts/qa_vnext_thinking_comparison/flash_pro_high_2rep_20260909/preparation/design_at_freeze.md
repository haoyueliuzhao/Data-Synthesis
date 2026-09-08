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

## 8. 正式结果（生成与遮蔽复核结束后追加）

冻结时尚未启动本批正式 Provider 调用。
