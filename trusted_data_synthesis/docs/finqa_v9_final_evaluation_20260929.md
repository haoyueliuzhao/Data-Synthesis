# 条件性五臂真实终点→完整dev883→配对统计

## 范围与当前状态

新增 `finance_research.v9_final_evaluation`，承接既有训练launcher的真实最终保存点，复用V7公共合同、LocalTorchProvider、原storage封存和原生FinQA评分。不修改训练总体、审阅规则、训练核或提示；不创建另一套金融框架。

本次交付是可运行入口与CPU/mock接口控制。没有由本模块运行生产Qwen/CUDA、任何dev会话、API、Base重测或实际效果统计，不能把编排接通写成训练/效用已验证。付费生产审阅使用另一冻结执行树，不依赖本模块等待GPU或材料。

旧training launcher保持不变；评价是显式的后继入口，避免把未来运行误标为当前已自动完成。

## 1. 固定完整矩阵，而非最佳保存点

登记必须同时取得11、29、47三个种子的五个真实终点，共15个模型。条件固定为Static、Manual+、Manual−、C-only、Full，唯一训练步数为实际冻结N对应的10s，s=ceil(N/5)。

每个点严格检查：

- 同一已登记训练协议、pool_id、实际X*和任务日程；
- 真实seed结果声明完整五臂，并绑定其实际保存点；
- 路径位于对应seed/arm的 `step{10s}_step`，不接受3s/5s机制点或outer/branch阶段；
- checkpoint字节SHA、完整tensor/state摘要、seed、arm、step、phase均一致；
- 实际Adam/RNG/pi所在的原保存状态、动态execution_plan和日程身份保留；
- C-only/Full已完成四次外更新，其他臂没有被伪装成自动臂；
- 实际最终LoRA参数为有限FP32，登记参数摘要、原Base摘要和buffers摘要。

任一终点未完成、缺失、错臂/种子/步数/阶段或字节变化，均不能把其余成功前缀登记为完整矩阵。全部15个终点先固定，随后才进行任何终点dev生成，不进行最佳seed/检查点选择。

## 2. 装载的是实际最终参数

执行复用原 `load_student` 装载本地原始Qwen和仓库自定义q/v LowRankLinear壳，不读取旧Static或其他实验adapter文件。随后：

1. 校验实际架构与保存的adapter_binding；
2. 校验真实装载的冻结Base张量摘要；
3. 完整匹配最终parameters与buffers的键、形状、dtype；
4. 逐项安装实际最终张量，再检查安装后的字节摘要；
5. 全模型冻结并切换eval，关闭gradient checkpointing、启用推理cache；
6. 使用最终参数摘要、buffer/state绑定、seed/arm坐标、tokenizer与模板构成精确本地点身份，交给原LocalTorchProvider。

这里的fresh壳只是机械装载载体，不是重新fresh训练。推理采用原评价seed20260928和greedy合同，不恢复训练采样RNG来改变评价合同。

`install_checkpoint_state(model,state,scope)`也可被已独立验证坐标的机制评价调用。它只负责精确装载，调用者仍须验证相应机制点；本模块的正式终点登记仍仅接受10s。

## 3. 完整883题与Base可比性

评价固定原官方FinQA dev883。训练X*变小不改变此评价分母，也不按是否训练过某题删除dev题。

公共合同与既有Base逐项比较：

- 原snapshot、role plan、全部883任务及其公共输入hash；
- V7公共system、tools、native tool-call模板及提交profile；
- 原模型和tokenizer资产，chat template、EOS与tokenizer身份；
- temperature=0、top_p=1、top_k=0、max_steps=32、max_new_tokens=2048、context_limit=24576；
- 公共执行、provider、评分及封存关键源文件与pinned scorer文件身份。

源码增加编排模块不被误判为公共合同改变；影响实际执行/评分的关键文件若变化，则拒绝无声沿用Base。

Base只读取原冻结报告的聚合指标和身份，不重跑、不使用逐题错误来设计提示或调整准入。若Base未完整封存/评分或合同不再相同，停止，而不是硬编码33/883、填零或重测后假装原对照不变。

## 4. 每模型先完整封存，再私参评分

每个模型登记一个完整883任务的既有storage run。实际生成不加载private reference；保留公开推理、工具调用、完整事件、真实模型调用计数及原终态。

原883会话全部完成、provider调用状态已结算、任务顺序/身份/配置/公共输入全部吻合后，才写该模型的whole-dev seal，并打开原private reference文件进行原生评分。

任何883前缀、不完整会话、未知/基础设施执行状态或未封存run都不能评分。原生评分明确未知时保留None；不转换为错误0，也不以已知项平均数冒充完整dev均值。格式/程序无效但在原评分合同中明确为0的已完成预测，仍如实保留原生0分，和基础设施unknown区分。

