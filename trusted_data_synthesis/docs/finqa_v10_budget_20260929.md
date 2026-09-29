# V10 新批同钱包用途与双子额

## 范围与状态

本说明记录前瞻实现及临时 SQLite CPU 验证，不是实钱包已登记、已付费采集或实验完成的证据。实际登记由主控制器完成。代码不创建替代钱包，不改变原预算配置、历史请求、原 65 个 UNKNOWN 或其保留额。

固定新批 ID：`finqa-v10-20260929-new8000-01`。原 1000 题每题 8 个新槽位，全部仍为 `common_material_candidate`。新生成、A/B 审阅、每题一次映射分别使用 `v10gen:`、`v10review:`、`v10map:`，坐标由专用 helper 作 SHA256 绑定，不复用旧生成或旧生产审阅 ID。

## 金额与请求数

金额使用整数微元（1 CNY = 1,000,000 micro-CNY）。费用是原冻结价目表对实际 usage 的向上取整上界，不等同服务商发票。

| 范围 | 请求数上限 | 费用风险上限 |
| --- | ---: | ---: |
| 原钱包总计 | 258000 | 1200 CNY |
| 冻结历史 | 40076 | 已结算 336.264329 + 保留 144.834560 CNY |
| V10 新生成 | 199000 | 100 CNY |
| V10 A/B 审阅与一次映射合计 | 17000 | 550 CNY |
| 未分配、不可自动使用 | 1924 | 68.901111 CNY |

原预警值仍为 700 CNY。原 950 请求 buffer 仍禁用，不能在 1924 之外再加一份可用容量。子额之间不可借用；全局上限与用途子额同时检查。请求数包括已保留的请求，而非仅返回次数。费用风险包括 `settled + RESERVED/DISPATCHED/UNKNOWN held`；UNKNOWN 在确认弃用后仍永久占用原完整保留额。

199000 次生成容量不保证 8000 个最多 32 轮的会话一定完成，100/550 CNY 子额也不保证完成。用尽任何适用硬限时停止，不删困难题、不调用余量、不重发 UNKNOWN。

## 登记与调用接口

入口位于 `trusted_synthesis.finance_research.v10_budget`：

```python
generation_episode_id(batch_id, task_id, slot_index)  # slot_index 0..7
review_episode_id(batch_id, slot_id, reviewer)         # reviewer 'A'/'B'
map_episode_id(batch_id, task_id)

register_v10_batch(
    original_wallet_path,
    expected_run_id=original_run_id,
    expected_config_sha256=original_config_sha256,
    batch_id='finqa-v10-20260929-new8000-01',
    generation_slots=slots,  # 8000 {slot_id,task_id,slot_index,purpose}
    evidence={'user_authorization': audit_authority, ...},
)
ledger = open_budget(original_wallet_path)
status = budget_snapshot_v10(original_wallet_path)  # preflight 的同义只读入口
```

登记要求原实库存在、原 run/config 哈希匹配、全局有效上限 1200、预警 700、请求上限 258000、精确历史计数和金额、全部 65 UNKNOWN 已有不可变确认、`pending=0` 且无 halt。登记时进行一次历史行金额/数量核对，随后只维护两行用途计数。原配置 JSON 和 V8 配额行不变；新增三个 V10 表、两个索引、两个记账触发器和不可变登记事件。

登记后，旧进程即使持有先前打开的 `ProbeBudget` 实例，新增 reserve 也会读取当前 V10 登记：旧 `v7-slot:`、`v8review:`、`v8prod:` 和未登记新 ID 均不能取得容量。历史已有 ID 同样不能再次发送。

`ProbeBudget.reserve` 保留模型 `deepseek-flash`、`thinking=disabled`、实际 HTTP body 与坐标绑定。仅 V10 精确审阅/映射白名单新增容量档位 `2048/4096/8192/16384/32768/65536`；旧配置的 `allowed_output_limits` 不变，旧用途不能借用 4096/8192 等新档位。生成仍只允许原兼容档位 2048/16384，并由冻结生成协议进一步限定每个请求的真实值。结算始终检查该请求保存的 `max_tokens`，不是其他任务的输出上限。

