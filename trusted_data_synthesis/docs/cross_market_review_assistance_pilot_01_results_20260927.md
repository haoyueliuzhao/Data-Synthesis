# 文本辅助审阅试点01：真实执行结果与只读失败审计

## 结论及适用范围

本次有限试点已真实完成10次HTTP请求，全部取得正常传输响应及usage记录。原冻结验证器仅接受2份响应，另外8份按原规则保留失败。被接受的2份均为**0条findings**，分别包含7条、12条uncertainties；这只表示JSON结构与原文绑定检查通过，不是财务语义判断正确、全文没有三年aggregate或全源审阅完成的证据。

本次未启动全量6,099包／12,198辅助任务；独立原文终审、逐页视觉审阅、全源穷尽证书、正式180题模型评测及新训练更新均为0。不能据此确认训练价值，也不能把有限传输试点称为整体实验完成。

## 冻结记录、时间和预算

- 代码冻结commit：`7fe58252e2ea3ee9f69e33130f26f03cff016e6b`。
- 执行协议：`cross_market_source_review_assistance_execution_protocol:5f51d05354c390b31d22844c5028ecdda89d5d9572c853cad71dad94d92f309d`。
- 完成记录：`cross_market_source_review_assistance_pilot_completed:25bff1a02dca19cf96a10168773b6a4dea43e5a4feaa8cde1c83af6a1eb90dab`。
- 北京时间登记：2026-09-27 01:12:26；完成：01:14:03，登记至完成约97秒。登记时间不等于首个HTTP实际发送时间。
- 独立输出根：`cross_market_calibration_cache_20260926/original_evidence_revision_02/source_review_assistance_pilot_01/`。
- 选择规则：在模型输出前固定packet ID字典序最前4包及原始JSON字节最大1包，共5包；每包discovery／challenge各1次。不是按本次结果或财务答案筛选。
- discovery固定`deepseek-flash`；challenge固定`deepseek-v4-pro`；并发2；总预算10次物理POST，每job只调度1次，无自动重试、模型发现、fallback或跳转。
- 单响应输出上限4,096 tokens；10份传输收据均为`RESPONSE_SAVED_NOT_SEMANTICALLY_REVIEWED`，物理请求合计10。响应传输成功不等于下游JSON／原文校验成功。

已报告输入tokens为105,924，输出tokens为27,019，总计132,943；usage未知请求为0。这里报告实际provider usage，不换算未经本报告核算的货币成本，也不把失败请求视为免费或退还预算。

原始材料包、05财务结果、零API材料阶段及01协议／request／raw response／reservation／scan result全部保留。结果未被新的提示词、定位算法或事后响应修补覆盖。

## 逐响应失败矩阵

以下packet采用唯一的16位hash前缀缩写；完整身份由协议中的`selected_packets`及`scan_results`绑定。`quote唯一`只表示模型原样返回的字符串在其声明segment中恰好出现一次；没有去空白、大小写转换、模糊匹配或跨segment搬移。

| Packet hash前缀 | 通道 | finish_reason | 输出tokens | 可解析findings | 原冻结验证结果及只读诊断 |
|---|---|---|---:|---:|---|
| `000472583d647af4` | challenge | stop | 1,433 | 2 | 失败：2个quote在声明segment中不存在，在该包其他segment也不存在。 |
| `000472583d647af4` | discovery | stop | 2,951 | 9 | 失败：8个quote唯一存在但报告offset错误；另1个quote在整包各segment中均不存在。 |
| `002f16a3eaa34248` | challenge | stop | 1,920 | 7 | 失败：7个quote均唯一存在，但全部报告offset错误。 |
| `002f16a3eaa34248` | discovery | stop | 1,069 | 0 | 仅结构／原文校验通过；7条uncertainties，未作独立语义认证。 |
| `004eccb0a5bb65f7` | challenge | length | 4,096 | 不可完整解析 | 失败：输出达到上限，JSON字符串被截断。 |
| `004eccb0a5bb65f7` | discovery | stop | 2,123 | 8 | 首先失败于额外顶层字段`type: "json_object"`；另8个quote均唯一存在但报告offset错误。未删除该字段。 |
| `0069894ba80641d4` | challenge | stop | 3,609 | 13 | 失败：13个quote均唯一存在，但全部报告offset错误。 |
| `0069894ba80641d4` | discovery | length | 4,096 | 不可完整解析 | 失败：输出达到上限，JSON字符串被截断。 |
| `1200e28c235bc74c` | challenge | stop | 1,626 | 0 | 仅结构／原文校验通过；12条uncertainties，未作独立语义认证。 |
| `1200e28c235bc74c` | discovery | length | 4,096 | 不可完整解析 | 失败：输出达到上限，JSON字符串被截断。 |