每模型报告保留883逐题记录、execution和program指标、原终态与模型调用计数。native execution改善不等于公开推理可靠性改善，不宣称轨迹CompletePass。

## 5. 恢复与设备

只在真实终点及公共run检查通过后查询登记范围内GPU。可使用有其他进程但余量满足原设备门的GPU，不占位等材料、不杀其他进程；显存门是尝试门，不是假装CUDA已验收。

已有执行attempt必须显式 `resume-model` 或 `resume-seed`。复用已完成的原会话；若存在开始事件但没有完整会话，原inspect检查先阻断，不能悄悄重新采样。完整封存的模型只进行离线评分，不重新加载GPU或生成。GPU/本地执行异常保留attempt/事件并停止，无自动重试或换结果。

每个模型有独立锁，同一评价输出的GPU锁防止多个worker互相抢同一卡。三个seed可各用一个worker并行；每个worker按固定五臂顺序执行。已有训练必须先形成全部15个真实终点，当前入口不会通过边训边看dev选择候选。

## 6. 预登记配对统计

主效用固定为完整dev883的execution：

\[
\Delta_{Full}=\frac13\sum_s\frac1{883}\sum_i
\bigl(Q_{s,Full,i}-Q_{s,Static,i}\bigr).
\]

固定次比较为Full−C-only、Manual+−Static、Manual−−Static。program准确率使用同一配对方式作为另列的原生诊断。Static−Base单列为普通学习效应，不能归为VTDO增量。

汇总严格要求15份真实终点报告、每份883相同题目及全部已知原生指标，且报告绑定各自完整generation seal。少模型、少题、错配顺序、任何unknown都不能进入最终配对统计；不做complete-case删除或成功前缀汇总。

结果明确区分：

- 每seed对同一883题的配对差、win/loss/tie；
- 三个seed差值的平均、范围及描述性标准差；
- 每道原题在三个seed中的平均配对差，distinct question数仍为883；
- 原lineage.source_group的题数及组内描述性配对差，保留来源簇结构。

三个训练seed不是2649道独立题；883题本身也不能无视来源簇而一律视为独立观测。主估计仍按完整题目分母加权，来源簇摘要不偷偷改成等权簇主估计。

本入口不自动生成置信区间或p值，不根据三个seed的描述性范围宣称显著性、统计功效或普遍有效。报告须区分实际效用差、条件性训练支持域及推理可靠性。

## 7. CLI：真实终点出现后再执行

运行环境使用仓库venv和 `PYTHONPATH=trusted_data_synthesis/src`。以下均为未来真实材料/训练完成后的命令示意，不是当前运行事实。

登记全部15个真实终点、公共评价合同与统计口径：

```bash
python -m trusted_synthesis.finance_research.v9_final_evaluation register \
  --training-root /absolute/path/five_arm_training \
  --output /absolute/path/final_dev883
```

每个seed一个worker，固定顺序执行五个模型的完整dev生成及封存后评分：

```bash
python -m trusted_synthesis.finance_research.v9_final_evaluation run-seed \
  --output /absolute/path/final_dev883 --seed 11 --gpu 5
```

29、47可在其他登记GPU运行，也可按次序复用同一卡。单模型入口：

```bash
python -m trusted_synthesis.finance_research.v9_final_evaluation run-model \
  --output /absolute/path/final_dev883 --seed 11 --arm Full --gpu 5
```

已有attempt使用 `resume-model` 或 `resume-seed`。仅对已经完整封存的会话离线评分：

```bash
python -m trusted_synthesis.finance_research.v9_final_evaluation score-model \
  --output /absolute/path/final_dev883 --seed 11 --arm Full
```

全部15份报告完整且无unknown后：

```bash
python -m trusted_synthesis.finance_research.v9_final_evaluation aggregate \
  --output /absolute/path/final_dev883
```

生成 `paired_summary/record.json`，含各报告与原Base报告的hash引用。此入口不运行后续test1147，不将机制calibration5400与dev13245合并，也不宣称Experiment0–5全部完成。

## 8. 本次有限验证

CPU/mock覆盖：真实CPU checkpoint读写及字节/内容绑定；错seed/arm/step/phase拒绝；实际小张量和buffers安装后冻结；全部883封存前禁止私参读取；unknown保留；缺模型/缺题禁止配对；883重复题/三seed/来源簇层级；原loader最终点绑定；已封存不调用GPU；未封存执行加载→生成→评分顺序及显式恢复要求。

另只读比较了实际原dev公共合同与既有Base合同，不读取Base逐题错误、不加载模型、不启动GPU。以上不是生产CUDA验收或效果结果。
