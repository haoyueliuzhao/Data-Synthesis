# 分层 Loss 独立分支：实现、固定 π 控制与正式实验阻塞

## 1. 结论与隔离

本轮实现审计建议的 `HierarchicalTrajectoryLoss` 及其原包、类梯度和诊断接口。
当前证据属于实现与合成 CPU 控制，**不是已完成的真实金融 VTDO 效用实验**。
正式对照的两个前提仍不成立：原共同材料不足，父分支真实 Qwen 反馈适配尚未验证。

- 新分支：`codex/anchored-vtdo-hierarchical-loss`。
- 父提交：`bab60b79fdcec2742ee5d88b729c1b50ae3d17a6`。
- 新包：`finance_qa_vnext_hierarchical_loss`；不修改原 anchored 包。
- 审计附件 SHA-256：`4d013d4d443f4d4bb2b4d81b2f903699383707a66890d1dc817cc0241222bad5`。
- 工作树：`/tmp/data-synthesis-hierarchical-loss-yvab69o2`。

main 和 `codex/anchored-vtdo-20260913` 均不合并、不修改。
本轮仅读取 main 的训练材料准入元数据，没有读取 Student 开发/确认成绩或据此调参。
也没有新 Teacher 请求、题面改写请求、GPU 或真实 Qwen 调用。

## 2. 真实材料前提不能被换 Loss 绕过

原已封存材料的实际结果是 `STOP_INSUFFICIENT_COMMON_AB_MATERIALS`，
`population_selection.status=INPUT_INADEQUATE`，选定训练包列表为空。
共同合格任务数为：

| 类别 | 原共同 A/B 合格任务数 |
| --- | ---: |
| annual_flow_components | 0 |
| stock_rollforward | 0 |
| defined_metric_reconstruction | 0 |
| control | 43 |

材料记录：
`fixed_AB_material_manifest:307dc06e72fbfc8ae6ef5c4792697a213bfdca24b48b4178ff9e99a6ba115981`；
原文件 SHA-256：`69d31c12accbd8dcfb6d8fa4c5ea0b5e5608fd487497b2bef293f64863febe3d`。
这不是 GPU 忙导致的延后，而是当前没有达到原 N≥180 门槛的共同训练总体。

进一步仅读同一材料清单的 `common_AB_readiness[].counts_by_pool_actual_method`，
可定位直接计数瓶颈：三个 dual 组共 155 个任务，A/B 两池的 movement 包计数逐项均为 0。

| 组／任务数 | endpoint 在 A/B 均≥10的任务数 | movement 在 A/B 的包总数 |
| --- | ---: | --- |
| annual_flow_components／54 | 34 | 0／0 |
| defined_metric_reconstruction／48 | 6 | 0／0 |
| stock_rollforward／53 | 31 | 0／0 |

控制组共100任务，双池均≥10的交集为43。即便 endpoint 已达标，没有 movement 仍不能
满足原双方法共同核。该表**不能解释 movement 为何消失**：生成、方法分类、金融资格
和表征过滤等环节尚未区分；本轮没有读取原轨迹来猜测原因，也没有为此重采集。

新 `material-preflight` 只读固定的 `manifest.json` 和 `material_manifest.json`，
检查内容身份、成员 SHA/大小以及读取前后字节一致。它没有扫描全部原件，
也不将元数据 READY 当作新实验准入。没有把未选包拼成新总体、删除难例或放宽门槛。
正式 `study run` 仍硬拒绝；合成控制成功也不能打开此门。

## 3. 对审计公式的必要澄清

### 3.1 保留真正的 Full 基线

已有基线是在一个原包的全部既有监督 Token 上求平均 NLL：

`ell_full(P) = sum_original_target_NLL(P) / L(P)`。

而三个分层均值再以 `(1,1,1)` 相加是另一个目标，通常不等于此基线。
新 Full 分支直接委托父类梯度与父 64 包消费者，没有替换其实际计算。
这里“Full”指既有 SFT 监督范围，不等于全部随机生成 Token 的轨迹概率；
原 SFT 的 prompt、工具观察和 EOS/suffix 遮罩仍保持不变。

