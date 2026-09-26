# 第二次前瞻接口试验：选原行ID，不让模型计算字符偏移

这是一个**新请求/回复协议**，不是对第一次真实试运行失败回复的纠错。第一次10次HTTP结果及其2通过、8失败保留：3次因length截断；其余5个完整失败回复含39条finding，原字符偏移无一精确，其中36个quote虽然可唯一找到、3个quote根本不存在。新组件不会查找或搬移这些旧quote来改判。

新文件`scripts/cross_market_review_line_locator_20260927.py`独立实现原行索引及确定性派生；原projection、core、第一次pilot及其预算均不修改，不调用API或已冻结prepare。第二次试验仍需主执行器另行冻结输入、代码和有限调用预算。

## 无损行账本和完整输入

`project_packet(original_packet, original_reference)`先复用冻结的原packet身份检查，然后对**每个原segment**执行`splitlines(keepends=True)`。行编号为packet内部的`L000000…`，segment短键为`S000…`；它们通过新`line_ledger_id`、原packet ID及原字节hash绑定，不在其它packet之间混用。

账本保存每行的原segment ID、行序、Python Unicode局部start/end及原行text，并验证逐行拼接严格等于原segment.text。CRLF、CR、Unicode换行、空白和无结尾换行均不改。原`segments`完整对象留在新投影记录的`original_segments`；模型仅接收一次同样的全文字符，即`payload.indexed_segments[].lines[].text`，避免再重复回显整段。原页身份、完整task intervals、四指标及视觉未审警报仍保留。

空segment保留独立S键与原身份，`lines=[]`，不虚构可引用的空行。模型必须仍把该S键列入已处理声明；空文本/视觉未覆盖等问题应返回uncertainty，不能由空文本推定无汇总值。

## 新回复格式

顶层仍仅为`packet_id`、`segments_reviewed`、`findings`、`uncertainties`：

- `packet_id`必须是原packet ID。
- `segments_reviewed`必须完整列出输入全部S短键，每个恰一次；不会由代码自动补上模型漏掉的段。
- 每条finding精确包含`id, line_start, line_end, metric, kind, period_start, period_end, reason`。两端是实际L行ID，含首行与末行，必须同一segment、顺序正确；范围内所有中间行都纳入。
- metric仍只允许原四指标或unknown；kind仍为potential_aggregate、annual_observation、other_scope、uncertain。日期仍只是未经独立裁定的模型提议。
- uncertainty精确包含`segment_key, reason`。跨segment证据必须分开定位或报告不确定性，不能拼接成假连续区间。

模型**不得返回quote或字符start/end**；出现这些旧字段直接失败。提示建议reason为简短具体短句，但不截断任何返回内容，也不要求为了4096上限省略发现、原文、区间或四指标。示例用显式EXAMPLE_ONLY占位符，不能充当真实行ID。

## 确定性派生与原始回复并存

`validate_line_scan(packet, projection, rawpayload)`逐条验证真实行ID，按封存账本直接取该连续范围的起点/终点，再从**原segment.text**切片产生quote。还核对quote等于所有所选原行text的拼接，然后把标准派生payload交给冻结`core.validate_scan`。

这不是模糊搜索、相似quote匹配、偏移搬移或语义修补。未知、倒序、跨段、重复finding、遗漏segment、旧字符协议字段及被篡改的账本均拒绝。即使模型选择了真实行，仍可能选错证据或解释错误；确定性映射只保证定位，不保证财务语义。

返回值保留冻结core的标准`status/payload/passed=false`等字段，另附：

- `raw_line_payload`：模型原始JSON对象的原样副本；主执行器还须保留原HTTP content/envelope，不改收到的原字符串。
- `line_mapping_proof`：原packet、投影和行账本ID/hash、raw/derived payload hash、每条finding完整行范围及原Unicode偏移/quote hash、S键到原segment ID映射。

独立裁定仍消费原材料和标准派生payload，不因派生quote必定存在就自动确认“无三年汇总”。视觉覆盖、来源版本和语义门槛均未降低。

## 执行器适配与字节预算

接口继续提供`project_packet`和`render_request`；renderer返回原`FrozenRequest(body, metadata)`。内层user JSON及外层body均用`base.encode`规范化；metadata包含request_sha256。thinking-disabled、stream-false在线格式字段在真实UTF-8字节检查前加入；transport应原样发送body，或保证`json.loads(body)`后再次`base.encode`逐字节相同。

请求字节cap必须显式登记，超限拒绝、不裁剪；输出上限保持4096。新独立控制器可在其隔离命名空间替换`request_payload`为此renderer、`validate_scan`为`validate_line_scan`，不能修改冻结core，也不能在第一次pilot输出目录复用缓存改变旧结论。

短行ID和不回显quote有望减少偏移错误及输出量，但**不保证4096以内或成功率**。证据密集包仍可能截断；必须按真实第二次结果记录失败和预算，不隐藏截断、不回收失败额度。

## 必要测试

18项纯合成测试通过，覆盖Unicode/CRLF/Unicode换行及所有段/区间无损、空段声明、确定性原quote、raw payload不改、未知/倒序/跨段/虚构空行/旧quote或offset字段拒绝、错packet/漏段/重复段/未知uncertainty/错指标/重复finding拒绝、篡改并重算hash仍拒绝、规范wire/文件读回hash一致、thinking/stream与4096保持、超字节cap不截断、长reason不被硬截、示例占位符不能作实际选择。Ruff通过。没有生产API、资格运行或旧回复改判。
