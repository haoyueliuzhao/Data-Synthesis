# FinQA评测版本核验修复与八卡恢复

2026年10月5日完成更新：本轮于北京时间04:56完成主dev与全部机制评价，最终结果见[完整实验报告](finqa_v18_five_arm_final_report_20261005.md)。下文恢复过程、测试与15:02观察保持为原始历史记录。

2026年10月4日13:58，十五个训练分支全部完成。随后评测登记被源码一致性保护拒绝，原六卡调度器保存失败并退出。用户授权“处理问题恢复评测”，并进一步要求“八卡全部纳入可用范围”。本次新增外置、版本化的评测恢复入口，不修改旧Base协议、冻结运行时、训练结果或既定评测方案。

本次已恢复原十五模型dev及其后续预登记机制实验与汇总。15:02的观察确认八张卡上的评测worker均已实际生成会话，另有七个模型排队。不重训，不追加API，不重采训练反馈，不重跑Base，不打开public test或Experiment 5；评测尚未全部完成，不能据启动状态报告模型成绩。

## 失败原因和严格适用范围

原 `v9_final_evaluation.public_evaluation_contract` 比较九个评测源码文件和四个原生评分文件。十三项中仅 `providers.py` 的全文件SHA不同，另外十二项以及此前的题目、公开视图、工具、系统提示、配置和角色检查均未触发拒绝。

Base评测源码来自提交 `39f090c2f3ecd13d3b04aa26bb037c1ebf3eb05e`。当前训练与评测的数值实现继续来自既有 `finqa-v18-researcher-continuation-20260930` 冻结目录。两个providers版本唯一差异位于 `DeepSeekFlashProvider.chat`：

```python
# Base登记时
httpx.AsyncClient(timeout=self.timeout)
# 当前冻结实现
httpx.AsyncClient(timeout=self.timeout, trust_env=False)
```

该变化影响API客户端是否读取环境代理，但本轮Student dev使用 `LocalTorchProvider`，不调用DeepSeek。不能据此宣称两种API行为等价，也不能任意忽略整个providers文件。

新增证明只接受下列固定全文件哈希对：

| 角色 | SHA256 |
| --- | --- |
| Base providers | `d22c7836aab85a4ace9e98559e20d0d207cb79755ce90be9eae5f82b13c555d9` |
| 当前冻结providers | `add33ed7e4229b87ed5e0766d73b4f14e2c5f6a3ec69a92475f77d51715f1f01` |

证明同时核对实际文件哈希、唯一精确字节逆变换、真实AST调用及其所属类和异步方法。移除这一处 `trust_env=False` 后，完整文件必须重现Base哈希；`LocalTorchProvider`源码和其余文件字节必须相同。任何额外改动、第二处匹配、字符串／注释冒充节点、不同方法或调用者自选哈希均拒绝。

这是源码适用性证明，不是新的CUDA数值等价性测量。证明明确记录 `numerical_equivalence_measured=False` 和API调用为0。

## 登记桥接和真实运行时记录

恢复入口复用原 `public_evaluation_contract` 和 `register` 的字节码，仅在函数副本中将providers交由上述独立严格证明；其余十二个源码及全部公共评测合同继续走原检查。

返回合同补回providers的实际当前哈希，并内嵌完整证明及外部证据绑定。最终登记中的 `evaluation_source_sha256` 和 `runtime_binding` 均记录实际V18源码，没有冒充Base哈希，没有修改旧Base记录，也没有以新的Student结果重选Base或评测条件。

原worker的 `checked_plan`、模型安装、生成、评分和机制实现保持不变。原登记流程仍须完整验证十五个实际1490步终点的状态文件、参数摘要、有限FP32适配器、seed、arm、日程、材料和outer历史；这一次正式注册同时作为必要的终点准入检查，不另外重复运行GPU小试。

## 八卡资源范围

原训练／评测协议的设备政策已允许GPU0至7在显存足够时共享。本次新增独立评测资源登记，将后续调度范围扩为 `[0,1,2,3,4,5,6,7]`、最大并发8；没有修改已完成训练分支的原执行profile。

| GPU | 实测NUMA节点 | CPU亲和性 |
| --- | --- | --- |
| 0、1、2、3 | 0 | `0-37,76-113` |
| 4、5、6、7 | 1 | `38-75,114-151` |

新资源登记保留原24576 MiB空闲显存门槛、加载前复查、GPU锁和NUMA策略。八卡可用不表示八卡独占，不向其他账户进程发信号。显存门槛仍是准入启发式，不是整个推理上下文不会OOM的保证；数值失败和已分配后的资源失败不自动重试。

资源登记有独立ID，后续launch、退出与冷恢复使用该ID。历史训练profile引用保持原值，Full／29和Full／47不会被改绑为新训练版本。原调度字节码通过固定依赖绑定使用八卡清单；不原地修改六卡脚本、旧注册记录或冻结工作树。

## 独立恢复队列与阶段顺序

新权威记录位于原V18目录下的 `evaluation_continuation_01/`，包括资源策略、兼容性证明、恢复登记、评测登记引用、控制器启动信息、独立queue、attempt和失败记录。旧 `six_gpu_queue_01/` 的失败日志和记录只读保留。