最终状态仍为：`ASSISTANCE_RESPONSE_SAVED_NOT_ADMITTED` 2份；`SCAN_ATTEMPT_FAILED_NOT_REFUNDED` 8份。

## 分层计数与解释边界

10份响应中，7份`finish_reason=stop`且完整JSON可解析；另3份均为`length`、输出4,096 tokens并发生JSON解析错误。没有修复括号、补字符串、拼接部分finding或把截断前可读文字计为完整结果。

在7份完整JSON中，packet ID全部正确，segments声明全部覆盖其原包，无遗漏、额外项或重复；finding ID无重复，已返回的metric／classification／reasoning声明及uncertainty来源字段未发现本次冻结校验器所拒绝的值。这些仅是结构和来源绑定性质，不证明分类、期间、scope或语义解释正确。截断的3份不参与这些“完整声明”结论。

5份带findings的完整JSON共返回39条findings：

- **0／39**条的模型报告start/end与quote共同精确匹配原segment切片。
- **36／39**条的原样quote在声明segment中唯一逐字存在，但报告start/end错误。
- **3／39**条的原样quote在声明segment及该包其他segment中都不存在，不能声称只需修正offset。
- 此39条中未观察到“quote存在多次导致唯一位置不确定”的情况；该结论只适用于本次39条，不保证后续来源。

按原校验器首先遇到的失败分类，8份失败分为：3份截断／非正常完整结束，4份exact source quote失败，1份顶层schema失败。该首因分类不排斥多问题：schema失败的1份仍有8条错误offset。

只有`002f16a3…challenge`的7条及`0069894b…challenge`的13条，属于整份完整响应的所有findings均仅观察到“原词唯一存在但offset错误”的情况。此可定位性诊断不是获准事后修复的依据，更不是两份新增通过结果。其余完整失败中，存在原词缺失或schema违规，不应一概描述为可修复的索引问题。

不同数据包、文种、原文内容和输出长度会影响结果。5包是预先登记的工程试点，不是随机代表样本；不能从2／10推断全量成功率，亦不能据此次tokens／耗时给全量审阅或正式模型实验作无条件外推。特别是通过响应均0 findings，当前尚未验证“模型返回非空定位并严格通过”的实际成功实例。

## 后续前瞻修订，而非改写01

本次结果支持明确的工程诊断：让语言模型直接计算长原文Unicode字符offset不可靠，同时4,096输出预算出现截断。不能靠放宽原文一致性、改写引文、模糊匹配、移除额外字段或补全截断JSON来提高本轮通过数。

拟议02将另立协议、代码冻结、独立输出根和独立10次预算，仍使用同5个原始packet。新请求前瞻提供绑定原文的line IDs，由模型选择原始行范围，确定性line ledger派生该范围的原始quote与Unicode offsets；原模型响应和派生定位记录分别保留。该修订是在检查01结果之后设计的工程修订，**不是对01 outcome-blind的追加验证**，也不是给01退还预算或改判。

本文只报告01真实完成结果；不声称02已登记、调用、完成或取得通过。02必须保持全部原文、原包身份、严格line范围及引用证据检查，不能把行号有效视为财务语义正确。行号格式本身也不保证消除输出截断，后续仍需如实报告新失败。

无论文本辅助格式如何修订，独立原文终审及58,711原页的真实视觉覆盖仍未完成。API定位JSON、程序生成offset或返回`passed=false`的辅助结果，均不能取代全源语义穷尽证书；在证书及其他固定门槛满足前，不启动正式面板评测或声称新的正向训练价值。

## 审计方法

本报告基于AI助手对已保存10份响应及其5个冻结packet的只读逐项检查：finish_reason、JSON完整性、packet／segment身份、finding ID唯一性、所有39条finding的原文切片及原样quote在声明segment内的逐字出现次数。只读诊断不重发API、不打开PDF、不查看图片、不调用财务资格枚举、不更改任何生产结果。它不是人工签署证明，也不是独立全文财务语义／视觉认证。
