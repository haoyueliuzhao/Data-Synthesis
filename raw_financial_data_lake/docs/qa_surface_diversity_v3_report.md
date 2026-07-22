# QA 问题反标准化与 LLM 改写报告

## 1. 目标

问题反标准化不是撤销事实、实体和指标标准化，而是在问题生成的最后一层恢复自然语言中的合理变化。底层语义继续固定为 canonical semantics、Operation Plan 和 Evidence，表层允许使用经过登记的简称、严格同义词、自然时间表达、语体和句式。

最终链路为：

```text
Canonical QA Semantics
→ 确定性槽位白名单
→ 稳定选择非标准表面形式
→ Protected Question
→ LLM 句式改写
→ 独立语义重解析
→ 数字与槽位校验
→ Deterministic Fallback
```

LLM 不接收答案，不生成实体、指标、期间、阈值或 top-k。它只能重排受保护占位符周围的语言。Operation 顺序、比较方向、极值方向和 lookup 语义由程序独立复核。

## 2. 本轮改进

### 2.1 Surface Variation V3

- 将语体扩展为 direct、analyst、concise、comparative、evidence-focused、plain-language、research 和 screening。
- 扩充严格金融同义词，包括收入、利润、资产负债、现金、债务、现金流、资本开支和 EPS 等指标。
- 增加 `FY2023`、`FY 2023`、`the 2023 fiscal year` 等年度形式。
- 增加 `FY2020 Q2 YTD`、`the first six months of FY2020` 等累计季度形式。
- 对安全的 scope 增加 peer group、covered companies 等上下文化表达。
- 默认由本地稳定算法选择白名单槽位变体，LLM 只负责句式改写，结果可复现且不允许模型发明指标别名。

### 2.2 LLM 协议与模型兼容

- Protected Rewrite 最多执行有限次数的语义修复；重试只携带错误码和未变更契约。
- 新增不含事实值的 semantic cues，明确 filter、rank、extreme、lookup 的操作顺序和可观察语言锚点。
- Provider 额外返回的说明字段不参与渲染，记录为 `rewrite_unknown_fields_ignored`；占位符、数字、方向、多问句和扩展结论仍 fail-closed。
- 增加 HTTP 403 模型回退条件。模型发现成功后，可从额度不可用的请求模型切换到可调用模型。
- API 密钥只从 `DASHSCOPE_API_KEY` 读取，不写入仓库、构建报告或样本元数据。

### 2.3 时间与指标语义修正

- FRED、World Bank 和 IMF 年度数据按 calendar year 表达，非年度数据按 observation date 表达，不再误写为公司 fiscal year。
- 复杂排名 follow-up 在缺少显式角色字段时，从 candidate 的有序 metric IDs 恢复主、副指标，避免输出 `primary metric` 等占位描述。

### 2.4 多样性与质量门控

每个 build 现在统计：

```text
unique questions / linguistic skeletons
style variant distribution
surface realization source
denormalization applied rate
average noncanonical slots
slot variant usage
request / retry / fallback rate
```

可配置质量门包括最小非标准槽位均值、最小语体数量和最大重试率。事实、Operation、Evidence 和 Question Parser 门控保持不变。

## 3. 真实 API 小规模回归

最终测试固定 KG：`kg_20260711_062123_bc4b4394`，QA build：`qa_build_20260722_031157_6210ed2d`。请求模型额度不可用时，客户端通过模型发现切换到 `qwen-max`。

| 指标 | 结果 |
| --- | ---: |
| Candidates / eligible | 19 / 19 |
| QA verifier passed | 19 / 19 |
| LLM controlled rewrite | 18 / 19 |
| Deterministic fallback | 1 / 19 |
| HTTP / JSON success | 100% / 100% |
| API requests / retries | 23 / 4 |
| Retry rate | 21.05% |
| Total tokens | 12,999 |
| Unique questions | 19 / 19 |
| Unique linguistic skeletons | 19 / 19 |
| Surface styles | 7 |
| Average noncanonical slots | 1.95 |
| Denormalization applied | 84.21% |

难度分布为 Easy 8、Hard 6、Expert 2、Research 3；包含 13 个 task subtype、8 类 graph pattern 和 7 类 operation sequence。

唯一回退样本是 pairwise comparison。模型连续将“比较两个实体并给出差值”写成两个问句，触发 `rewrite_not_single_question`。系统保留确定性问题并拒绝将其计为受控 LLM 改写。由于 smoke profile 要求 100% controlled generation 和 0 fallback，build gate 正确失败，构建未激活；事实与证据质量仍全部通过。

前一轮在未显式提供 semantic cues 时为 17/19；本轮提升到 18/19。额外 JSON 字段从硬错误改为不可消费的审计警告后，模型兼容性显著提高，而语义门控没有放宽。

完整审计位于：

```text
data/audit/qa_surface_v3_dashscope_20_20260722_v7/
data/audit/qa_surface_v3_dashscope_20_20260722_v7/analysis/
```

## 4. 结论与生产建议

当前实现已经能够在不改变标准答案的前提下，稳定增加指标别名、实体简称、时间形式、语体和句法多样性。设计上应继续坚持：

1. 金融语义、阈值、scope 和答案由确定性程序固定。
2. LLM 只处理受保护的表面表达，并接受独立 Question Parser 复核。
3. 额外 Provider 元数据可以忽略，但任何语义漂移必须拒绝。
4. 生产发布不应强求单模型 100% 生成成功；不合格输出可以安全回退，但应分别报告 LLM 覆盖率与最终 QA 正确率。
5. 扩大到 150 条前，应将 controlled generation 最低门设为可观测的服务目标，例如 95%，同时继续要求最终 QA verifier 100% 通过、unsupported numeric 为 0、fallback 有明确原因。

本轮完整项目测试为 `156 passed`，Ruff 与 JSON 配置检查通过，未发现 API key 或已弃用的 Provider 密钥变量残留。
