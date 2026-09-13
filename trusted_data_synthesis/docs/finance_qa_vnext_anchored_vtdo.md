# 独立锚定VTDO分支：实现、CPU证据与生产边界

## 1. 范围与分支隔离

本轮依据用户2026-09-13审计建立独立算法分支，不改名现有三臂选择器。
审计附件SHA-256为`a3cd378ed11fc646be48fca14d524f8fadd932931f5c44c9ede120ffddbeddbe`。
附件中指向的参考ZIP/完整Markdown没有随本条消息提供；本实现依据已贴出的完整公式与规范，
没有声称取得或运行审计方的41项控制，也没有把它们计入本项目测试。

分支：`codex/anchored-vtdo-20260913`。基点：
`fcb0607b81709479285e30f4e42a8e9f53094647`。独立稀疏工作树：
`/tmp/data-synthesis-anchored-vtdo-MaNMFd`。新包：`finance_qa_vnext_anchored_vtdo`。
只取源码、测试、文档与配置，不复制主分支的活跃账本、采集目录或训练产物。
本轮只提交并推送该分支，不合并到main，不改变原8并发采集或三臂follow。

开发起点实际记录于2026-09-13 01:33:12 UTC：
`branch_start:bd5f37cf7d05cbc00c46c593be20ad46824739840a6c71ab5cc76063979ad6ae`。
记录对main的1,850个既有源码/测试文件建立摘要，仅检查预先指定的原Student目录是否存在，
未读取原Student成绩、逐题结果、检查点或活跃账本。该时点preparation/training/确认目录均不存在。
这个文件系统观察不证明服务器历史上绝对未计算过；Git未发布也不是确认独立性的证据。

新开发读取器拒绝旧Student输出及任何confirm反馈输入，即使误加到allowlist也拒绝。
这是本实现的数据访问边界，不是任意恶意Python代码的形式化沙箱。若之后开发利用旧确认成绩，
这720题对新算法必须改作已知验证材料，并重新登记确认；不得靠保留本文件继续声称独立确认。

用户随后另行授权并行检查main采集、推进原后续训练。该运维任务与本算法分支分开，
仅共享主线状态/产物身份/阻塞信息，不向本算法开发传入确认成绩或臂优劣。

## 2. 当前真实完成状态

已实现并以CPU控制连接：原样状态材料、模型类梯度、真实Torch Adam状态、虚拟一步、
专用随机探针的全轨迹概率梯度、中心化Contribution、Novelty、正值势、双锚分布更新、
新64包消费者及epoch 0/5两次外层控制。

仍必须区分：

| 对象 | 本分支证据 |
| --- | --- |
| 核心数值/原包接口/两轮CPU接线 | 有实际代码与独立控制，不是三臂argmax改名 |
| 真实Qwen随机反馈worker/GPU整合 | `PRODUCTION_ADAPTER_NOT_VALIDATED`，未执行 |
| 新金融VTDO RoundArtifact | 尚无；保存的是明确标记CPU合成控制的RoundArtifact |
| 实际效用/因果授权/独立确认 | 未测量，不能由数值测试替代 |
| 新16,740会话预算 | 条件性建议，未自动继承原研究授权 |

`study run`和生产反馈入口硬拒绝启动。当前分支的CPU材料/反馈记录不能通过改一个actual布尔值
变成Qwen实际运行记录。正式数据工件和新预算/生产接线门成立后，需要另行批准执行。

## 3. 语义状态与固定材料核

`state_catalog.py`新增带标签有限DAG的精确同构比较。执行ID只作引用键；来源、实际期间、
运算输入角色、数据依赖、可见性、修订、核验、声明与Final支持链必须保留。
相同答案不会让endpoint与movement归为同一状态。循环直接拒绝；搜索超出固定限额时保持未定，
不以近似hash替代证明。

实际runtime投影只覆盖明确可重放的结构化工具/Final子域，计算依赖取自AST与已存在结果引用。
真实执行中所有已经观测的工具输出都保留可见性依赖，不将“没有显式引用”推断为“不影响选择”。
因此抽象DAG中已经证明无边的独立节点可交换，不等于所有真实顺序都可删除。
自由文本或未支持的语义声明保持`PENDING_REVIEW`。

