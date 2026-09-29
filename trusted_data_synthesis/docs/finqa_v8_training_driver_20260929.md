# V8 五臂训练执行链：实现与验证边界（2026-09-29）

## 结论

本次新增 `finance_research/v8_training_driver.py`，不是再次写一份 admission 声明。
五题完整任务加权反向、真实 AdamW 更新、不可变提交点、恢复、完整类梯度、真实虚拟参数安装、
700 条本地反馈公共封存、封存后原生评分、实际反馈梯度和 clip-aware Adam pullback 都有可调用实现。
它复用已有 `materials.execute_task_batch_update`、冻结 consumer、feedback 和 kernel；没有改写这些内核。

**这不是一次实际 FinQA 训练结果，也不是生产准入声明。** 当前尚无本轮完整的 V8 1000 题共同核及全部
Student 编码；没有加载生产 Qwen、启动 GPU、调用 API、运行真实 700 条反馈或重新评价 Base。
CPU 微型控制证明的是接口与数值执行行为，不证明未来真实材料具备资格，更不证明训练有效。

## 1. 一次性实际文件核验

入口 `load_training_pool(binding_path)` 接收文件清单，不替换库存、审阅或编码本身的 schema。
清单格式 `v8_training_artifact_binding.v1`：

```json
{
  "schema": "v8_training_artifact_binding.v1",
  "review_policy_id": "8bef26302b75eae1cf504df39de8a4da7a794503451edcd6a601805b0969dd99",
  "generation_protocol": {"path": "...", "sha256": "..."},
  "generation_seal": {"path": "...", "sha256": "..."},
  "inventory": {"path": "...", "sha256": "..."},
  "resolutions": {"original-task-id": {"path": "...", "sha256": "..."}},
  "encodings": {"original-slot-id": {"path": "...", "sha256": "..."}},
  "tokenizer_binding": ["tokenizer_digest", "chat_template_digest"]
}
```

路径可相对清单。真实读取每个引用文件的 bytes、核对 SHA，解析后缓存；训练 hot path 不再扫描磁盘。
`generation_protocol` 是实际 `v8_independent_public_generation_launch.v1` 的
`<generation_root>/registration/protocol.json`，不是旧 ed78 材料登记本身。
新 launch 的 `original` 保留旧 ed78 全登记：角色从 `original.role_plan` 取，槽从 launch 顶层 `slots` 取，
源路径使用 `original.original_snapshot`。复用 `validate_material_registration` 核验旧登记的整数
histogram 历史身份，不重写原文；同时核对原登记文件 SHA/嵌入原件/原 ed78 ID 和新 launch ID。
`generation_seal` 必须位于同一输出 root 下，schema 为 `v8_whole_generation_seal.v1`，
`protocol_id` 绑定新 launch。实际 seal 行没有 `episode_path`：加载器使用既有 `slot_directory`
从已登记槽推导 `slots/<slot-hash>/episode/episode.json`，不信任用户填写的替代 episode 路径，
再核文件 SHA、内容 digest、配置、COMPLETE/实际 calls/stop reason/settlement。
`inspect_generation_binding(entry)` 可单独只读验收上述公共前缀，不读取任何生成结果，也不准入训练。
未来 semantic inventory 必须单独形成；`v8_native_full_population_support.v1` 明确不能冒充材料库存。
源 snapshot 和 role plan 仍由既有公共源校验器核实，不能把任意子集写成原始 1000 题。
完整 8000 generation seal、每题八原槽、所有原件、全部 1000 resolution 都须在。

本轮只接显式新 `v8_common_material_resolution.v1`、`v8_student_encoding.v1`，
不将旧有限资格、旧 165 子集、作者脚本、旧评审失败或技术小试视为可训练共同核。
`not_assessed_native_ineligible` 只能出现在 `q_native == false` 的槽中；其含义不是 process invalid。
所有 `Q_native=true AND V_trace=valid` 的原包必须保留、整题映射完成、双审 mask 一致。
任何原题缺支持、遗漏难映射包、缺编码或长度溢出均阻断；不删题，不补采，不筛 NLL/长度。

