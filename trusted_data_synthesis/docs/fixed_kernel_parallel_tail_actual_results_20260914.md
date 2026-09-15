# Fixed-kernel：保留八个原 Student 与并行尾任务的实际结果

本页仅汇总实际闭合报告；训练或归档完成不等于发现正科学效应。
八个已有 A Student 在原进程完成后按原字节导入，历史报告 ID、训练配置与路径字段不重写。
只有 A/minus/47 使用登记的八卡并行 SUM 后端；B 分支仍采用原单卡轨迹训练配置。
公开评测身份指向实际复制的最终 adapter，仍引用原训练报告 ID。

## 材料与执行来源

- 原始采集：10240/10,240；kernel `fixed_kernel:f67d9edd0712d87d6d63d6e9535f8ff2db677cb81c884780afc8315c1d15c729`。
- 采集预算曾由 250M 修订至 350M tokens；不将其描述为原始未修订预注册方案。
- 原轨迹 cache `trajectory_material_cache:587363af1e6e25da9236833df79da620669f8420278ec438f82f217fb554b8bf` 原样复用；无重采样、重分词或 kernel 重建。
- 新执行 authority `parallel_tail_execution_authority:ed45417bbdad434e5c47cf0201425c8ea3f15b68cdd2efef330cec7a9614d73b`；原八个完成运行导入清单 `completed_parent_training_imports:c0eb041864d97e1932866753be42ed042b7cd7b5017eabad7e23c6368e17a8e2`。
- 混合配置 lineage `heterogeneous_execution_lineage:48c2fae2ba55c57ff9f5d9d52517850b2ab2010d47ff24ece03a88ed82e8357a`；原报告配置不被改称统一配置。

## 尾任务实际报告

- 训练报告 `training_report:d72b980706bf54543effadbfdb8af57c85f18607c7d72d1f5ee203eea7be118c`；真实配置 `training_configuration:9959a7beb582708e6e56e89a63d55e5cb44f2a2f524eadaef711ce1b3070e76d`。
- 后端／world size／归约："nccl" / 8 / "SUM"。
- 实际进程退出：[{"exit_code": 0, "gpu_uuid": "GPU-f813ce38-39d7-ab21-f72b-55f87284eaa5", "pid": 3408892, "rank": 0}, {"exit_code": 0, "gpu_uuid": "GPU-0a62363e-fb3c-74fd-c5fe-1a2720c7e66a", "pid": 3408898, "rank": 1}, {"exit_code": 0, "gpu_uuid": "GPU-88a33540-ff55-746e-d82b-45821b463102", "pid": 3408910, "rank": 2}, {"exit_code": 0, "gpu_uuid": "GPU-004a2d75-6298-df4d-7b95-103bc6c1b02a", "pid": 3408934, "rank": 3}, {"exit_code": 0, "gpu_uuid": "GPU-ae8978c8-5100-933e-78d1-46ed781a8a0e", "pid": 3408954, "rank": 4}, {"exit_code": 0, "gpu_uuid": "GPU-f731a280-01e3-2359-ace9-aa2ad2112f55", "pid": 3408979, "rank": 5}, {"exit_code": 0, "gpu_uuid": "GPU-6cf85ebf-ae89-905b-5d97-46f83b295526", "pid": 3408998, "rank": 6}, {"exit_code": 0, "gpu_uuid": "GPU-ab6e97cc-19e4-64b8-f792-7b6920a45434", "pid": 3409022, "rank": 7}]。
- 报告中的 dropout stream："original_single_GPU_serial_native_Philox_offsets"。
- 报告中的原串行掩码重放声明：true。
- 以上随机流描述仅来自实际运行记录，不等于另做了掩码逐位审计。
  FP32 归约顺序变化明确保留；没有声称梯度、optimizer 或最终参数逐位相同。

## 正式结果

- `status`："COMPLETE_NO_POSITIVE_DIRECTION"。
- `actual_training_runs`：9。
- `actual_evaluation_sessions`：1620。
- `confirmation_sessions`：0。
- `independent_positive_effect_confirmed`：false。
- A 开发选择："alpha0"；配对均值增益：{"alpha0": "0", "minus": "0", "plus": "0"}。
- 未执行的确认分支不推断效果；统计结果仍条件于这些已固定训练检查点。

## 单次发布

- 实际执行报告 `execution_report:c2427de4084db9e0865521d53c4b32d2a61983f1f7e3332355b4b07a5b4a916e`；发布 lineage `parallel_execution_publication_lineage:daff86d8d08ebde81ee4b5e59ea035e3d3ba90c7c14057fcdca17785a0849519`。
- 原材料 archive `publication_manifest:457d6009f338c172a665ef177ce1ebb2fd7f528e508b1918cc18bc50212a4ae0` 只复制，不重封。
- 本执行结果 archive `publication_manifest:c4ca72e5703a238fc79c34ac939929ca7b1f3b9a74be75b2c3faaa7a538e342f` 仅封存一次。
- 仅精确暂存密封归档、分页索引、权威小报告及本文；大型 producer manifest 不直接暂存。
- 目标 https://github.com/haoyueliuzhao/Data-Synthesis.git main；普通非强制 push，失败留证且不自动重试。
- 本文不预先宣称 push 成功；远端结果以独立 Git receipt 为准。