## 原子记账与恢复

SQLite `BEGIN IMMEDIATE` 在同一事务内检查总额/子额、插入请求和用途 allocation。触发器在原 ledger 状态转移的同一事务内更新用途的 requests/dispatched/spent/held/pending/unknown。全局计数必须等于冻结历史加两个新用途计数；V8 消耗数必须停留在登记时值。事件索引用于已存在 UNKNOWN 确认的精确查找，避免每请求重复扫描全部历史事件；不改写历史事件。

仅确定未发送的 `RESERVED` 可显式继续原请求：

```python
continue_reserved(ledger, invocation_id,
                  coordinates=original_coordinates,
                  request=original_request,
                  request_body=original_exact_http_bytes)
ledger.mark_dispatched(invocation_id)  # 必须先成功，再由 provider 发出 HTTP
```

继续操作必须精确匹配坐标、哈希和 HTTP bytes，不重新扣请求数或保留额；原子的 `mark_dispatched` 最多允许一个发送者。`SETTLED` 只能由上层重用原返回 bytes；`DISPATCHED` 不因进程重启而重新发送；`UNKNOWN` 不重试。

## 新批网络 UNKNOWN 的有限终态政策

政策随 V10 子额登记，不沿用旧审阅的网络终态 ID。允许主控制器在所有在途请求 drain 后显式调用：

```python
receipt = acknowledge_connection_unknowns(
    ledger, batch_id=batch_id,
    expected_requests={invocation_id: original_request_sha256, ...},
)
```

必须覆盖当前全部未确认 UNKNOWN，且每项都属于本新批精确 whitelist/allocation，曾 `mark_dispatched`，原请求为 `deepseek-flash`，保留额完整，HTTP status/body、usage、结算均为 None。仅登记的 Connect/Read/Write Error/Timeout 或 RemoteProtocolError，无服务返回的真实证据，且 `reason == 'v10 transport response or usage unknown'` 才可进入该政策。

只清除当前精确被覆盖 halt，并检查该 halt 后的所有 halt 事件没有混入来源、费用格式、HTTP 服务错误或其他不在集合内的问题。幂等读取旧回执不清除后来 halt。每个新确认仍兼容原钱包对原 UNKNOWN 行哈希和保留额的审计；不改原行、usage、计数或保留额。

返回 `records[]` 明确记录 `model_response=None`、`model_usage=None`、`model_result=None`、`material_eligible=False`。这是未得到模型返回的终态，不是假审阅、不是 native=0，也不授权替代调用。上层必须分别报告实际返回数和已处理终态数。

## 必要 CPU 验证

只使用临时目录内合成/复制的 SQLite；未打开实钱包、未调用 API、未使用 GPU。新 28 项覆盖两子额并发请求上限、已结算＋held 金额上限、用途不得借用、原配置和旧 UNKNOWN/行不变、旧队列阻断、小档位仅新用途、真实请求 cap 结算、RESERVED 原 bytes 继续、全部在途 drain、多 UNKNOWN 全集合绑定、非网络和后来 halt 不绕过、幂等回执不重复收费/放行。

相关五文件回归 81 项通过；最后 SQL 排版、事件索引及回执原事件绑定调整后，另行重跑新 V10 文件 28 项通过（22.78 秒）。复现命令（项目虚拟环境，工作树根目录）：

```bash
PYTHONPATH=trusted_data_synthesis/src trusted_data_synthesis/.venv/bin/python -m pytest -q \
  trusted_data_synthesis/tests/test_finance_v10_budget.py \
  trusted_data_synthesis/tests/test_finance_v6_probe_budget.py \
  trusted_data_synthesis/tests/test_finance_v8_request_partition.py \
  trusted_data_synthesis/tests/test_finance_v9_monetary_amendment.py \
  trusted_data_synthesis/tests/test_finance_v9_network_unknowns.py
```

这证明本地接口与账务控制，不证明新批已实际完成或最终材料具有训练价值。生成、审阅、映射、材料准入和 CUDA 训练各自的真实完成证据仍由对应控制器登记。