目录保存原session、旧signature/fine ID、新mapper版本、新状态、原始证据与归并理由。
旧签名、旧资格、原包顺序、原始Token行均不覆盖。未来`build_from_parents`只接受完整已封存
原采集/材料父，核对全部8+2原件及其成员SHA；本轮没有对主线真实材料调用此入口。

任一训练包映射未定，新目录的训练门关闭，不能删包恢复READY。
heldout原件始终保留并校验；其映射未定单列，不进入训练状态数，也不伪造为训练包。
heldout原件缺失或字节损坏同样拒绝，不能用“未训练”忽略证据完整性。

对每个池/任务/状态，类内核为原训练包均匀分布，状态计数为n。
双依据初始`pi0(z|x)=n/16`，控制`pi0=n/8`；覆盖先验固定`r=pi0`。
由此每个原包的初始质量恰好恢复alpha0。A/B各有自己的支持，不把A的权重转给B不存在的状态。
该先验是保留初始有效覆盖的设计，不是Teacher自然生成概率或未知最优分布。

## 4. 当前模型相关的Contribution代理

`gradients.class_gradients`从真实Torch当前参数计算类内原包平均NLL梯度：

`g[x,z] = mean_package(gradient(sum_target_NLL / whole_package_target_tokens))`。

它读取完整原历史，只在正确的因果前驱位置取logits；不把该NLL当作轨迹概率。
代理计算时关闭dropout，并恢复原模块模式；不更新真实参数、优化器或`.grad`累计。
G仍包含全部任务和控制，`G = sum_x mu(x) sum_z pi(z|x) g[x,z]`。