恢复控制器同时持有旧六卡队列锁和新队列锁，避免另一条旧恢复命令同时派发。训练队列仅核对十五个完成结果后跳过；任何训练launch、任意脚本或白名单之外的动作均硬拒绝。

后续仍沿用原阶段屏障：

1. 十五个终点固定并完成登记。
2. 十五模型分别生成完整883题dev，再按原规则评分与比较。
3. 三个seed执行预先登记的机制构建。
4. 原5400会话机制评价，再评分和汇总。

既有机制登记继续使用原launcher和实际V18 runtime，不能在已有Student结果后重新选择实现。恢复前实际核对了其所需33个保存点／outer输入文件均存在；不改实验分母、生成配置、工具、评分器或最终候选选择规则。

冷恢复必须使用本次冻结入口和同一新root的 `resume` 动作，继续识别原PID及birth、保留尝试和真实退出记录。若发生部分生成／机制失败，保存并停检，不把失败自动转为重新采样或新机制seed。控制器退出信号只停止新派发并等待其已有子进程，不向Student或其他进程转发信号。

## 必要验证

十项纯源码证明测试、三十六项恢复控制CPU／mock测试均通过，共46项；Ruff通过。覆盖唯一哈希对和节点范围、其他公共合同拒绝、十五结果完整性、禁止重训、八卡上限、GPU5／7亲和性、新旧profile边界、冷恢复ID和原始Python文件绑定接口。

真实CPU预检确认原冻结运行时可加载、十五个训练结果完整、原机制登记及33个必要文件存在；GPU拓扑与新八卡映射一致。此时 `final_evaluation` 尚未创建。上述检查不等于GPU推理已经启动或评测已经通过。

## 实际恢复记录

修复代码冻结于提交 `86f1a246cf800a8380f00bfa5487bf4cd5d83c62`。仅将两个外置控制脚本的已提交字节保存到新root的 `implementation/`，并登记各自SHA；没有复制或修改整个旧科学工作树。解释器仍为项目 `.venv/bin/python`，工作目录和 `PYTHONPATH`仍指向原V18冻结目录。

保留原 `OMP_NUM_THREADS=4`、`MKL_NUM_THREADS=4` 和 `TOKENIZERS_PARALLELISM=false`，控制器清除继承的 `CUDA_VISIBLE_DEVICES`，由原worker按指定GPU映射。新增 `PYTHONDONTWRITEBYTECODE=1` 只禁止写入源码目录下的字节码缓存，不改模型计算或生成配置。

北京时间14:54启动持久控制器，PID为2430833、birth标识为352127516。原十五终点正式核验及评测登记随后通过，14:57开始派发GPU任务。新评测计划保持十五模型、每模型883题、总13,245会话，记录 `Base_rerun=False`、`API_calls=0` 和实际V18 runtime。

15:02:51的不可变观察确认：状态为 `V22_DEV_EVALUATION_RUNNING`，八个worker的PID与birth均存活，实际GPU UUID与各自指派一致，每个worker都已分配模型显存并产生完整episode文件；共观察到150个已生成会话，七个模型尚在队列，`failures=[]`。

| 首批模型 | GPU | 观察时已生成会话 |
| --- | ---: | ---: |
| Static seed11 | 4 | 21 |
| Manual+ seed11 | 1 | 19 |
| Manual− seed11 | 0 | 20 |
| C-only seed11 | 3 | 18 |
| Full seed11 | 2 | 21 |
| Static seed29 | 6 | 16 |
| Manual+ seed29 | 7 | 18 |
| Manual− seed29 | 5 | 17 |

这是生成进度，不是准确率或已完成整模型评测数量；原完整883题生成后再评分的规则不变。实际记录仅支持恢复和八卡工作已开始，不构成整轮成功、固定加速比例或后续无OOM的保证。

| 不可变记录 | ID |
| --- | --- |
| 冻结控制实现 | `ded181b441dd68a3057ce46d495886be6fd8f0824c608dab4088818cffcab661` |
| 恢复设置 | `1cdf5a78b21585567066bd4f2d908f101cd572b36de5327c5b3184df1cc4da34` |
| 控制器启动 | `60561c9df6e64ea57d4009b9d719ba76d8dbb5f8f6b600ef83fce666cd731d57` |
| 八卡资源策略 | `85c86064aa274f2bf065326911d47558150dee515c7c4cf77608fc2ef88cc790` |
| 精确源码兼容证明 | `03ebb91819993862178f17ef08c7322a3069463d544d6ae89885a253994836c5` |
| 后继恢复登记 | `7019c355912e2d13f8d178894668b022e847eadefecccad6a9f256527934360f` |
| 十五终点评测登记 | `af67256cf6484c67321513e6b3ad4f5c7327f5ba38db85ff4069cc76de0729e3` |
| 八卡实际生成观察 | `dbb1358869c26b6c37b986fd57a941be6c16b5fda9afb2af0248c18677fadf53` |

当前权威状态文件是 `evaluation_continuation_01/queue/status.json`。完整首次启动和冷恢复命令、双锁、环境、解释器与实现绑定保存在 `controller_restore_settings/record.json`；不要再用旧六卡控制器继续派发。

本次提交保留必要的登记、启动、worker launch和定点观察证据，不提交实时status、模型Tensor、生成大日志或测试模拟产物。旧Base、旧失败及训练历史均未覆盖。
