# Fixed-kernel writer recovery：实际终态记录

本页只汇总已写出的原始报告，不重新运行实验，也不把封存成功视为科学结果通过。
旧失败批次及其完整分母保持封闭；恢复批不导入旧成功前缀。

## 采集与材料门

- Operator 终态：`STOP_EXISTING_MATERIAL_GATE_FAIL`；记录：`operator_workflow_terminal:43dec0db00d87e8ff10dd7d53812f4c742816f762ddbf7fa8bdcd5bc184fa67d`。
- 采集状态："STOP_INCOMPLETE_OR_CONTRACT"。
- 预注册 session 分母：10240。
- finished session 数：9968。
- 未发出请求的 session 数：157。
- 实际 HTTP 请求数：57745。
- 恢复批保守 token 扣账（不等同于全部已知 usage）：239706046。
- 既有 training gate："FAIL"。
- 共同干预任务数：未提供／未测量。
- 全局质量移动量：未提供／未测量。

## Student 实际结果

材料门 FAIL；operator 未启动 Student prepare/execute，训练与评估均未运行。

## 已闭合封存

- materials：manifest `publication_manifest:dd731d072dae39f53993c4398d0b3b3589bc7fad8b1a016e39bce1a61e0170c7`；203859 个原文件、3651005598 字节、115 个 archive。
- results：未提供闭合 manifest；没有宣称该阶段已封存。

## 发布范围与限制

仅提交固定 workflow 元数据、少量原始顶层报告、清单绑定的 index 页面与 archive。
不直接暂存原始 session/token/kernel 巨型 JSON、控制台日志、钱包、.env 或模型基础权重。
已有 publisher 完成秘密扫描与原件往返验证；本 helper 只核对清单、路径和字节绑定，
没有重做财务语义验证、归档解包、API 请求或 GPU 操作。
项目忽略 artifacts 目录；git add --force 仅用于已验证的精确文件白名单，不扩大暂存范围。
目标为 https://github.com/haoyueliuzhao/Data-Synthesis.git 的 main，普通非强制 push；本页不预先宣称 push 成功。
实际 commit/push 回执保存在隔离 runtime/final_publication_receipt.json。
