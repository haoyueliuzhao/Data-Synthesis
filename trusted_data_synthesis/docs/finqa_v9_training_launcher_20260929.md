# 条件性 FinQA 五臂生产启动与恢复入口

## 1. 实施范围与当前证据

本次新增 `finance_research.v9_training_launcher`，只负责把已经冻结的条件性材料接入现有真实 Student 与训练驱动，不另写优化核、材料资格规则或反馈替代品。对应依据为2026-09-29阶段审计及用户对条件性五臂研究总体修订的确认。

本次只进行了CPU mock控制与有限CPU张量检查，没有加载生产Qwen、初始化CUDA、占GPU、调用API、采集反馈或启动训练。因此“启动入口可以执行”不等于“材料已就绪”，更不等于“正式CUDA训练与700反馈已验收”。实际N未知，本文不给820或其他数字预填训练任务数。

原1000题全覆盖协议的未准入状态保持。新入口要求同时存在原1000题/8000原槽父库存、一次完整生产资格流程形成的固定X*、以及所有共同有效原包及其状态、共识mask和完整Student编码；它不接受调用者任意拼出的子集。

## 2. 材料及Student前规模门

使用 `v9_conditional_training.load_training_pool(binding_path)`，生产原件、完整处理范围、原包及编码检查仍由该严格加载器完成。启动器只增加便宜的身份绑定与实验可识别门，不重复实现加载器：

- 实际N>0；
- D_pi>0，即确实存在状态分布可以改变的任务；
- 至少一题在共同支持内同时存在chi0/chi1，避免名义Manual±与Static完全相同；
- 所有单状态题照常保留，不通过删除它们提高灵活任务比例；
- pool、support manifest、完整capability profile及动态日程身份一致。

这些只是最低代数识别条件，不是统计功效保证。材料冻结后、任何Student结果产生前，由研究负责人显式登记薄规模决策 `v9_pre_student_scale_decision.v1`。其绑定实际pool_id、support_manifest_id、N、完整capability profile hash和execution_plan；决策为 `proceed_exploratory` 或 `stop`，附理由及条件性范围确认。当前入口不自动声称有统计功效，后续结论限于这份固定经验支持域。此记录不可在结果出现后覆盖。

若总体、共同原包、mask、映射或编码不完整，或者上述识别门不成立，加载/登记即停止，不查询或占用GPU，也不选择容易前缀训练。代数门不成立时可以直接保留材料profile的停止结论；不能通过删题、补包或改审阅规则使启动器通过。

## 3. 真实模型与五臂调用链

正式执行调用原 `finance_qa_vnext_pq_student.model.load_student`：

- 原始本地Qwen2.5-7B-Instruct绑定；原装载器验证冻结权重文件、形状及软件；
- Base参数冻结为BF16；
- 每层仅q_proj/v_proj安装仓库原有 `LowRankLinear`；
- r=8、alpha=16、dropout=0.05，A/B为FP32；
- 调用时仅传 `trainable=True`，不传任何历史adapter路径；
- 检查fresh B全零、A非零且有限、Adam状态为空，并记录实际adapter摘要；
- AdamW lr=1e-4、betas=(0.9,0.999)、eps=1e-8、weight_decay=0；无额外调度器。

每个种子11/29/47独立执行：

1. 同一fresh Student完成共同2s前缀，s=ceil(N/5)；
2. Static、Manual+、Manual−、C-only、Full各自从真实共同保存点恢复模型、Adam、RNG、pi及任务日程；
3. 各臂通过 `ConditionalTrainingDriver.run_until(10s)`完成后续历史；
4. C-only与Full在2s、4s、6s、8s通过原驱动执行真实外更新；最终必须完整登记四次；
5. 所有步骤仍由现有任务梯度、优化器和保存逻辑执行。末批为真实1—4题时，驱动使用实际B_j，不伪造或删题。

同一seed在一张卡上顺序完成五臂。三个seed可由独立进程在三张有余量的卡上并行；也可以在同一张卡上按seed顺序执行。没有通过结果选择臂或提前淘汰Full。

## 4. 真实700反馈，不用SFT mask替代概率

自动臂使用原 `LocalFeedbackCollector`，绑定原公开snapshot、role plan和固定350题×2种子。公开合同保持V7输入/工具，反馈temperature=1、top_p=1、top_k=0、max_steps=32、max_new_tokens=2048、context_limit=24576；Student采样在虚拟点实际安装参数后运行。

复用原collector的完整700统一封存后评分、原反馈梯度及零奖励处理，不把SFT正目标mask当作反馈轨迹概率。反馈数700不随实际N变化。

