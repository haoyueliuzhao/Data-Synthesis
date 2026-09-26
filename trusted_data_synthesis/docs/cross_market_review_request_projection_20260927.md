# 全文辅助审阅请求的有损几何／无损文本投影

本模块为当前6,099份冻结材料包提供**只含原文文字的辅助请求视图**。它不是重新制作材料包，不改任何冻结文件，不读取原PDF/图片，不发送API，不改变实验预算或调用已冻结`prepare`。原材料包及其完整几何清单始终保留。

代码：`scripts/cross_market_review_request_projection_20260927.py`。新投影有独立内容hash/ID，显式绑定原packet ID、原规范JSON字节hash与原登记引用；不把删去几何明细后的对象伪称为原材料包。

## 无损保留什么

- 原`segments`的全部对象、顺序、字符、segment ID、原文档ID、页码、页文本hash、页字符总数及start/end偏移原样深拷贝。空文本页的空segment也保留，字符不规范化、不裁剪、不翻译。
- 原`registered_candidate_intervals`全部对象原样保留，不只选前60任务或当前命中区间。
- 四个固定mean指标、原PDF hash/URL、完整页文本引用、几何引用及完整文档页数保留；不添加Student/种子/分支/Q或答案条件。
- 每页原警报、空文本状态、image placement数量及完整原几何inventory的hash保留。只有几何placement细节不进入模型请求；完整记录仍能从原hash绑定材料追溯。

投影明确声明只提供文字、没有视觉内容、没有完成原页视觉/向量语义审阅，也没有来源穷尽证明。非空文本不代表图像或向量表格已覆盖，单个packet的投影也不证明整份报告已审阅。

## 请求与回复契约

请求仍通过冻结`core.request_payload`构造，system指令逐字不变、四指标/两通道含义不变、JSON response format不变、输出上限保持4096。模型输入明确`packet_id`必须返回**原packet ID**，不是新projection ID。

新增格式说明使用Python Unicode code points作为精确原segment.text的索引：start含、end不含，不是UTF-8字节或UTF-16代码单元。quote必须逐字等于原`segment.text[start:end]`，不允许去空白、换引号或改Unicode规范化形式。

JSON示例明确标记`SCHEMA EXAMPLE ONLY`，只用“示例”这一合成字符串与`EXAMPLE_ONLY_NOT_A_REAL_*`标识符，不捏造实际source_segment ID，也不声称发现了任何原文事实。照抄示例ID的回复无法通过原validator。

最终回复直接以原材料包交给冻结`core.validate_scan`；不修正ID、偏移、quote或模型语义，不把两个模型同意变成审阅通过。原validator只产生`SCHEMA_AND_QUOTES_CHECKED_NOT_SEMANTICALLY_CERTIFIED`、`passed=false`。

## 适配接口

```python
projection = project_packet(original_packet, original_manifest_reference)
wire = render_request(
    original_packet, projection, lane, registered_model,
    maximum_request_bytes=registered_byte_cap,
    transport_fields={"thinking": {"type": "disabled"}, "stream": False},
)
# 独立控制器登记预算、保存projection和wire.metadata后才能调用transport。
# transport必须发送wire.body原字节；本模块没有发送功能。
checked = validate_projected_scan(original_packet, projection, provider_json)
```

`render_request`返回`FrozenRequest(body: bytes, metadata: dict)`。内部user content这一JSON字符串先用`base.encode(projection['payload']).decode('utf-8')`规范化，外层body再用`base.encode(request)`生成排序、紧凑、非ASCII转义UTF-8 JSON。因此内存字典与规范文件读回的键插入顺序不同，也不会改变wire hash；冻结core不被修改，system prompt逐字不变。metadata提供`request_sha256`及实际字节数。控制器若通过`json.loads(body)`给现有transport，再用同一个`base.encode`编码，应逐字节相等。禁止在字节检查后追加或修改字段。

`maximum_request_bytes`必须显式给定正整数，没有无限或隐式默认值。先把可选的thinking-disabled及stream-false线格式字段加入请求，再计算**最终真实HTTP body**字节；超限直接拒绝，不截掉原文或任务区间。transport选项不能覆盖model、messages、response_format或max_tokens。这个字节上限不是provider tokenizer核验或输入token计量的替代。

投影检查原材料kind/内容ID、原登记字节hash/大小、完整固定字段、segment内容hash/唯一性及原页字符偏移。未来出现未知packet字段会明确拒绝，不能默默删掉新的重要信息。

## 必要核验与限制

21项纯合成测试通过：全部segments和35个区间不变、空页/警报保留、巨量图像清单移除但hash仍在、投影ID独立且确定、冻结system prompt及4096不变、thinking/stream计入最终字节hash、内外层JSON键序及文件读回wire hash不变、UTF-8精确cap边界和超限不裁剪、运输层不能覆盖契约、重算hash后的删段/删区间仍拒绝、原引用/未知字段/重复segment拒绝、emoji codepoint偏移严格校验及示例ID不能充当真实回复。Ruff通过。

这些是请求格式/谱系控制，不是API成功、语义审阅或最终面板完成。任何真实试运行或全量调用，仍由另一个前瞻冻结的有限预算执行器负责；本模块没有生产调用或预算授权行为。
