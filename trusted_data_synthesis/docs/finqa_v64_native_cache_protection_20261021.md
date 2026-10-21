# FinQA V64：原 V63 同进程 native 显存缓存保护

日期：2026-10-21，北京时间。

## 1. 当前状态与结论边界

本说明初稿对应实现与 CPU/mock 核验阶段。用户已明确要求“提供保护，防止再次被挤占”，选择“完整断点受控切换”，并询问能否提前预留显存。截至本节形成时，**尚未进行 V64 受控切换，尚未派发 V64 科学 worker，也没有实际执行 V64 显存预热**。旧 V63 worker 的继续运行或自然完成不属于 V64 保护效果。

已完成的分项 CPU/mock 测试为 52 项：资源保护 19 项、控制器及入口 33 项。这些是控制逻辑和模拟资源验证，不是 GPU 数值、碎片、吞吐或抗竞争实验。整体入口核验、冻结来源提交、协议 ID、受控切换及首个真实预热记录须在实际完成后另行追加，不能用本节的实现完成代替运行证据。

本轮不另起 GPU 资源小试，不额外执行 Student forward、反馈、response 回放或 optimizer 更新。保护首次实际验收使用新版本首个真实科学 worker 的预热记录和原资源观测。

科学根仍为：

`trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/v18_researcher_continuation_01/v63_balanced_feedback_repetition_01/`

独立控制根为科学根下的：

`gpu_memory_protection_01/`

原 V63 科学协议 ID 为 `a4e56b5954cad3f578cfa5e8ba7bac64a87810cc857d04ef8c5b736f28b4d8db`，112 文件实施包 ID 为 `4442335a0a1e881bbba25bd97a507f73ce3fcbf7fcc9c14b4b264f8a391b6dc8`。这两个历史身份及原冻结文件不改写。V64 是同一实验剩余工作的运行层修订，不是新的科学对照轮次。

## 2. 授权范围与保持不变的科学合同

授权仅保护本项目自身进程持有和复用的显存，不控制其他项目，不修改 GPU compute mode、系统权限或全机调度规则，不发送信号给其他项目，不另起 GPU 旁路占位进程。

原三父点 seed137、251、389、C1/C05 两臂、反馈批次 b=1、draw101/103、反馈条件、实际参数点、封存奖励、完整轨迹 logP、700 分母、R3 数值和累加顺序均不改变。原完整类梯度只读复用，不新增 class forward，不将 V64 控制协议 ID 替换为原科学条件或 checkpoint ID。

本次交接要求原 4,200 条完整反馈已经齐全；不重新调用其中任何已返回反馈。原六分支 1,788 次有效 optimizer 提交、24 个评价生成作业和 7,458 条评价会话保持，不额外评价 745/test/Hold，不提前统一评分，不改变 V63 主判据。完整科学设计仍以 [V63 说明](finqa_v63_balanced_feedback_repetition_20261020.md) 为准。

已封存完整 response 前缀、正式累计梯度、两个 draw 分量和真实训练提交只读继承，不以切换为由重放或重复提交。未封存的计算若在合法接续中需要重新执行，必须计为维护/恢复开销，不能声称所有物理计算均零重复。

## 3. 问题与保护能力的实际边界