每份编码核对原 episode、完整 mask manifest、实际 tokenizer/template、每响应原文 hash、row hash、
完整上下文长度及因果 target 坐标，`L_P` 必须等于全包全部监督 token 总数。
所有原响应 row 保留；零 target row 只是不发起空 loss backward，后续完整 prompt 中的错误/撤回历史不裁掉。
此处不重做语言学资格判定，也不伪造 API TokenReceipt、API 采样 token 或数值 final answer。

## 2. 真实一步与三种分母

`TrainingDriver.step()` 实际调用冻结 consumer。每步从统一 schedule 取五个不同完整任务，
每任务消费所有原合格包，每包每段 target 的系数为：

`pi(z|x) / (5 * n_xz * L_P)`。

task sampler 的 `mu/(B*p_s)` 已化成 `1/5`，不再除一次 batch；不同 target 层也不各自归一化。
每步 sum CE backward 全部包后只做一次全局 clip(1)、一次 AdamW.step。
R/U、认可行动、Final 及其认可 EOS 用同一 mask；工具观察/system/user 不监督。
driver 使用已有编码数组，不在每步重分词。

生产配置检查 AdamW `lr=1e-4, betas=.9/.999, eps=1e-8, weight_decay=0`，
LoRA `q_proj/v_proj, rank8, alpha16, dropout.05` 及 FP32 训练坐标。
模型检查直接复用仓库 `load_student/install_adapters` 使用的自定义 `LowRankLinear`，不依赖
`peft_config` 或另一个 PEFT 装载方式。实际每层 q/v 都须为该类，A/B shape 对应 rank8、scaling=2、
Dropout=.05、A/B为同设备可训练FP32；所有其余原始 Base 参数必须冻结且为BF16。
可将 `load_student` 返回的 scope 传给 `TrainingDriver(..., adapter_scope=scope)`；scope 的内容身份、
目标名、实际 shape 和参数数均与已安装模块核对，并进入 checkpoint 绑定。这个结构检查本身不证明
adapter 是 freshly initialized；fresh 初始化与 resume 是正式运行登记中的不同操作。
调用方仍负责原始 Base 模型装载、fresh adapter 初始化、设备准入和正式运行登记；本模块不是自动 GPU launcher。

原 1000 题 schedule 复用 `build_task_schedule`：seeds11/29/47，每 epoch 从原顺序独立 shuffle，
10 epochs、2000 steps、每题恰好访问十次，各臂同 seed 使用相同 schedule。

## 3. 共享400、分支与提交恢复

`arm='shared'` 只能到400；生产分支必须从实际 shared400 checkpoint `restore(..., branch=True)`。
保存实际 trainable 参数、模型 buffer、冻结 Base 参数 digest、Adam moments/step/config、
Python/Torch/CUDA RNG、schedule 与当前步、π/r、已完成外环坐标。
固定 Base 本体不在每步重复保存；恢复必须匹配其实际 frozen parameter digest。

每个 checkpoint 用已有不可变目录发布器写完整 `state.pt + record.json`，原子提交后才允许下一步。
异常发生于反向/step/保存时，内存标记 tainted，不能继续；必须明确恢复已提交点。
重建 driver 指向已有目录不会从0静默重跑。它不自动寻找或猜测最新 checkpoint。
目前每一步保留提交点，400/800/1200/1600/2000自然保留；不含自动清理或空间回收策略。

Manual± 在实际400分支时执行既有固定 `normalize(r * 2**(±chi))`，不使用 C、N 或 feedback，
也不把 Manual− 当作机制实验的 first-direction reverse。
`conditional_sharing_proof` 只有真实 C-only/Full step400 outer commits 的参数、Adam、RNG、schedule、π/r、
G、gJ、C、pullback 及同一个700反馈 seal 全部相符才返回 true。奖励个数相同不构成共享证明。
共享是可选优化；driver 不自动省略臂，也不按理论预减预算。

## 4. 完整外环真实接线

在400/800/1200/1600，C-only/Full 的下一步被阻断，直到 `outer_update()` 真正完成：

