# 封存生产 worker、Token 与改写账本只读审计

结论：PASS_AS_SCOPED。在下述限定范围内未发现实质缺陷；不构成外部独立金融语义认证，也不授予训练资格。评测面板的财务目标／期间语义不在本审计范围内，本结论不能解除其他审计发现的评测准入阻断。

审计对象：生产提交 `dd7567a11961176c2aea07680438ba06c9a36a07`，封存目录 `catalog_bridge_20260912`。本 sidecar 位于封存目录之外，没有修改生产代码或产物。

可复跑程序：`trusted_data_synthesis/scripts/audit_qa_vnext_catalog_bridge_worker.py`（不在冻结生产代码清单内，SHA256 `cd702628a79743fe318e3b5139c5c5f4194e64c075b3495cebeb6164ca210632`）。使用项目 `.venv/bin/python` 运行，默认只将 JSON 写到 stdout。最终脚本复跑结果在相邻 `_worker_audit_reproduction.json`：5,413 次断言、0 失败；比初始审计多 3 条结束时的只读保持／未导入模型和 tokenizer 检查，其他实测数量一致。

- 全部 2,080 个主 manifest 成员的字节数与 SHA256 相符，共 1,134,775,464 bytes；68 个冻结代码文件相符。审计前后 manifest 与 controls/report.json SHA256 均未变化。
- 36 个脚本会话离线重放，与保存的 assessment 完全一致。188 条事件含 35 个首 Final，另 1 条无 Final；首 Final 后没有继续生成。实际方法为 endpoint 16、movement 10、control 4、未定 6。
- 29 条 MAPPED、7 条 PENDING_REVIEW 合理：后者包括 6 条预期不合格边界，及 1 条财务有效但格式恢复细类仍待定的记录。独立比较确认等价表达细类相同；重复重算、实质修订、来源执行顺序具有不同细类；重复重算没有被称为独立来源核验；替代依据交叉核对没有覆盖首 Final 的 endpoint 方法。
- 30 个脚本原样包、167 行均与实际原响应和完整输入历史相连。独立检查 token 数组、causal shift、mask、labels、后缀排除以及无需 tokenizer 的公开 chat 渲染通过。目标 Token 合计 9,284，完整序列 Token 合计 636,097；单行长度 1,216—6,904，低于冻结的 24,576，且后者低于模型实际 32,768 上下文。
- 本次未加载 tokenizer。生产记录的 1 次加载与冻结代码的单一 `_binding_and_tokenizer` 路径一致；这是代码路径和记录支持，不是新增的独立动态构造计数器。本次也没有重新做 token-to-text 解码。
- 15 个增量改写请求对应 10 个新任务：10 次初始、5 次合同修复。逐次 request / receipt / raw_response / reservation 的任务、尝试、模型、用量闭合。prompt 8,480 + completion 1,720 = 10,200 Token；历史 211,338 + 本次 10,200 = 221,538，剩余总额度 999,778,462；无未结算或预算 breach。
- 请求体归档会排序 JSON 键，直接对归档对象再次序列化会出现 15 个哈希假阳性。按冻结发送器原始键序还原后，15/15 请求 body 均与原记录 SHA256 完全一致。原始 wire body 未作为单独字节文件保存，因此该项依赖冻结序列化规则重建，不能把排序后的归档字节称为原始 HTTP body。
- Teacher、Student、训练资格、权重及 GPU 路径均与保存的零调用标记和 instrumented guards 一致；这些 guards 不是正式 OS 隔离，也不审计服务器其他无关活动。14 个现有 family / quantity / surface 交叉格没有补造缺失的两格。

生产与开发严格区分：旧开发末轮是 9,263 个目标 Token、49,152 上限，前两次开发物化实际共构造 tokenizer 4 次；这些不作为最终资格证据。最终生产是 9,284 个目标 Token、24,576 上限、修复后的单加载路径。

本审计执行 5,410 次断言求值（包括重复嵌套身份检查，不是 5,410 个独立测试或样本），最终未解决缺陷 0。审计复用了冻结确定性 evaluator 进行重放，并独立实现哈希、原样历史、数组/mask、chat 渲染和账本三方复算；执行者仍是原实现团队，不冒称外部审计。