反馈目录按seed、arm分开，启动器保守地不假定C-only与Full同点，不宣称节省采集或计算。每臂8s后续加共同2s，总核心物理训练为126s；不使用未经实证核对的120s共享缩减。

## 5. 设备准入与资源释放

必须先完整加载并核对材料、范围决策和源代码绑定，随后才查询指定GPU。登记允许使用的GPU index及最低空余MiB，worker运行时记录实际UUID并再次核查。

默认最低空余24576MiB，只是有余量时允许尝试的启发式，不证明该显存足以容纳所有实际长序列、梯度和反馈。已有其他进程不自动排除该卡；不要求完全空闲，不杀其他进程，不占位等材料，也不在已加载模型后等待另一块卡。显存不足时直接停止本次启动；OOM或其他异常保留已有提交并退出，后续需显式恢复。

同一输出目录的seed锁及GPU锁避免本启动器多个worker冲突；锁不分配显存，也不能控制其他项目的资源竞争。`CUDA_VISIBLE_DEVICES`使用选定实际UUID，在真实模型初始化前设置。需要换卡恢复时使用新进程，不在已经初始化CUDA的进程内重映射。

## 6. 明确恢复语义

首次执行使用 `run-seed`。seed目录存在后必须显式使用 `resume-seed`，不得默认fresh重启。

恢复选择当前臂最高步数的完整实际提交；同一步的outer提交优先于step/branch，避免已经完成的外更新被再次执行。提交的模型参数、Adam、RNG、pi、材料身份和日程仍由原驱动验证和恢复。重载时原装载器创建fresh壳，再恢复原提交；这不是新一轮fresh训练。

共享前缀只执行一次；已经完成的臂可以恢复到终点而不增加步数。所有五臂都完成后生成seed结果，保留每臂真实最终checkpoint引用。

启动前检查固定反馈目录。如果任何已开始点缺少两个draw的generation seal，直接停止且保留原件，不创建新的反馈目录、不删除部分样本、不重采。完整封存但后续处理未完成的反馈由原collector按原身份复用。此入口不提供隐式修复、重试或跳过反馈的功能。

## 7. CLI

以下命令是材料实际就绪后的调用方式，不是本次已执行记录。运行环境使用仓库既定venv，`PYTHONPATH=trusted_data_synthesis/src`。所有路径必须指向真实冻结工件。

先由负责人基于真实profile登记范围与规模判断：

```bash
python -m trusted_synthesis.finance_research.v9_training_launcher scale-decision \
  --material-binding /absolute/path/material_binding.json \
  --output /absolute/path/scale_decision \
  --decision proceed_exploratory --scope-confirmed \
  --rationale "对实际冻结profile的事前规模判断；有限灵活支持，仅作条件性探索解释"
```

登记完整启动合同，不加载Student：

```bash
python -m trusted_synthesis.finance_research.v9_training_launcher register \
  --material-binding /absolute/path/material_binding.json \
  --scale-record /absolute/path/scale_decision/record.json \
  --output /absolute/path/five_arm_training \
  --gpus 0,5,7 --minimum-free-mib 24576
```

独立worker执行一个完整seed的五臂：

```bash
python -m trusted_synthesis.finance_research.v9_training_launcher run-seed \
  --output /absolute/path/five_arm_training --seed 11 --gpu 5
```

29、47必须使用同一登记合同。可以在其他登记GPU上开独立进程，或待上一seed结束后使用同一卡。明确恢复：

```bash
python -m trusted_synthesis.finance_research.v9_training_launcher resume-seed \
  --output /absolute/path/five_arm_training --seed 11 --gpu 5
```

源代码或材料工件字节改变会被拒绝，不借恢复重写原登记。

## 8. 验证及未完成边界

新增CPU控制覆盖：材料门在设备查询之前；有占用但余量足够允许尝试；显存不足不加载/占位；原load_student fresh参数；共同前缀分叉五臂；四次外更新调用顺序；外更新提交后故障显式恢复且不重复；partial700阻断；singleton/chi不变支持拒绝名义五臂；实际profile规模决策；fresh B与Adam检查。

这些是隔离的CPU mocks和小张量检查，不会制造真实反馈、材料、训练效果或CUDA验收记录。完整Qwen/CUDA、实际700反馈、真实多状态训练规模仍待材料准入后执行。

本入口不重跑Base、不自动运行dev/test，不实现新的评价框架。冻结合同保留完整dev883和后续test1147，训练终点会给出实际保存点供既有评价链路接入；未评价之前不会宣称Full−Static或其他效用差。C方向3s、N局部5s的真实步保存点由原驱动保留，但此入口本身不自动开展Exp2反方向短训/诊断，亦不声称Experiment0–5整体完成。