1. 在 eval/dropout-off 下，对每个状态的全部原包算实际平均梯度 `g_xz`，包含所有单状态控制题。
   类梯度在 CPU 保存，冻结核每次仅将一个状态搬到模型设备；这是缓存内存策略，不改变权重或求和域。
2. `prepare_virtual_point` 从当前真实 Adam state 和全人口 `G=sum mu*pi*g` 创建 clip-aware `theta_bar`。
3. `LocalFeedbackCollector.collect` 真正安装该虚拟参数，绑定 actual parameter digest 的 LocalTorchProvider。
   使用公共 source/role 中固定350反馈题、两个预先指定且不同 sampling seeds，不另抽题。
   固定 V7 harness、32步、2048输出、24576上下文、T=1/p=1/k=0；本地调用不属于 API 模型例外。
4. 两个350组均完整封存后，再创建共同700 `SealedFeedbackCohort`；只有此后才读取私有参考并计算 native reward。
   正常模型失败为0；基础设施或参考异常仍 unknown，不能改成0。
5. `feedback_gradient` 使用真实 receipts 的所有实际生成 token/logP（包括错误、恢复和 EOS），固定分母700。
   不读取 SFT mask。生产禁止注入测试 replay/callback，默认调用已有真实分段 replay 后端。
6. 调用既有 pullback/centered-C/anchored-update；C 已含 μ，driver 不再乘 μ/π。
   C-only 只去掉 N 项；Full 保留原登记参数。全零 reward 保持 π 原样，不做 N-only 漂移。
7. 保存 outer commit 后方可执行下一 training batch。

虚拟参数安装结束后，无论正常或失败，都恢复 live 参数、训练模式与 RNG；不会用虚拟 Adam 更新覆盖真实 Adam。
公共反馈 intent 先写入；同一真实点一旦产生未完整封存尝试，后续会拒绝自动重采。
两个350组都已完整封存时允许重读同一原件、重做离线 replay，不重新生成。
不会恢复一部分反馈后抽新样本填满700。

## 5. 已完成 CPU 控制与尚未完成事项

本轮 focused tests 包含：真实五完整任务/15原包一次更新、精确 `1/30` 系数、
真实参数变化、单次 zero_grad/clip/step；保存/恢复真实 Adam 与 dropout RNG 后下一 batch 完全重现；
已存在目录拒绝从0重启；真实 step 后保存前失败必须回滚恢复；类梯度不改变模型/Adam/RNG；
真实虚拟参数安装与恢复；CPU LocalTorchProvider 生成的真实测试 receipts 经 seal、gJ、pullback 的零反馈保持；
缺 collector 外环阻断；固定 Manual±；缺材料/错误 SHA/旧编码 schema 拒绝；tiny pool 不准 CUDA；
反馈 partial intent 禁止重采和提前读私参。
另以 CPU 两层 Qwen 形状模型实际调用既有 `install_adapters`，验证无 `peft_config` 仍通过、
BF16前向和FP32 A/B反向真实可用，并拒绝错误rank、dropout、k替代v、遗漏v、篡改scope及FP32 Base。
完整文件契约控制另用1000×8明确标记的 synthetic 原件写出实际 V8 launch/seal 字段，
真实读取文件并核 SHA，通过槽目录推导装入全部原件、1000份 resolution/encoding；测试中禁止读取 private gold，
并验证 native_support 替代 semantic inventory 会被拒绝。此控制不生成真实模型评审或金融实验结果。

这些控制不等于生产 Qwen 已完成训练、700反馈已完成、材料全历史都能编码、CUDA replay 已验收，
也没有 Experiment1–3 的训练价值结果。
当前明确剩余阻塞是全新1000×8生成及原生必要条件、V8全量审阅/映射/完整编码、真实生产装载与资源准入。
loader 未对“尚不存在的完整真实包”完成端到端验收；须在其真实形成后运行实际文件校验。
本次没有 Base/dev 结果驱动的 prompt 调参，也没有重跑 Base、数学实验或额外金融测试组合。