### 3.2 不重排交错轨迹

reasoning、工具调用、观察与最终交付在实际历史中可能交错。
分层只是给**原始位置**的监督 Token 加不同系数，不能拼接成所有 reasoning 在前、
所有 tool 在后。模型仍条件于原完整历史，只选取目标 Token 的因果前驱 logits，
没有二次 shift、截短历史或加入 `<think>` 等新标记。

### 3.3 按包分层，再保持原类内核

对原包 P 的层 k，`L_k(P)` 是该包全部原行中属于该层的目标 Token 数。

`ell_hier(P) = sum_k lambda_k * sum_NLL_k(P) / L_k(P)`。

一个状态的损失是原包的均匀均值，不是把不同长度包的 Token 拼成新的类均值：

`L(x,z) = (1/n(x,z)) * sum_P ell(P)`。

五任务更新中每个层目标 Token 的有效系数为：

`pi(z|x)/(5*n(x,z)) * lambda_k/L_k(P)`。

π 只出现一次，不再额外除原整包长度，也不会在按 π 抽样后又乘一次 π。
本实现枚举全部原包；不能将带重复制权的期望式当作同一目标。

| 项目 | Full | Hierarchical |
| --- | --- | --- |
| 包内目标 | 原监督 Token 总均值 | 固定权重的包内分层均值 |
| 类内核 | 原包均匀均值 | 相同 |
| 任务/状态权重 | 原 μ、固定 π | 相同，只用一次 |
| 原字节、Token、时间顺序 | 保留 | 保留 |
| 64 包更新 | 一次 zero/clip/step | 相同 |
| 随机反馈 logP | 父定义不变 | 不用 HierLoss 替代 logP |

## 4. 边界来源与缺失 Reasoning

侧车支持两个明确的既有公共格式：

1. 当前原包的 `eval_readiness.v2.original_Teacher_response`；
   用原严格 JSON 解析器复核工具响应或 Final。
2. 旧公开候选的 action/update/final 协议；
   action 和结构化观察处理 update 归 tools，final 整响应归 final。

Final 内的数值、引用和解释仍全部属于 final。不会凭“看起来像思考”猜 Reasoning，
也不从私有 `reasoning_content` 提取文本。当前公共协议没有独立 Reasoning 层。

因此提供两种**事前输入可用性模式**，不是看结果挑选的超参数：

| 公共模式 | reasoning | tools | final | 权重和 |
| --- | ---: | ---: | ---: | ---: |
| 有明确公共三层的 RTF 控制 | 0.3 | 0.5 | 0.2 | 1 |
| 现有公开 Tool＋Final 特例 | 0 | 0.5 | 0.2 | 0.7 |

TF 不逐包重归一，也不偷偷改成 `(0,5/7,2/7)`。其总监督强度 0.7 是明确设计选择，
不能把后续差异仅归因于“工具权重更高”而忽略归一化和总尺度变化。
生产模式须在模型结果出现前，由实际材料公开结构统一冻结；不能按包或按成功率切换。
任一正权重层缺失即阻断两条件共同准入，不保留仅能跑 Full 的例外子集。

侧车保留候选和编码行身份、原 target SHA、tokenizer binding、层掩码和原时间顺序。
验证时重新解析嵌入的公开候选、重算映射与掩码，保证每个原 target 恰属一层，
context、system/user、工具返回和 suffix 始终不进入层目标。
原行不重写、不重新 tokenize；Token 解码真实性继承原已绑定编码证据，
不能宣称本轮没有加载 tokenizer 却重新完成了原文解码验证。
合成 RTF 另有明确 `CPU_only/synthetic` 权威，不能冒充真实公开候选。

## 5. 与 VTDO 的连接及第一阶段范围

