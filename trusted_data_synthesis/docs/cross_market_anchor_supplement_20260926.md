# 三种精确原文行标签的缓存补锚模块

本模块只提供新注册阶段的纯内存扫描，不自行登记、读文件或执行生产扫描。根控制器须先提交/冻结代码与有限协议，再统一扫描同440份报告的既有7,530个selected geometry页；不能只扫先前看起来有收益的18项关系缺口。没有PDF重读、图像、网络/API、Student、财务资格或任务枚举调用。

## 固定标签与非目标边界

只支持整行标签`Revenues`、`Cost of revenue`、`Cost of revenues`。匹配只使用Unicode NFKC、空白折叠与casefold，不添加同义词，不删任意前缀/后缀语义。保留原文大小写和原词索引。`Cost of goods sold`、单数`Revenue`搭配下一行`Goods and services`的层级结构、无标签小计、`Other/Total Revenues`、`Cost of revenues excluding ...`均不补锚；也不按毛利减收入或数值闭合反推成本。

原行至少含两个完整可识别原数值词；百分比、破折号或附注不能变成零。附注列表/标记只在明确语法范围内保留为未分配原词；不会在扫描阶段区分金额属于哪年或哪些数字是附注。出现其它语义词则保留拒绝，不通过清理文字扩大标签。

## 返回接口与额度

`scan_document(original_extraction, geometry, doc)`要求内容身份正确、完全相同的原报告身份、已完成缓存几何且page集合恰为该报告已注册的selected pages。返回：

- `new_anchors`：每个新原物理行一个候选，ID为`source_geometry_anchor:<sha>`。
- `mechanical_reviews`：与新候选一一对应，`mechanical_checks_passed=False`，明确待财务资格，不伪造旧parser/机械信用。
- `skipped_existing`：同页、同概念、同字面标签已有任何原候选时保守跳过，不论原候选曾通过还是失败；原标签去空白的key仅用于重复抑制，不扩大新标签匹配。
- `rejected_rows`：命中字面前缀但含不支持的额外词或少于两原数值词；其它不相关行只计`outside_registered_literals`，原缓存仍完整保存。
- `counts`：`original_candidates`、`selected_geometry_pages`、`inspected_geometry_lines`、`outside_registered_literals`、`literal_prefix_rows`、`skipped_existing_rows`、`rejected_literal_rows`、`new_row_anchors`。

`MAX_ROWS_PER_DOCUMENT=64`；超过时抛`AnchorCapExceeded`，不返回截断的前64条。根控制器累计全部报告后必须调用`enforce_global_anchor_cap(total_new_rows)`，`MAX_TOTAL_ROWS=1024`；总超限同样失败，不能按配额截选。扫描页与新行身份不受金额大小、闭合、旧模型Q或准入产量影响。

## 与既有财务核的字段边界

新候选提供`financial_facts`实际读取的shape，但没有来源证明的旧式字段明确为`None`：期间、金额、币种/scale、财务范围、报表类型、parser列号/表ID以及period/unit/statement旧定位页。`None`不是零，也不是metadata年。`extraction_metadata.statement_title=None`、`period_inference=not_established_new_geometry_anchor`；状态固定`NEW_LITERAL_GEOMETRY_ROW_ANCHOR_UNQUALIFIED`，QA/KG eligibility为0。

有直接证据的字段仅包含原document/raw SHA/URL、物理页、原几何行及word indices、原字面标签、未分配数值/注号词坐标、geometry ID和hash派生的新候选ID。`row_index`显式是新geometry行号，不冒称旧parser表格行。完整信息保存在`source_geometry_anchor_provenance`和`UNQUALIFIED_PLACEHOLDERS`合同中。

随后的一次统一财务资格运行应把原9,513个候选原封不动保留，另行并入这些新候选及pending review。核心仍需从真实几何重新确定合并范围、日期、币种、单位、列数、版本和财务关系。根控制器必须在新事实/裁定中保留补锚来源，不能把新候选称为旧parser成功或仅凭scan完成升级为事实。

本模块未进行真实扫描，不预报会新增多少行/事实/题，更不保证双路径60题。本次仅实现与合成测试，实际额度消费与结果由另行冻结的执行协议记录。