当前环境的 PyTorch 为 `2.7.1+cu128`，使用 `native,expandable_segments:False`。native caching allocator 会保留已释放张量的底层块，后续同进程分配可以复用；`empty_cache()` 会将可释放的未占用缓存归还，使其他 GPU 应用能够使用这些空间。保留缓存的目的，是减少本项目把已取得空间反复归还给系统后再竞争的窗口，而不是阻止其他项目使用其余空闲显存。[PyTorch 2.7 CUDA 内存说明](https://docs.pytorch.org/docs/2.7/notes/cuda.html#memory-management)

原 V63 的 R3 并非每个 response 都无条件执行 `empty_cache()`。清理点主要在模型/阶段边界；训练每个真实提交 step 也调用常规清理；原 V56 容量等待在首次不足时另有一次清理。因此不能把本次保护描述成“修复每条 R3 都释放缓存”的问题。

缓存复用受块大小、碎片和 stream 等条件限制。native allocator 分配失败时也可能释放可回收缓存并重新申请。`reserved−allocated` 只是潜在可复用量的估计，不保证任意下一张量都能得到所需连续块；本轮不更换 allocator、不使用新 `MemPool` 或 `cudaMallocAsync`，也不把缓存数量当作 OOM 安全证明。[PyTorch v2.7.1 allocator 源码](https://github.com/pytorch/pytorch/blob/v2.7.1/c10/cuda/CUDACachingAllocator.cpp#L54-L70)

本项目租约仍只约束遵守同一租约的项目 worker，不是跨用户或操作系统级 GPU 独占。外部进程仍可能消耗真实 free，触发原资源门；本轮只能降低再次竞争的风险，不能保证“再也不会被挤占”或保证完成时间。

## 4. 显存保护实现

### 4.1 预热时机与对象

预热只用于 R3 replay，且每个新冷 worker 最多一次。位置是首次 `prepare_replay_response` 中、原真实 R3 科学调用之前。此时模型已经加载，实际虚拟参数点 theta 已安装，回放需要的持久张量已经就位。

不能只在模型加载之前分配 16GiB 后即声称获得 16GiB 回放余量：后续模型常驻张量可能直接消耗这部分缓存。本实现使用上述更晚的真实边界，不在当前旧 worker 上热改，不通过外部 holder 与 worker 争用显存。

预热执行一次 `torch.empty(..., dtype=torch.uint8, device="cuda:0")`，同步后释放该临时张量引用，但不调用 `empty_cache()`。它不填充随机数，不调用模型，不改 RNG，不执行任何额外 response；临时活跃张量不与随后科学计算同时保留。剩下的是同一 worker 可复用的 native allocator cache。

### 4.2 预热计划与 FULL/PARTIAL/ZERO

记实测物理空闲量为 F、当前 allocated 为 A。预热申请量为下式向下对齐至 2MiB 的结果：

```text
min(16GiB,
    max(0, F − 14GiB),
    max(0, 76GiB − A − 64MiB))
```

14GiB 是规划余量：原 full-KV 上限 8GiB、saved-KV 上限 2GiB、原边界 free 2GiB，再加 2GiB 规划裕量。64MiB 是峰值规划裕量。两者都不是新的科学准入门，也不替代每条实际 response 的精确原门。

| 实际完成的预热申请 | 记录状态 | 允许的表述 |
|---|---|---|
| 16GiB | `FULL` | 完成登记的预热申请；仍须看实际缓存与降级记录 |
| 大于0且小于16GiB | `PARTIAL` | 只获得部分预热，不称足额 |
| 0 | `ZERO` | 本次没有额外预热申请，不称已预留16GiB |
| 申请、观测或停止检查失败 | `FAILED` | 未通过本次预热流程，不进入该次科学调用 |

申请量不等于新增 reserved：申请可能复用原缓存。因此真实记录同时保存 before/after、`actual_warm_allocation_bytes`、reserved 实际增量、潜在可复用量估计及规划 free 是否仍在，不能仅以“申请16GiB”推断驱动新增保留16GiB。`FULL` 也不覆盖随后发生的缓存降级释放；两项应一起报告。

所有预热申请均计入原进程 allocated 历史峰，模型加载也计入同一生命周期；不重置峰值、不删去预热峰。原模型前 admission 中的 `warm_allocation_bytes=0` 仍是当时的事实。新最终 report 则写真实累计预热量，并单列 `inherited_pre_model_warm_allocation_bytes=0`，不能将旧零值当作新运行全过程事实。

### 4.3 保留与有条件降级释放

新私有 `ScientificMonitor.clear_unused` 保留原前后资源观测和 `gc.collect()`，但不再常规执行 `empty_cache()`。训练等经该 monitor 的常规清理也因此保留自身缓存；这些阶段没有新增16GiB预热。

容量等待保留原单次60秒上限及原后继冷恢复规则。若原 physical-free 谓词通过、只是自身总可用容量或主存不足，则不主动清空缓存：清空不会增加该进程的 `free+cache` 总量，还可能形成外部竞争窗口。若原 physical-free 谓词失败，则明确记录降级事件，只释放本进程 unused cache，再执行原新鲜资源检查；不触碰 live tensor 或其他进程。

失败 preflight 仍保留为失败观测，不能因后续释放成功而改写为曾经通过。原 response 已测得的失败边界也不能被稍后空闲量替代。阶段实际完成并释放模型后、进程退出时，原最终清理仍正常归还本进程缓存。

## 5. 原资源硬门与运行策略

| 项目 | V64 继承的要求 |
|---|---|
| 设备及并发 | 物理 GPU0至7；最多6个 worker；每卡最多1个；CPU初始化、等待和 draining 均占名额 |
| 冷启动 free | feedback/distribution/generate 24GiB；train 26GiB；R3 replay 56GiB |
| GPU 历史峰 | allocated 最多76GiB，包含加载和新预热，阶段间不重置 |
| 规定边界 free | 至少2GiB；不被 reserved 或预热额度替代 |
| 进程主存 | 本轮非 class worker 的 RSS 历史峰最多192GiB；原 class160GiB合同不变，本次不新派 class |
| 全机主存 | 有效可用 RAM 至少96GiB余量；启动预算仍沿用原实现 |
| 共享设备 | 已知归属共享准入不变；未知归属/MPS仍阻断；不干预外部进程 |
| 自动恢复 | 仅确认资源/I/O故障，在真实退出及持久断点审计后接续；UNKNOWN、数值/状态/源码异常不盲重试 |

R3 仍执行原两类条件：真实 `free ≥ 2GiB + 当前完整KV估计 + 2GiB saved-KV`，以及 `free + 估计自有缓存 ≥ 2GiB + 当前完整KV估计 + 2GiB saved-KV + 16GiB非KV激活预算`。实际原后端门和 response 后76GiB/2GiB检查仍执行。不得因为预热成功就跳过这些检查。

原无任意等待/阶段截止的运行设置、累计等待、attempt 序号、退避及合法停止行为继续继承；本次不安装新 cron 或全机 observer，不扩展旧信号过滤授权。

原 `resource_policy.warm_allocation_bytes=0` 是旧运行策略字段。新控制协议通过独立 `effective_resource_overrides` 明确覆盖 **R3运行期预热** 和常规缓存清理行为；不是声称旧资源策略的每个字段仍逐字描述新行为。原反馈不预热、硬资源门、科学身份和历史协议仍保持原义。

## 6. 完整断点受控交接

本次批准一次受控切换，而非自动反复尝试迁移。交接前须绑定原监督器和控制器精确 PID/birth、旧队列和原科学协议；确认全部4,200条反馈已完整封存，活跃科学作业仅处于获准的 replay 范围，没有 UNKNOWN 或其他不可覆盖的终止条件。

只允许对核验身份的本项目旧控制器发出登记维护请求，由原协作停止路径处理本项目 worker；不直接强杀 worker、不中断未完整保存的科学状态来伪造退出。实际 response 完整边界须封存正式累计梯度、两个 draw 分量、cursor、RNG及绑定。所有旧 worker 真实退出并结算，旧控制器与监督器身份实际消失，租约、空队列及断点审计全部通过后，才可单次启动新控制版本。

如果出现新的无关停止、UNKNOWN、数值/状态错误、身份变化或未结清 worker，不得把本次维护许可当作覆盖失败的通用例外。旧 STOP、失败、launch、冻结实现和历史资源结果均不回写；新控制目录保存维护、继承、运行与收口证据，新的科学结果仍追加到原 V63 科学根。

已经自然完成并 accepted 的作业只读继承。完成“代码登记”或“控制器启动”都不能自动说明预热已生效；至少须观察新版真实 worker 的预热 receipt 和原科学调用边界。

## 7. 来源绑定、必要核验与证据阅读

新运行层由 `finqa_v64_binding/registration/runtime/worker/controller/entry/handoff.py` 构成，需来自独立提交并冻结。原 V63 112 文件包不修改。每个原模块由 `source_module` 核对其冻结文件来源与 SHA；资源 adapter 对原 V56 cleanup、C1/C05停止选择和依赖导入使用固定出现次数的精确替换；worker 只在私有模块中替换唯一资源入口，并绑定新私有 monitor，不全局替换 `torch.cuda.empty_cache`。

已完成的64项联合 CPU/mock 核验（另补2项维护资源/启动失败回归）范围包括：

- 预热16GiB上限、2MiB对齐、64MiB峰值规划余量，以及partial/zero情形。
- 真实峰值不因释放临时张量而消失，不新增峰值reset；已有硬峰失败先于保护逻辑。
- 不调用 RNG、模型或额外response；预热前后明确停止均阻止继续该次科学调用。
- 原raw-free不足时释放并重新核验，自身总容量不足时保留缓存并有界等待；原失败观测不追认。
- 常规cleanup保留缓存但不绕过原资源门；原worker及原函数不被修改。
- 控制器与入口的继承、冻结来源和维护边界mock测试。其完整实际执行记录及整体核验结果由后续运行节补充。

CPU/mock测试临时目录应按仓库约定在 `artifacts/test_tmp/` 下用 `mktemp -d` 创建。冻结运行层须先于pytest的工作区conftest导入，避免把工作区科学包误加载为原冻结依赖；不能为方便测试放宽生产来源校验。

正式运行后按以下证据区分状态：

| 证据 | 能说明什么 | 不能说明什么 |
|---|---|---|
| 新控制 `protocol/record.json` 与 `implementation/record.json` | 授权和实现已独立绑定 | 不代表切换或预热已发生 |
| 维护/继承记录与旧进程真实退出 | 旧阶段已在合法边界结算 | 不代表新worker已取得缓存 |
| 新控制 `resources/<job>/pid*/cache_warm/record.json` | 本worker真实预热量、before/after及部分/零状态 | 不保证全卡独占、连续块或未来free |
| 原科学 `resources/<job>/pid*/observations.jsonl` 和结果资源report | 原科学边界与新保护/降级事件的实际观测 | 不追认旧失败，不等于整轮完成 |
| 新控制监督/队列及最终收口 | 当前控制尝试、真实退出和最终状态 | 不可仅凭陈旧queue判断进程仍存活 |

后续必须如实记录首次实际预热及是否发生降级、资源等待或恢复。只有整轮原评价与统一评分按 V63 合同完成后，才能报告科学实验结果；保护代码和测试通过不是新的准确率或吞吐结论。

## 8. 后续实际执行记录

整体 CPU/mock 联合执行64项通过；随后新增维护暂停资源硬门、启动失败终止两项回归，交接测试文件最终13项通过，总覆盖66项。没有执行CUDA小试或额外科学计算。

交接还要求内核停止receipt来源明确且没有已报告的receipt队列丢失；ReplayPaused必须同时具有本进程实际资源closeout且全部原资源门通过。新控制器启动若失败，先发布新控制根终止标记，在GPU租约屏障释放前请求停止；退出未确认时如实标记，不宣称已退出。

待实际冻结、整体入口核验、受控交接和首个真实预热发生后追加。本节目前没有声称上述步骤已完成。