层损失各项都进入新的 `g[x,z]=gradient L(x,z)`。
原 Contribution 形式、Novelty 和双锚公式不修改；但 g 改变后，G、虚拟模型点和 C 的
**实际数值一般会改变**，不能把“形式相同”表述为“Contribution 不受影响”。

为了先隔离 Loss，本阶段固定同一 π，零外层更新、零随机反馈请求。
两条件从同一模型、Adam 状态、seed 和原包顺序开始，唯一终点为第十轮。
CPU 随机数使用专用 Generator，不触及 CUDA RNG；每条件类梯度和训练前均恢复同一状态，
结束后恢复调用方 CPU RNG。优化器 tensor 在序列化前必须有限且位于 CPU。

Full 委托父实现，Hier 使用独立有效系数，保留旧 coefficient 字段仅供原材料断言验证。
整类包数、行 SHA、来源映射、当前 π 和完整 64 包均需通过原断言。
类梯度不改真实参数、buffer、已有 grad 对象或模式；正常只读路径不改变 tensor version。
输入别名、回调篡改、非有限值及参数/梯度/Adam 状态提前变化会在 step 前被拒绝。

数值交叉审查修复了均匀系数快速路径的 FP32 下溢漏洞：现在先检查实际 FP32 可表示性，
再调用原 Full 损失，不能让极小正系数静默产生零 loss/梯度。

## 6. 主指标和诊断不越权

`CompletePass` 保持原完整轨迹资格定义，不用答案正确或泛化 success 字段替代。
现有 `support_status` 只验证最终引用的支持链，quantity 检查又依赖支持成功。
因此不能简单改名为独立工具规划成功率和独立最终交付成功率。

本轮保留两个具名代理：`observed_support_chain`、`support_conditioned_final_quantity`。
独立 `tool_success/final_success` 缺权威时为 UNKNOWN；无 Final 可明确记最终交付 FAIL。
新增独立判据的预登记/绑定接口，但真实独立评价器尚未验证，生产门不开放。

所有注册任务保留固定分母，重复、缺失和错 TaskID/pool/seed/surface/材料/π 配对均拒绝。
UNKNOWN 的零 credit 不冒充观察失败；汇总分别给 PASS/FAIL/UNKNOWN、覆盖率和部分识别界限。
配对界限不是置信区间，诊断代理的变化也不是金融效用或因果证明。

## 7. 控制证据与复现

新模块独立控制：分层映射 48、损失 34、原包/类梯度接线 52、诊断 56、固定 π 配对及门禁 21。
父分支 157 项控制另作回归，不当作新增独立测试。
最终 **211 项新增控制＋157 项父回归＝368 项通过**，失败/错误/跳过均为 0；
JUnit 用时 **133.966 秒**（控制台四舍五入为 133.97 秒），Ruff 全通过。
该轮开始时间为 2026-09-13 13:16:58.999153 Asia/Shanghai。

完整配对控制使用五个合成任务、64 个原包、每包四个合成 Token 行；
每条件做十个五任务更新。RTF 和 TF 是两种标注输入域的数值控制，各自只比较 Full/Hier，
不是四个真实金融训练臂，更没有按结果从两种 profile 中选优。
当前保存控制 seed 为 11；spec 中的 11/29/47 是后续方案种子，不冒称三种子正式实验已完成。
小型模型只有 35 个训练参数；CPU 控制 AdamW 的 lr=0.002、eps=0.03、weight_decay=0.02，
用于检验不同梯度确实被实际更新消费，不冒称已使用真实 Qwen 训练配置。
不同目标的训练 loss 数值不能直接比较为效用高低。

继承的五任务 fixture 中，同一包内四行的 logits/labels 恰好相同，
所以 RTF 三个层均值相同，权重和为 1 时与 Full 在实数算术下等价。
两条件终态约 `1e-7` 的差异只能解释为 FP32 舍入；测试将其作为等价性控制，
不再用“bitwise 不相等”当作实质效果依据。TF 在这个 fixture 中主要隔离权重和 0.7
产生的总尺度差异，也不代表工具或最终能力改善。

