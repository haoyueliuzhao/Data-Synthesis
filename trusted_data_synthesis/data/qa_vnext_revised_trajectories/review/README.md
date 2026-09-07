# 合格 QA 轨迹人工审阅

18条轨迹均按“问题 → 关键证据 → 主要推理与操作 → 最终答案 → 纠正情况”整理。说明依据实际公开执行记录编写；中间长小数以约数展示，最终答案保留原精度。

阅读时可重点比较B01/B02的多步增长率计算，以及Share轨迹中“直接使用披露总额”与“使用本会话求和结果”两种实际分母来源。

| 轨迹 | 问题 | 实际运算次数 |
| --- | --- | ---: |
| [task_panel_F01](task_panel_F01.md) | Huntington Ingalls Industries 在2014年第一季度的营业收入是多少？ | 1 |
| [task_panel_C01](task_panel_C01.md) | Huntington Ingalls Industries 在2014年第四季度的营业收入和营业利润，哪项更高？相差多少？ | 1 |
| [task_panel_G01](task_panel_G01.md) | Huntington Ingalls Industries 的营业收入从2014年第二季度到第三季度变化了百分之多少？ | 3 |
| [task_panel_A01](task_panel_A01.md) | Huntington Ingalls Industries 在2014年第二至第四季度的平均营业收入是多少？ | 4 |
| [task_panel_D01](task_panel_D01.md) | Huntington Ingalls Industries 的营业收入从2014年第一季度到第二季度增加或减少了多少金额？ | 3 |
| [task_panel_R01](task_panel_R01.md) | CDW 在2016财年的营业利润与营业收入之比是多少？ | 3 |
| [task_panel_B01](task_panel_B01.md) | CDW 从2015财年到2016财年的营业收入增长率和营业利润增长率，相差多少个百分点（取绝对值）？ | 8 |
| [task_panel_F02](task_panel_F02.md) | Huntington Ingalls Industries 在2014年第一季度的营业收入是多少？ | 1 |
| [task_panel_C02](task_panel_C02.md) | Huntington Ingalls Industries 在2014年第四季度的营业收入和营业利润，哪项更高？相差多少？ | 1 |
| [task_panel_G02](task_panel_G02.md) | Huntington Ingalls Industries 的营业收入从2014年第二季度到第三季度变化了百分之多少？ | 3 |
| [task_panel_A02](task_panel_A02.md) | Huntington Ingalls Industries 在2014年第二至第四季度的平均营业收入是多少？ | 4 |
| [task_panel_D02](task_panel_D02.md) | Huntington Ingalls Industries 的营业收入从2014年第一季度到第二季度增加或减少了多少金额？ | 3 |
| [task_panel_R02](task_panel_R02.md) | CDW 在2016财年的营业利润与营业收入之比是多少？ | 3 |
| [task_panel_B02](task_panel_B02.md) | CDW 从2015财年到2016财年的营业收入增长率和营业利润增长率，相差多少个百分点（取绝对值）？ | 8 |
| [task_panel_S02](task_panel_S02.md) | Union Pacific 及其子公司在2015财年的货运收入占营业总收入的百分比是多少？保留六位小数。 | 3 |
| [support_exploration_E02](support_exploration_E02.md) | Union Pacific 及其子公司在2015财年的货运收入占营业总收入的百分比是多少？保留六位小数。 | 3 |
| [support_exploration_N03](support_exploration_N03.md) | Union Pacific 及其子公司在2015财年的货运收入占营业总收入的百分比是多少？保留六位小数。 | 3 |
| [support_exploration_E04](support_exploration_E04.md) | Union Pacific 及其子公司在2015财年的货运收入占营业总收入的百分比是多少？保留六位小数。 | 3 |

计数中的运算包括读取数据和数值计算；接受中间结果、修改提交和提交最终答案不单独算作运算。

各页说明对应各自会话的实际路径，未将重复执行合并为同一个会话。原始输入、精确数值与完整纠正历史保存在[数据包](../README.md)。

重建命令：`python trusted_data_synthesis/scripts/render_qa_trajectory_review.py`。
