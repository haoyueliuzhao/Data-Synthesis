# 来源覆盖扩展与受保护 LLM 题面实现（2026-09-12）

## 本阶段边界

本文件先登记实施规格，运行后补充实际结果。原任务工厂运行提交为
a547633410a5d3355ee03888b6492c6b64f24657，发布提交为
b3d7e7b182c1dbcdd8fff65a836518491a04d4ee。原 221 题按其范围通过；
其 LLM 状态是 NOT_ENABLED，不是请求失败后的回退。原目录不改写、不重新生成。

本阶段目录为 artifacts/qa_vnext_surface_build/task_surface_20260912；
数据库位于独立的 runtime_20260912。先提交代码，再冻结代码、输入字节、
解释规则与枚举次序；之后才产生新事实／KG／QA Build 和真实改写请求。
已有源码反例、来源诊断和来源补取结果是已知的实施依据，不宣称盲选。

不执行 Teacher 解题、Student、模型权重或 tokenizer 加载、GPU 训练，也不沿用
X1/X2 硬编码 worker 评价新任务。确定性参考见证是算术父产物，不是模型轨迹。

## 1. 来源扩展规则

继续使用原 CIK split：盐 basis_task_factory_sources_20260911.v1:，模 55，
train 桶 0–9；不迁移确认公司、不改盐。存量、年度流量、公司定义、控制的候选上限
仍分别为 53、54、53、100，总上限 260。变化额与变化率是同期间对的两种数量目标，
不是两份独立来源；句式变化不产生新科学任务。

扩展针对原始发行人披露中的具体缺口：

- Oracle 的 “We calculate free cash flow as follows:” 指向后续完整表格。原匹配器
  只在句号结束，会吞入冒号后的表格和说明。新增冒号结束规则，继续要求完整
  有符号对账行、明确单位和同一 filing 的原生 CFO 数值锚点。
- TI 的完整 subtracting-capex-from-CFO 句式被登记为有限语法，严格要求 CFO、
  capex 两种角色，不新增全局 FCF 公式。正数 capex 的隐式符号转换不在本次域内。
- 星号或数字脚注可以从行标签的角色识别部分剥离，但必须在原表之后找到真实说明；
  原标签、原单元格、脚注原文和文本偏移均保留。标签中的符号本身不算说明证据。
- ServiceNow／TI 的破折号仍不是数字。不凭本期金额、常识或算术闭合把前期破折号
  当零；只使用满足规则的完整披露。跨期间要求相同定义文本与组成标签身份。

额外补取 Oracle 2020 报告：SEC 原文请求得到 403；发行人链接下载的 HTML 是渲染
后的 XBRL 报表，不是含 MD&A 的合格完整正文。三次来源 HTTP 尝试及未接纳文件留档，
未将其加入有效来源集合，也未为凑足 40 题取消源文档验证。来源补取与模型请求分账。

## 2. 在真实题面上验证“同一数量”

新增 finraw.qa.temporal_rewrite 有限英文解析域：

| 合同要素 | 验收 |
| --- | --- |
| 差额 | 有符号 current − previous；拒绝反向差、绝对值、两期和等 |
| 增长率 | 100 × (current − previous) / previous；前期必须为正 |
| 实体、指标定义、实际期间 | 原槽位保留；合同携带实际绑定角色、期间、定义 ID |
| 单位与精度 | 输出指令保持原文并位于末尾 |
| 域外表达 | 拒绝候选；最多一次合同修复，之后保留 canonical |

解析实际渲染后的题面，不接受模型自报“语义保持”。多个完整句式可以通过；全文
匹配防止合法前缀后藏额外操作。按文本的角色顺序解析方向，不先排序日期后猜题义。
数字检查覆盖句末 42.、括号、正负号、小数与日期槽位。

源码版本为 question rewrite v3.3、question parser v1.6.0、QA generator v4.30。
原 8 个控制中的正确差额／前期分母增长率通过，其余运算、槽位、数字负控制拒绝。
这些是合成控制，不是将旧 221 题重新判错；也不是通用自然语言定理证明。

## 3. 真实请求合同

固定 controlled_llm / protected_rewrite、英文、variants=2、max_attempts=2；
关闭 surface_variation 和模型别名选择。按响应原始顺序取第一个合格候选，不按
文风、Student 结果或任务难易筛选。第一候选合格后，其余响应保留但不继续打分。
原文或仅标点／大小写／空白变化另计，不算真正改写。

登记一个 API 身份 deepseek-flash，地址 https://api.deepseek.com/chat/completions，
显式禁用 thinking，省略 temperature/top_p，使用 JSON 输出，单次最多 1,536 output
tokens。精确核对实际返回模型字符串；该字符串不是权重版本哈希。不开自动模型发现、
缓存、模型回退或重定向。这是改写专用合同，不声称与旧 Teacher thinking 合同等价。

Prompt 只含受保护问句及必要的数量语义。不传数值答案、来源正确角色表或
endpoint/movement 标签／路线菜单。保留原始响应、请求体（无 Authorization 值）、
响应 SHA、用量、错误、候选检查和最终题面。密钥仅从项目 .env 读取，不进入日志。

