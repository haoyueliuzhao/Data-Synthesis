# R6：保留语义判据的结构简化与固定12调用验证

## 1. 范围与已有证据

本次响应“查看实验。继续推进”，仅处理先前R5已经记录的审阅器结构与字段一致性问题。Base dev883现已结束，但本修订不使用其答案、准确率或个例改变生成prompt、资格、题目集合或五臂设计；V7公开Probe契约保持不变。

R5的12调用中9份通过机械接口、5份语义一致、无length。三次机械失败已对照API原字符串、保存对象及review_text确认：一个把根级terms写进semantic_graph；一个增加semantic_graph.edges_note；一个提前关闭根对象，在尾部又写v_trace。它们均已取得usage，输出5053/5338/1901 token，未触及16384。

请求真实使用beta endpoint、strict:true和指定submit_review；schema仅使用已公布的类型、properties、required、additionalProperties、items、enum，全部对象required齐全并禁止额外属性。未发现本地漏开严格模式、改坏返回或已知不支持schema关键字。[官方strict说明](https://api-docs.deepseek.com/zh-cn/guides/tool_calls/)给出结构约束保证，但本批实际返回仍违反请求schema；不能从这些客户端证据断言供应商内部原因，更不能假称已修复服务端。

另外4份接口通过但语义不一致包含：substantive=true却decision_change=none；后命题不critical；缺少实际动作、关联观察与后续accepted后果等。它们是原记录内的矛盾/缺证据，不因JSON结构改版就自动有效。

## 2. 新wire，不是修补旧模型输出

新增`v6_slot_review.v6`：根级terms/nodes/edges三个数组替代semantic_graph封套；actions和mask采用统一记录数组，显式action_id/target_id。主机仍核对所有原动作/目标ID恰好一次，拒绝缺项、重复、未知或越类ID、额外字段及多段JSON。只有完整匹配新协议的返回才作事前定义的字段投射，继续经过原v5有限语义验证。

投射不移动旧失败中的terms、不删除edges_note、不补括号、不补命题或证据、不把substantive改成false。原请求、原参数字符串及SHA、投射SHA、v5语义基准和新v6身份分开保存。新返回从不冒充v5实际模型返回，旧R5结果不重判、不拼入新双审。

附录仅明确原有实质更新条件，包括critical且accepted后命题、真实动作与关联观察、后续时序、非none后果和accepted更新节点。合法verification仍能获得χ=1；普通计算或提交并不因此自动算实质更新，也不指示模型一律输出false。空Q栏规则保持原v5窄范围零监督，关键未知/矛盾仍阻断。

在同六题原请求上的离线比较中，strict parameters紧凑JSON字符数下降18.85%–43.16%，对象数由18–36降为9；这不是API tokenizer计数、费用改善、语义成功率或供应商strict问题解决的证据。各题继承已登记的16384输出上限；本次问题不是截断，不据此任意加大额度。

## 3. 固定小试与不扩张条件

沿用原预先选择的六题，各取原slot0，双独立审阅，共12个全新调用；不按原native成绩/模型结果选择，不复用任何旧一侧通过。Flash、thinking disabled、4并发、无网络重试/JSON修复/第三审阅，仍使用原共同800元上限、700元预警、258000请求上限。旧UNKNOWN的2.228224元保守预留永久计入占用；不清账、不换数据库，不因本批新ID而重发旧UNKNOWN。

工程门仍要求12/12实际strict返回通过接口、无length、本批无新增未知费用。没有“必须判断有效”的门。小试通过也不意味着原96逐槽＋12对齐门已通过；完整工程验证必须另行登记全108个新调用，不挑旧通过结果拼接。任何真正训练仍需新批原1000题完整共同材料核、状态映射和Student编码，不能直接使用这些旧六题技术样本。

R6注册、预算快照、started、逐项响应/assessment和结果均写入独立`finqa_v6_01/review_revision_06/`。本说明在新模型调用前写入；实际结果另追加，不预填成功。原新8000槽登记仍是未启动，本次没有自动采集、GPU占位或训练。
