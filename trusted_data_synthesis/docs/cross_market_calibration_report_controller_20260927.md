# 跨市场短程校准：独立统计、报告与自动发布入口

## 范围与状态

`scripts/run_cross_market_calibration_report_20260927.py`是独立收口控制器，不修改既有评价协议、评分函数、统计数值核或任何旧结果。本文描述实现与合成验证，不宣称真实4,860会话、统计或报告已经完成。

截至实现时，九个step240保存点均已存在；新增三条反向尾段合计120个已提交更新、120次更新计量，已于2026-09-26北京时间11:46:19完成。已有六个Static／正向保存点继续保留复用信用。真实评价能否启动仍取决于新180题面板通过全部准入。

## 调用与等待

在独立工作树、原项目Python环境及其`PYTHONPATH`下使用：

```text
python trusted_data_synthesis/scripts/run_cross_market_calibration_report_20260927.py start --root /tmp/data-synthesis-fixed-kernel-parallel-tail-20260914
```

`start`启动CPU等待进程；`watch`每30秒只检查状态，先等待固定`cross_market_calibration_cache_20260926/evaluation_01/protocol.json`出现，再登记统计合同，随后等待完整评价封存。它不会为了等待而运行模型、提前评分、读取未封存Q或修改任何上游阶段。首次等待时核验源码已经提交，保存其hash；后续登记必须仍匹配等待时源码，不能在已载入旧代码的后台进程中登记新代码。

另有`register`、`run`、`status`、`publish`命令，以及对应Python接口。输出固定在`cross_market_calibration_cache_20260926/statistics_01/`；不能借命令行选择新数据、种子、统计参数或另一个评价根。

## 准入与结果身份

登记只读评价协议、公开面板准入、发行人准入及面板编译协议，绑定有限文本／表格审阅bundle ID和引用，不读取原API回复或新Q。

统计前必须满足：

- 评价完成记录明确4,860个已评分会话和18份报告，且所有已知评价worker已经退出；PID出生身份沿用原控制器的`started`优先于`launched`规则。
- 原全局generation seal真实覆盖九个参数点、18个cohort、4,860条轨迹，随机／greedy共用相应模型点，跨arm采样种子配对；在该核验之前不开评分报告。
- 每份评分报告与seal、对应generation manifest、参数点、公开面板、runtime、训练seed、arm、解码模式及逐条task/repeat/group/session身份完全匹配。随机cohort各360条、greedy各180条；缺失、重复或非二值Q均拒绝，绝不补Q=0。

训练seed取报告头的11／29／47，不使用generation job中的逐轨迹采样seed。统计直接调用原`cross_market_statistics_20260926.analyze`：三组各60题、固定20,000个有效发行人整簇样本、最多200,000次抽样、随机种子20260926。四个比较共用重抽样权重，随机与greedy分别解释；不修改原科学计算。

## 有限恢复与发布

统计最多2次计量尝试，预扣费后才调用数值核；仅已记录的`MemoryError`允许同输入、同随机种子的有限恢复。未知中断或数值／身份错误停止，不自动改预算。原子保存的统计结果可直接用于重建报告，不再次计算统计。若bootstrap自身达到已登记抽样上限而未完成，保留不完整状态和原限制，不扩额。

中文报告和JSON保留整体、组别、seed及seed×组×repeat的四项配对比较、精确分数、区间、bootstrap摘要、九个模型保存点、原训练信用、负向完成记录及实际评价物理计量。报告明确限定文本／表格语义域，未读图像不获得视觉审阅信用；来源准备API调用与Student4,860会话独立列账。本统计阶段不新增生成，不等于整轮没有新生成。

报告只自动stage、commit及push以下两条固定路径：

- `artifacts/qa_vnext_fixed_kernel_value/cross_market_calibration_20260926/public/calibration_final_report_20260927.json`
- `docs/cross_market_calibration_report_20260927.md`

路径均位于`trusted_data_synthesis/`内。发布有独占锁，Git操作前持久化尝试计量；最多8次，间隔至少300秒。推送失败不重训、不重新评分、不重算统计，也不会提交其他工作树改动。

## 必要验证

30项纯合成CPU测试通过（最终4.36秒），ruff通过。覆盖生产形状4,860条映射、错误cohort/session/Q拒绝、封存前禁止读取评分、固定统计登记不读私有输入、分析恢复上限、发布幂等及预扣费、指定文件提交、等待状态，以及旧未知launch身份不妨碍已明确退出的worker。未为这些测试加载真实Student、读取真实评价Q、占用GPU或联网。

无论本轮随机／greedy支持标志如何，报告仍必须明确：这是固定中港来源、三个固定训练种子的短程跨市场校准，不能自动确认原美股反馈分布上的训练价值，不能替代完整400步新独立确认。
