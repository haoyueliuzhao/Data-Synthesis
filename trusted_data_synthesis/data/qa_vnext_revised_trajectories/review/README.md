# 合格 QA 轨迹人工审阅

18条轨迹均按“明确问题 → 选择依据与方法 → 执行操作 → 判断并接受结果 → 使用结果继续推导 → 给出有依据的答案”整理。每一步分别说明当前目标、主要判断、实际操作、结果与接受、后续使用。文字是基于公开决策、操作和引用关系的说明性转述，不是模型逐字原话。

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

所有58次操作分别核对观察结果、后续明确接受及消费顺序；全部28次未准入提交分别说明随后调整。已接受但未使用的结果明确标注。原始输入、精确数值与完整纠正历史保存在[数据包](../README.md)。

重建命令：`python trusted_data_synthesis/scripts/render_qa_trajectory_review.py`。
