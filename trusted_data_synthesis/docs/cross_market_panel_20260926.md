# PDF原生180题编译合同（预备实现，尚未准入）

新增`cross_market_panel_20260926.py`只连接已完成的财务资格、逐文档发行人证据与公开／私有评价合同；不重新解析PDF，不补采来源，不训练或调用模型。当前修订后的实际财务候选为dual14、composition163（仍待独立源穷尽审查）、other29，因此不能编成固定60／60／60面板。程序尚未进行生产登记或真实面板编译，不产生实验效果结论。

## 准入与确定性选择

每个候选必须绑定同一已登记财务pass的事实、报告和版本。发行人需具备法律身份准入、项目历史身份筛查通过，以及本题每份原PDF的独立identity绑定；证券代码不充当独立簇，文本未命中不等于模型没有见过发行人。

composition的状态`PENDING_ISSUER_AND_SOURCE_EXHAUSTION`不满足准入。编译器只接受**另行产生**的`cross_market_composition_source_exhaustion_review`：必须绑定候选题ID、财务协议、指标、三个实际期间、全部相关原PDF hash及逐页文本reference，明确独立完整源语义审查、全部页已审阅、没有同概念三年聚合量。仅没有regex命中、没有抽到某行、parser只输出年度数据或程序填写布尔值，都不能代替该审查。编译器不创建这种证书；没有证书就保留pending并拒绝。

发行人＋目标（组别、数量定义、指标、实际期间、原币种）去重；可替代版本按既有财务协议的发布日期／原文身份元数据规则确定。随后按固定盐的发行人hash轮转，每发行人内部按末期结束日、任务ID排序，每组取60。来源、题量或组配额不因不足而扩大，不按答案大小、模型表现或后续控制结果选择题。

不足任何组60题立即返回未就绪：不加载tokenizer、不构建可调用公开manifest、不发布私有gold，也不启动评价。选中180题之后若context或脚本控制失败，整块面板失败，不换入下一题。

## 公开来源范围与紧凑证据

题目公开写明其原报告vintage(s)。来源编译函数只接收公开题目／实际期间、公开报告descriptor和该报告全部已合格事实，不接收私有答案或见证角色。它公开声明报告、公开时间窗内**所有预登记指标**记录，不只保留解题需要的叶子。

任何相同发行人／指标／实际期间／币种／范围出现不同数值或不同原生定义，整题拒绝；不能悄悄挑与目标相符的数字，或把后期重述替换到旧报告上。保留原始正负号、原币种基本单位、标签／原生定义、实际日期、报告hash／URL，以及真实`pdf://...`页／表／行／期间槽／parser word index定位。

公开每行证据采用紧凑原始定位、原始数值token及单位标题，不重复数千字符的完整期间／列／范围证书。每行仍绑定完整证据hash和原财务事实ID；报告descriptor绑定财务资格记录ID及原PDF／完整页文本审计reference。完整证书保存在不可变审计／私有native binding中。该投影不删任何公开数值记录、标签、定义、期间或币种，不是答案相关裁剪，也没有给模型添加任意文件读取工具。

沿用原英文有限模板，仅将CIK实体槽换为证据中的法律发行人名、USD单位槽换为原币种，并明示报告版本。输出维持百万原币或百分比、两位小数、half-away-from-zero。SYSTEM及五工具接口不变。

## 私有合同、CPU控制与发布

私有bundle采用真正的财务关系证书和算子DAG，不伪装SEC数据。dual生成端点和收入＋已证实符号成本两路径（增长率增加严格正的前期基数）；均值证明三期间，峰值任务证明完整三期比较及同实际期间查找。事实native binding绑定真实发行人簇与PDF原生定位。

选定180题后，最多420次scripted CPU证明控制：各题正向充分轨迹与不受支持Final负向控制，dual另加第二种充分路径。这些不是Student调用或真实模型评分，不能列入4,860会话效果分母。每题只做一次初始tokenization，固定初始prompt最多18,432 tokens，保留4,096历史增长与2,048输出空间，不截断、不改源、不因失败换题。

全部通过后才发布兼容评价桥的`source_view_manifest_v2`、`calibration_panel_admission`、180个真正`EvaluationTaskBundle`、native绑定与`calibration_private_assets`索引。产出`evaluation_panel_references.json`供单独评价登记使用；编译完成不会自动启动模型。生成阶段的全局私有评分屏障仍由评价控制器负责。

## 核验范围

14项纯合成CPU测试覆盖四种目标及实际PDF运行时脚本证明、composition pending／regex不足／内容变更、完整公开指标而非私有角色过滤、冲突vintage拒绝、历史／逐文档身份双门槛、确定性发行人目标去重、配额不足、不替换失败题、完整180公开／私有索引与评价桥接口，以及context溢出。完整180序列化测试隔离验证接口，使用mock控制结果；四类真实符号证明另有独立合成测试。没有访问新PDF、网络、真实Student或GPU。

## 实际执行补充：20:56已拒绝发布

本说明初版之后，代码在`d4304e8f06`冻结，20:56:18登记、20:56:21完成一次生产准入。最终来源/公开视图候选为14／0／25，返回`BLOCKED_GROUP_QUOTAS_OR_SOURCE_GATES`；163个composition保留完整源审阅pending，4个other因公开报告版本的观察冲突被拒绝。未达到60×3，因此没有加载tokenizer、运行真实面板scripted控制、发布公开/私有面板或启动评价。

完成记录为`cross_market_panel_compilation_completed:d26191334b221ed13f58744d92e45aa60db18090ac182bb24be5b8a52214cda3`。[完整执行记录](cross_market_admission_progress_20260926.md)及[失败摘要](../artifacts/qa_vnext_fixed_kernel_value/cross_market_calibration_20260926/public/panel_01_completed.json)保留真实数量与每个拒绝，不将其计作模型Q=0。