另外保留两个不等层长、不同层目标的包，独立验证分层类梯度无法用 Full 类梯度的
单一标量缩放表示，并保存梯度及投影残差。这是非退化计算控制，仍不是金融效用结果。
最初 366 项成功控制的草稿留在本地原目录；最终证据另存
`artifacts/qa_vnext_hierarchical_loss/implementation_checks_20260913_final`，
草稿和最终复跑不相加为更多独立测试。

最终 RTF/TF 配对各有 20 个实际 Adam 步骤，总计 40 步；每步完整消费 64 个原包、
256 行，包含 512 个监督 Token 和 1,024 个序列 Token，zero/clip/step 各一次。
这代表重复训练消费，不是新增 2,560 个独立材料包或独立科学任务。
两条件的初始模型、Adam、固定 π、seed、CPU RNG 和十轮原行顺序均一致。

| 非退化类梯度控制 | 最佳全局缩放系数 | 去除缩放后的梯度残差范数 |
| --- | ---: | ---: |
| RTF | 0.9938458887 | 0.1704784982 |
| TF | 0.6845543390 | 0.0210708496 |

这些残差只验证不同层目标能改变梯度方向，不是金融指标，也不能跨模式排名。
最终配对记录分别为：

- `fixed_pi_CPU_pair:1e75b94ff0d61df5c621eb64cafaf9db44cdfc957f8c405e53e792cd186b8306`。
- `fixed_pi_CPU_pair:fcfbd73212ea58931a03d45c20577cfe24c8401ad0ff8771fb6603e8b9cb9f73`。

源码与产物绑定记录为
`isolation_and_source_bindings:49c935d7958b4052b5e58b4536b58ae8e7090f9307cd956d3f53c7ff3c90ec92`。
它核对本工作树中父提交的 src/tests/config/finraw 范围共 1,849 个既有文件，
Git 原 blob 全部一致，并保存 12 个新源码/测试文件和执行证据的 SHA。
main 保持 `30284a2f139b7981bc96413646459c51b76e57d5`，父 anchored 保持 `bab60b79...`，
两个工作树仍干净。该记录如实说明绑定的是本次工作树源码 SHA，
不冒称控制执行前已有一个尚未产生的最终 Git 提交。

复现最终控制（CPU证据目录应尚不存在）：

```bash
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 \
PYTHONPATH=raw_financial_data_lake:trusted_data_synthesis/src \
HIERARCHICAL_CPU_EVIDENCE_DIRECTORY="$PWD/trusted_data_synthesis/artifacts/qa_vnext_hierarchical_loss/implementation_checks_20260913_final/cpu_pairs" \
/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/.venv/bin/python -m pytest -q \
trusted_data_synthesis/tests/test_qa_vnext_hierarchical_*.py \
trusted_data_synthesis/tests/test_qa_vnext_anchored_*.py \
--junitxml=trusted_data_synthesis/artifacts/qa_vnext_hierarchical_loss/implementation_checks_20260913_final/junit.xml
```

仅查看计划：`python -m trusted_synthesis.experiments.finance_qa_vnext_hierarchical_loss.study spec`。
`material-preflight --live-root ...` 只读材料元数据；输出只能写到当前新分支的专属 artifacts，
拒绝 `..`、符号链接、其他 cwd 和其他分支。`run` 明确拒绝正式执行。

## 8. 后续应先处理什么

1. 单独追查 movement 在生成、分类、资格或表征哪一环节未形成可用包；
   不能在此 Loss 比较中悄悄补样、删样或换门槛。
2. 完成父 anchored 的真实 Qwen 反馈/虚拟点/优化器接线验证，保持真实 logP 定义。
3. 在新的材料/状态目录/固定 π 可验证后，事前冻结公开层模式、两条件、资源与评测协议。
4. 真实运行后再报告 CompletePass 及有独立权威的诊断，不根据本轮 CPU 数值宣称收益。

本轮没有授权旧确认成绩参与新 Loss 权重、判据或候选选择。
