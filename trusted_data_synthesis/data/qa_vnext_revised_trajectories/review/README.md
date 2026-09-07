# 合格 QA 轨迹人工审阅索引

本目录展示上次抽取的全部18条合格轨迹：八任务面板15条、Share支持探索3条。每条轨迹单独成文，包含公开题目、最终答案、证据、逐次提交与反馈。

合格会话内的未准入提交和纠正历史全部保留。步骤编号T1起算，对应原sequence+1。展开区域展示解析后的完整模型提交，JSON经过排版；原始响应字节见数据包及来源工件。此处展示公开决策与执行轨迹，资格沿用冻结结果，未新增模型调用或人工审阅结论。

两个实验及Share的N/E提示条件分别标识，不将这些会话视作独立任务或合并统计总体。

| 轨迹 | 任务类型 | 提交数 | 准入 | 未准入 | 题目 |
| --- | --- | ---: | ---: | ---: | --- |
| [task_panel_F01](task_panel_F01.md) | fact_retrieval | 3 | 3 | 0 | What is Huntington Ingalls Industries's revenue for 2014 Q1? Report the result and identify the source. |
| [task_panel_C01](task_panel_C01.md) | registered_cross_metric_comparison | 3 | 3 | 0 | Compare revenue with operating_income for Huntington Ingalls Industries for 2014 Q4. Which metric is higher, and by how much? |
| [task_panel_G01](task_panel_G01.md) | temporal_growth | 7 | 7 | 0 | How much did Huntington Ingalls Industries's revenue change from 2014 Q2 to 2014 Q3? Report the percentage change. |
| [task_panel_A01](task_panel_A01.md) | temporal_average | 9 | 9 | 0 | What was the mean revenue for Huntington Ingalls Industries across 2014 Q2 through 2014 Q4? Use every listed observation and identify the sources. |
| [task_panel_D01](task_panel_D01.md) | temporal_absolute_change | 8 | 7 | 1 | Calculate the signed absolute change in Huntington Ingalls Industries's revenue from 2014 Q1 to 2014 Q2. |
| [task_panel_R01](task_panel_R01.md) | registered_ratio | 7 | 7 | 0 | Calculate CDW Corporation's operating_income-to-revenue ratio for FY2016 using the registered financial ratio definition. |
| [task_panel_B01](task_panel_B01.md) | derived_growth_absolute_spread | 18 | 17 | 1 | Across FY2015 to FY2016, what is the absolute percentage-point spread between CDW Corporation's revenue growth and operating-income growth after calculating both growth rates? |
| [task_panel_F02](task_panel_F02.md) | fact_retrieval | 3 | 3 | 0 | What is Huntington Ingalls Industries's revenue for 2014 Q1? Report the result and identify the source. |
| [task_panel_C02](task_panel_C02.md) | registered_cross_metric_comparison | 3 | 3 | 0 | Compare revenue with operating_income for Huntington Ingalls Industries for 2014 Q4. Which metric is higher, and by how much? |
| [task_panel_G02](task_panel_G02.md) | temporal_growth | 7 | 7 | 0 | How much did Huntington Ingalls Industries's revenue change from 2014 Q2 to 2014 Q3? Report the percentage change. |
| [task_panel_A02](task_panel_A02.md) | temporal_average | 9 | 9 | 0 | What was the mean revenue for Huntington Ingalls Industries across 2014 Q2 through 2014 Q4? Use every listed observation and identify the sources. |
| [task_panel_D02](task_panel_D02.md) | temporal_absolute_change | 7 | 7 | 0 | Calculate the signed absolute change in Huntington Ingalls Industries's revenue from 2014 Q1 to 2014 Q2. |
| [task_panel_R02](task_panel_R02.md) | registered_ratio | 7 | 7 | 0 | Calculate CDW Corporation's operating_income-to-revenue ratio for FY2016 using the registered financial ratio definition. |
| [task_panel_B02](task_panel_B02.md) | derived_growth_absolute_spread | 17 | 17 | 0 | Across FY2015 to FY2016, what is the absolute percentage-point spread between CDW Corporation's revenue growth and operating-income growth after calculating both growth rates? |
| [task_panel_S02](task_panel_S02.md) | source_explicit_part_whole_share | 12 | 7 | 5 | For Union Pacific Corporation and subsidiaries in fiscal year 2015, what percentage of total operating revenues was total freight revenues? Report to six decimal places and cite the actual calculation support. |
| [support_exploration_E02](support_exploration_E02.md) | source_explicit_part_whole_share | 16 | 7 | 9 | For Union Pacific Corporation and subsidiaries in fiscal year 2015, what percentage of total operating revenues was total freight revenues? Report to six decimal places and cite the actual calculation support. |
| [support_exploration_N03](support_exploration_N03.md) | source_explicit_part_whole_share | 8 | 7 | 1 | For Union Pacific Corporation and subsidiaries in fiscal year 2015, what percentage of total operating revenues was total freight revenues? Report to six decimal places and cite the actual calculation support. |
| [support_exploration_E04](support_exploration_E04.md) | source_explicit_part_whole_share | 18 | 7 | 11 | For Union Pacific Corporation and subsidiaries in fiscal year 2015, what percentage of total operating revenues was total freight revenues? Report to six decimal places and cite the actual calculation support. |

合计展示18条合格轨迹、162次提交，其中134次准入、28次未准入。

## 生成与验证

源文件：`../trajectories.qualified.jsonl.gz`。SHA-256：`12786777ddf700072dc4a3c3aff621d0336d2999122796c671b8e78f42f99b40`。

生成时校验源文件哈希、每条完整合格包及最终QA验证标记、连续事件序号，并确认每次提交均有独立步骤且完整parsed对象出现在对应页面。这验证审阅视图覆盖性，不重新判定模型或答案质量。

仓库根目录重建命令：

```bash
python trusted_data_synthesis/scripts/render_qa_trajectory_review.py
```

