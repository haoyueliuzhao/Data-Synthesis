# 文本主线：独立schema恢复预算

## 目的和原结果保留

主线已有442个packet保存了有效真实文本审核；另一个packet在原两次尝试中分别因重复finding ID和倒序实际日期被严格校验器拒绝。技术停发不等于原财务任务不合格，不能据此换题、删包、放宽validator或修改旧回复。

新增`run_cross_market_text_schema_recovery_20260927.py`只提供一层有限恢复执行。登记绑定原主线协议、已冻结262,144-byte capacity revision、原技术停止快照、442份已保存review引用及最初失败包的两次原reservation/outcome。所有旧记录保持不变；新增预算不退还任何旧尝试。

## 有限调用契约

- 原packet全集固定5,663，不增加来源或候选。
- 每个包仍首先使用父主线正常审核流程。已有review直接复用；没有耗尽原两次尝试的包不得直接使用恢复预算。
- 仅当原两次reservation和技术失败／未结算outcome均存在、来源身份正确且仍没有settled packet review，才能使用额外审核。
- 每个符合条件的包最多2次额外POST；整个恢复阶段最多128次额外POST，以共享锁下不可变reservation计数。
- 原主线预算保持不变；新协议另列两阶段合计上限。额度用尽只保留technical pending，不自动扩预算，不将技术失败用作选样排除。
- 原两次之后未来出现的同类未完成包，可使用这同一128预算；不是每次重启重新获批128次。
- 每次额外POST只有一次底层发送，没有provider内部重试。新增attempt中断后按已占用处理；不会重放同一个attempt，最多使用尚未用过的第二次额外尝试。

登记不调用API。源码提交冻结后，由控制端明确登记和启动；本实现和合成测试本身没有真实请求。

## 新请求与不变的证据

使用相同`deepseek-v4-pro`、相同完整原文投影、同一262,144-byte请求体上限、4,096输出token上限、JSON模式、关闭thinking／stream。只在system提示末尾前瞻追加schema及领域澄清：

1. finding ID必须在单份回复中唯一。
2. 两个实际日期均存在时必须`period_start < period_end`；不明则null，不得编造或倒置。
3. 仅审核四个登记流量指标的真实多年total／cumulative／mean及具体相关疑点。股东权益、留存收益、储备、资产负债表或股息余额／变动表不是这些目标流量；按年度并排列出的普通年度数也不是一个多年合计。
4. 仍须报告真正相关的汇总或不确定性，不能为了得到空数组而省略。

user消息中的完整源payload逐字保持一致。没有自动重排模型日期、重编号重复ID、删除错误finding、模糊匹配或修复旧JSON。新回复继续经过原`semantic.build_packet_review`内部的同一严格校验器；新增执行层不修改该validator全局或科学门槛。

schema恢复不负责裁定已经有效保存的语义疑点；若后续另有任务级证据复核，必须使用自己的明确协议及预算，不计入此128次、不覆盖旧初判。

## 新账本与父协议身份

新增记录位于原主线输出根：

- `schema_recovery_revision_01.json`：独立执行修订协议。
- `schema_recovery_prior_stop_01.json`：原停止状态的不可变副本。
- `recovery_attempts/<packet-key>/<1|2>/`：新增reservation、provider request／raw response／receipt、payload和outcome；与父`attempts/`分离。
- `schema_recovery_budget.lock`及每包锁：限制并行重复与全局超支。

reservation在发送前记录最终clarified request的hash、原耗尽attempt引用和恢复revision引用。成功的新review写入父`packet_reviews/`，仍使用原parent protocol ID和原packet身份，以便既定frontier继续；其`execution`额外记录恢复revision ID／引用和extra attempt编号。request／raw-response引用必须指向本次最终澄清请求的实际物理记录，不能误指父原请求。

已有442份成功review不重新调用、不覆盖；成功缓存可直接恢复。`execution_namespace(revision_record, revision_reference)`供控制端组合其他独立执行层，返回隔离namespace而非修改父模块全局。namespace的`SCRIPT`固定为新恢复脚本，`start`拉起的新子进程仍执行此恢复层，不会意外退回仅两次旧流程。

## 合成验证与完成边界

测试仅使用本地合成packet和假provider，验证：父正常流程优先；未耗尽不能恢复；旧attempt bytes不变；新增request包含澄清而源payload不变；新review绑定实际请求hash和revision；重复finding／倒序日期／非法JSON仍失败；每包额外2次及全局128次不能重置；未结算额外attempt不重放；未登记包被拒绝；成功后不再次发请求。

有效packet review不是任务PASS，更不是整个面板完成。本修订只减少可重现的格式错误导致的停发，是否存在目标多年汇总及任务是否可纳入，仍由既定语义审核和前沿闭合规则决定。真实新增请求数、成功数、失败原因、tokens及128预算余量须在实际运行后据新账本报告。