`optimizer_pullback`绑定实际theta、Adam一阶/二阶矩、step、参数组配置和摘要，
在聚合G处先处理全局clip，再作Adam虚拟一步`theta_bar=theta-U(G)`。
处理偏置修正、eps、weight decay和实际clip的`norm+1e-6`，不能平均逐状态`U(g[x,z])`。
相应算法形式见[PyTorch 2.7 AdamW](https://docs.pytorch.org/docs/2.7/generated/torch.optim.AdamW.html)。

实现的解析VJP与实际Torch FP32/64更新及有限差分对照。clip不可导边界、某些零矩/下溢情况
明确拒绝；可微零矩极限单独验证。同dtype/device的dense FP32/64是当前支持域，
特殊优化器模式不冒充已支持。旧真实下一步是五题mini-batch；此处是全总体聚合虚拟一步，二者不同。

`FunctionalStudent`只提供虚拟trainables与克隆buffer，函数式调用后原参数/buffer必须不变。
该视图要求同一模型单一拥有者执行，不宣称可与另一线程同时操作同一Python模型对象。

在虚拟点取得完整随机反馈梯度gJ后，计算：

`a = DU(G)^T(-gJ)`；
`C[x,z] = mu(x) * dot(a, g[x,z] - sum_z' pi(z'|x)*g[x,z'])`。

逐任务核验`sum_z pi*C=0`。向量—雅可比乘积不需要构造稠密Jacobian，
参考[PyTorch自动微分说明](https://docs.pytorch.org/docs/2.14/autograd.html)；
本机实际测试版本另随实现证据记录，没有升级主环境。

正式名称是“一步随机完整轨迹反馈Contribution代理”。虚拟一步代替多步SFT、
随机探针代替最终greedy效用，是两层明确近似；不能声称精确多步导数或已获因果授权。

## 5. 随机反馈与真实采样概率

每轮固定180个开发任务、三组各60、每题两次，共360探针。随机协议为temperature1、
top_p1、top_k0、无强制EOS；输出2048、上下文24576、32响应/32工具、neutral。
seed由pool、training seed、outer round、TaskID、repeat产生，不含condition，
以便相同参数点的C-only/full使用共同随机数。不会根据结果重抽seed。

采样保存实际prompt IDs、所有生成IDs、每Token logprob、真实EOS以及RNG状态连续性。
概率重放使用同一虚拟参数/buffer摘要和原prompt IDs，不重新tokenize原历史。
错误输出也进入logP，工具输出只是条件输入，不是模型采样目标；不沿用SFT正响应mask，不除轨迹长度。

先收齐并封存全部探针，再调用离线资格器。成功奖励必须对应完整轨迹资格，而非仅答案正确。
score-function估计采用固定`1/360`系数；全部失败、未知、无Final仍在分母。
其原理参考[Sutton等的策略梯度论文](https://proceedings.neurips.cc/paper/1999/hash/464d828b85b0bed98e80ade0a5c43b0f-Abstract.html)。
CPU控制使用明确的合成资格规则，并不冒称真实金融资格。

全零奖励标为`UNINFORMATIVE_FEEDBACK`，不证明理论Contribution为零。
缺失或无法证明完整采样的记录保留失败，但拒绝计算gJ；已知上下文拒绝的零采样可合法保留分母。
原参数和`.grad`不因反馈反传改变；探针永不加入SFT，不直接作真实Student策略梯度更新。
生产Qwen适配仍硬关闭，CPU callback分离不是已完成生产进程隔离验证。

## 6. Novelty、正值势与双锚

同支持上计算`N=max(0,log(r/pi))`，再用审计建议参数：

| 参数 | 事前值 |
| --- | --- |
| epsilon | .05 |
| Contribution指数a | .8 |
| Novelty指数b | .2；C-only仅将b置0，不把a改为1 |
| T_N | 1 |
| lambda_current / lambda_prior | 4 / 1 |
| T_C(x) | mu(x)×max(加权RMS(C/mu),1e-8) |

为落实审计未完全指定的尺度细节，RMS用非control任务的`mu*pi`加权，并除以非control总mu；
controls仍在G中，但不影响RMS或被优化。此为本轮事前工程选择，不依据任何确认成绩。

`C_tilde=epsilon+(1-2epsilon)*sigmoid(C/T_C)`；
`N_tilde=epsilon+(1-2epsilon)*(1-exp(-N/T_N))`；
`logPhi=a*log(C_tilde)+b*log(N_tilde)`。

逐任务新pi为`softmax((4*log(pi)+log(r)+logPhi)/5)`。
输出保留实际浮点值；下溢为零则拒绝，不截概率、不后验重归一。
每轮保存C/N/Phi、新旧pi、固定r、两个KL、TV、熵与最优性残差。
闭式解只对应冻结势函数的双KL目标，不保证真实任务效用单调增加。
小epsilon=.001、a=b=.5导致第二轮方向反转的同类合成反例也保留在测试，不用成功例覆盖它。

## 7. 新权重、两次外层与可核验记录

新消费者`state_materials`的系数是`pi(z|x)/(5*n[x,z]*L_package)`。
初始化精确还原旧`alpha/(40L)`，完整遍历所有物理包，不换类内材料、不改变任务边际。
新断言验证catalog/manifest、原行SHA、真实状态归属、原顺序、n和分母；旧alpha-only kernel保持不变，
不会通过取消旧断言接纳新分布。64包全部反传后裁剪与优化器各调用一次。

控制器在epoch0计算第一轮C/N/Phi/pi1，按pi1训练五遍；epoch5读取更新后的真实Adam状态，
重新计算第二轮，再训练五遍。唯一最终模型是epoch10，不按分数选择中间点。
两次外层与每遍N/5次内层更新分别登记。

每个CPU `RoundArtifact`实际含：材料/mapper ID、原包全集、当前参数和Adam矩/step、
类梯度、G、虚拟theta、360个探针原件/资格、gJ、pullback、中心化C、r/N/Phi/pi及独立工作计量。
原样Tensor值仅用于小型CPU证据；生产大模型分片保存与额外资源预算尚未据此获准。

本轮交叉审查还落实三处加固：同ID改rows/state不得进入类梯度；跨轮prior、mu、control、
材料与配置封存，回调只取得副本且不得原地改pi；静态基线也经过CPU硬门。
历史RoundArtifact与新pi不共享可变对象，每轮重验嵌套身份。
每个内层epoch还核对实际Adam step增长，不只相信callback返回“训练完成”。
另一个交叉反例是验证完成后的事件回调可通过调用方引用改包系数；新消费者入口现会深拷贝
并验证私有快照，后续只消费该快照。回归测试确认外部系数被改写时，实际损失、梯度及更新仍与
原验证输入完全一致，不将旧validation ID错误地附在另一组权重上。

## 8. 新比较与条件性预算

事前主候选固定为full anchored VTDO，不经原plus/minus三点选优产生。
A运行static alpha0、C-only、full，各三种子；B仅static与full，各三种子。
C-only更好也不能改称完整VTDO成功，确认失败不换另一个候选。

B的full在自己的模型、材料和状态支持上重算C，因此会使用180开发任务作反馈。
新分支明确不满足旧“B零开发”；旧三臂follow承诺保持不变。
新独立性来自720确认不参与反馈、超参数或候选选择，不来自把反馈改名。

预算上限：15个训练协议，9个自适应运行×2轮×360＝6,480反馈会话，
加最多10,260最终greedy开发/确认会话，共16,740个本地Student会话。
全数据梯度、虚拟参数/优化器、方向投影、logP反传另计，不藏进十遍SFT Token预算。
基线复用信用当前为0；必须有实际工件与物理配置完整相符证据才能另记复用。

## 9. 使用与结果解释

查看协议不会启动实验：

```bash
PYTHONPATH=raw_financial_data_lake:trusted_data_synthesis/src \
/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/.venv/bin/python -m \
trusted_synthesis.experiments.finance_qa_vnext_anchored_vtdo.study spec
```

`study run`当前必定拒绝，不能拿本轮CPU通过代替新GPU预算与生产验证。
新实验要执行前，还须绑定最终真实共同材料、完成其新状态目录、通过真实Qwen概率重放/
虚拟参数/优化器/原包训练适配验证、独立登记新资源额度，并在不利用旧确认成绩的条件下冻结比较。

本轮控制只使用小型CPU模型、合成原轨迹与临时文件，不读取主线金融材料或确认成绩。
两轮整合示例的训练总体是五个合成任务，每步64包；它不是正式N=180–200训练，
也不是对真实金融任务开展的小型效果试验。
联合测试数、执行耗时与保存的CPU证据由后续本分支实现报告给出，不与旧150项或审计方41项相加。

## 10. 本轮已执行的独立CPU验证

最终联合157项通过，失败/错误/跳过均0，实际耗时84.447秒，Ruff全通过。
这些控制包括：优化器/分布67项、状态目录/原包消费40项、随机反馈13项、
类梯度/隔离21项、两轮整合/边界16项。中间单模块与联合复跑不重复计算成更多独立测试。
测试仅使用本机已有`torch 2.7.1+cu128`的CPU路径，没有安装或升级主环境。

保存于`artifacts/qa_vnext_anchored_vtdo/implementation_checks_20260913`：
`junit.xml`和三个明确标记CPU控制的执行记录。C-only/full各包含两份RoundArtifact，
每轮360个合成探针；static不调用反馈。每个控制运行十个五题64包更新，
实际Adam step在外层边界分别为0和5，不把它说成正式180–200题的360–400次更新。

| 合成控制 | 外层次数 | 边界 | 第一轮最大N | 第二轮最大N |
| --- | ---: | --- | ---: | ---: |
| static alpha0 | 0 | 无 | 不适用 | 不适用 |
| C-only锚定 | 2 | epoch0/5 | 0 | 0.0123060678 |
| 完整C＋N锚定 | 2 | epoch0/5 | 0 | 0.0123060678 |

首轮C-only与full的pi在浮点容差内一致；第二轮各自使用已登记的b=0或b=.2。
完整C＋N第二轮的加权TV为0.0196461452，近端最优性残差为约2.22e-16。
这些数值说明新公式与训练/反馈状态确实连接，不是金融效用增益或因果授权证据。

完整C＋N控制记录为
`CPU_two_round_execution:cd02b7529b13100664be0f0e7733bb0d72d05e2ca203bcccd7af8707912200fd`，
两份RoundArtifact分别为
`RoundArtifact:5a8e4b7622105ab2f3c60b89242d9f81891edf589ab561289cd05b0b5f659838`及
`RoundArtifact:3ec3394e92c55b37def50135d167be75207fb9d49a00ff41548b328280845a67`。
全部控制明确`actual_Qwen_or_financial_utility_run=false`，没有确认成绩被用于本分支设计。

2026-09-13 02:16:44 UTC重新核验开发起点所列main源码/测试，1,850项SHA全部一致。
这核验既有生产文件，不包含用户另外授权的主线后处理运维分支可能新增的独立文件。
