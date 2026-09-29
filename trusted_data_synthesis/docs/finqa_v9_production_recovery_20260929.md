# 同一13022矩阵的有限恢复安排

此实现不改变V8审阅规则、请求、容量、原wallet或namespace；不新增技术批。
用户2026-09-29已明确批准原钱包总cap1200及全批可能仍未完成的风险，warning仍700。
模型返回、调用结算和本地文件缺失是不同情况，不能统称“失败后重试”。

## 运行与恢复

在同一冻结worktree、同一输出目录下：

```bash
python -m trusted_synthesis.finance_research.v9_production_review run
python -m trusted_synthesis.finance_research.v9_production_review audit-recovery
python -m trusted_synthesis.finance_research.v9_production_review resume
```

三个命令共享原controller锁。`run`仍拒绝已经有started的批次；`resume`必须显式调用，先检查原矩阵、
原账户invocation、原响应及当前钱包。没有常驻自动重启器，不宣称任何中断都能自动处理。

| 检查得到的事实 | 处理 |
|---|---|
| 结算完整，原response/assessment完整 | 复用，不再次请求 |
| 已结算model_response，但本地response丢失 | 由SQLite中完全相同的原请求/响应bytes、SHA、实际usage及原账重建本地transport工件；新增API=0 |
| 原response在，但本地assessment未完成 | 对原返回执行同一冻结检查；不换更好的返回、不修补JSON或标签 |
| 没有原ledger row，也无本地返回 | 确认未发送，可在原协议/namespace内继续该既定job |
| RESERVED、DISPATCHED或UNKNOWN存在 | 本有限恢复阻断；不能当作未发送，不清账、不释放UNKNOWN、不自动重发 |
| 非model_response的服务失败／无法核实的工件 | 保留并交人工审计，不合成valid或新的成功返回 |

RESERVED虽可能尚未发生HTTP，本实现仍保守拒绝自动重用其reservation；没有假称已覆盖此故障分支。
DISPATCHED标记在实际HTTP之前落盘，可能存在“不知道是否已发送”的窄窗口，也一律不重发。
任何新增UNKNOWN继续触发原钱包halt；此次费用批准不授权伪造usage或清除任意halt。

## 不完整前缀与不可变产物

仍然11382逐槽全部返回后才准备1640对齐，13022完整返回后才封存资格总体。
恢复时不重新请求已结算槽，不把已审便宜前缀冻结为X*。
原首次result保留；恢复审计与结果追加在`resume_attempts/attemptNNNN/`，最新`status.json`给出
`current_result_path`。完整seal、resolution、encoding等确定性产物只可原样复用，不覆盖不同内容。

status中的`dispatched`仍是provider调用尝试数，不是HTTP成功派发或已支付计数；实际费用和调用状态
以原ledger及真实返回为准。暂时不够保留下一次完整在途预留时即停发，并等待在途收口；只看已消费
尚未达到cap不能强行继续。

## 验证边界

7项新增临时SQLite／mock HTTP控制验证完全相同原响应重建、缺失本地检查重放、未发送识别、
RESERVED/DISPATCHED/UNKNOWN拒绝、外来矩阵拒绝；原生产控制器7项回归继续通过。
这些不是新的真实审阅，不证明模型资格产率。启动后遇到超出有限恢复范围的故障仍须如实停机审计。