专用发送入口使用线程局部网络许可；旧离线守卫仍拦截通用模型客户端、Teacher
runtime、Student、权重加载与 CUDA。计数是登记入口的运行检查，不是任意代码隔离证明。

## 4. 预算与故障

| 项目 | 上限／处理 |
| --- | --- |
| 登记任务 | ≤260 |
| 实际改写请求 | ≤520，每题 ≤2，首批 20 题包含在总量内 |
| 改写 Token 额度 | 2,000,000，计入原 1,000,000,000 上限，不另增总额度 |
| 每次预留 | 8,192 input + 1,536 output = 9,728 |
| Prompt 字节上限 | system + user 合计 6,144，预留另含消息开销余量 |
| 原子性 | SQLite WAL + BEGIN IMMEDIATE，请求前持久预留 |
| 用量未知／中断 | 保留全部预留，不释放、不自动重放 |
| 已报用量超出预留 | 记真实用量，标记 breach，拒绝后续预留 |
| 修复 | 仅明确结构／语义失败允许一次；空返回和运输错误不自动重试 |

已知真实用量结算后释放未使用预留。单题未用次数不能转成另一题的第三次尝试。
预留大小不是服务端 tokenizer 的形式化上界；用量超界检查和停发路径分别测试。
后续总预算必须扣除本阶段实际／保守记账以及其它已发生支出，不能重新启用十亿额度。

## 5. 身份、fallback 与统计

canonical_task_registry.json 在首个模型请求前登记全部目标。Task ID 只来自来源簇、
指标定义、实际期间和数量目标；surface version 由 Task ID 和实际公共输入字节确定。
新 QA ID 或语言变体不增加科学任务数。

每题固定一个 teacher_visible.json，未来 A/B、endpoint/movement 条件及所有训练臂
必须共享这些字节；不能把旧问题的响应换上新题目前缀。当前仅冻结候选公共输入，
不声称下游 TaskCatalog worker、轨迹材料或训练就绪。

无论改写是否成功，都保留通过来源／数量验收的任务。分别报告真正接受改写的任务数
／全部登记任务数、HTTP 成功数／实际请求数，以及拒绝候选、surface-only、
原文／纯格式变化、fallback、无返回、未发请求、修复请求和 input/output 用量。
零分母使用 null／NOT_APPLICABLE。API 表现只是观察指标，不作删题门槛。

首批 20 题须实际通过 QA 并全部保留，真实请求与真正接受改写均大于零后才继续其余
登记任务。首批不是新增效用实验，也没有额外预算。

## 6. 验证与复现

测试覆盖核心函数反例、数字边界、源脚注、有限定义、跨线程／进程预算、重启不重放、
异常用量、身份不符、运输错误，以及合成来源经真实 Fact/KG/QA 链路的接受与完整
fallback。一次测试收集误用了缺少 torch/lxml 的系统 Python，后改用项目虚拟环境；
另一次集成夹具未提供完整 public 字段，修正后重测。两者均无生产模型请求。

冻结前相关回归集为 275 项通过（18.51 秒）。新模块与适配器 Ruff 检查通过。
核心历史文件的无关宽泛 lint 告警未扩展整改；运行后校验所有新 manifest 成员、Task/Surface
身份、实际题面、逐题请求账与旧目录不变。独立来源脚本核对本次新目录的原始
JSON/HTML、父链、目标值和参考见证，不导入原任务生成器或计划执行器；
但其算术复算不替代自然语言语义检查，也不是独立人工财务审阅。

项目根目录设置 PYTHONPATH=raw_financial_data_lake:trusted_data_synthesis/src 后执行：

    trusted_data_synthesis/.venv/bin/python -m trusted_synthesis.experiments.finance_qa_vnext_surface_build.stage freeze
    trusted_data_synthesis/.venv/bin/python -m trusted_synthesis.experiments.finance_qa_vnext_surface_build.stage run
    trusted_data_synthesis/.venv/bin/python -m trusted_synthesis.experiments.finance_qa_vnext_surface_build.stage verify

一次冻结只运行一次；失败不删除预算／请求目录，不借重新命名批次重试。
首批和后续批次共享协议，真实结果由封存目录的报告决定。

## 7. 下游设计保留但不启动

保留约 200 题、120 双依据＋80 控制、每池 2,560 训练＋640 封存包、A/B 两池、
三种分布策略、全局转移质量 1/10、五题 64 包、200 题十遍 400 次更新，以及
180 开发／720 确认新任务、池 A 最多 9 次／池 B 最多 6 次训练、池 B 主确认。
不足时报告可支持的 180–200 区间配额，不以改写数、年份或种子乘数冒充独立来源。
worker 接入、资格和方法识别、真实两池材料、token 消费性仍是后续工作。

## 8. 实际运行结果

待冻结运行完成后补充，不预填任务数、改写率或来源扩展收益。
