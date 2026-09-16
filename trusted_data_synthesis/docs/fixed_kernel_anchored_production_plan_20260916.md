# anchored生产闭环：本次审计后的执行协议

依据438行新审计，SHA256 `065ead447c38ddd67537c800287957274978694e80a70204ce51a486f89b2920`。
附件另链长报告/ZIP未作为已取得或运行证据。保留旧收口/Static绑定/R2限定结论；
不重扫旧会话、不复跑旧8项或157项控制、不增加金融效果pilot或Teacher/Probe。

## 一次同token资源分项与最小保存优化

只用既有26+2、12219+8两个输入/输出，重建相同诊断梯度和虚拟参数。两种保存方式
在独立新进程计量，避免前一进程锁页分配器缓存污染优化RSS。只在首阶段确实测到
重复冻结权重保存后，启用已绑定且生命周期/version/storage/dtype/view范围均正确
的冻结参数引用保留；回取核对版本。激活不去重，不截断KV导数。

记录逻辑保存字节、不同底层存储生命周期字节、实际CPU分配/live/释放、锁页保存
张量、VmRSS/VmHWM/VmLck/VmPin、CUDA allocated/reserved。分类为绑定冻结参数及
view、实际SDPA K/V及view、其余prefill/decode激活；不是仅按形状猜语义。
原logP容差1e-6/1e-5不变；原保存模式完整梯度摘要须匹配R2，优化模式与其完整
梯度按atol1e-6/rtol1e-5对照，失败不松阈值。零新采样、零金融会话。

单个梯度worker，至少60GiB当前剩余显存和512GiB当前可用主存。不要求利用率
归零，不干预其他用户。CPU锁页保存量与操作系统VmLck分别报告，不混称同一量。

## 生产接线与边界

完整360条生成封存后独立评分，再按响应流式累加完整logP导数，固定分母360。
合法Q=0可省反传，但缺失/回放/资源失败不是零分；Q=1轨迹的错误响应、失败工具
和恢复token全部计入。单响应分段必须传回KV边界伴随梯度及prefill导数，不通过
切train模式凑缓存checkpoint。不缩短2048输出、不裁历史、不detach KV通过门控。

除既有反例外，必要准入覆盖22528prompt+2048固定合成output、完整/分段梯度对照、
跨响应释放和非空Adam接线；压力token不是金融采样。分段实现冻结后再执行。
首个正式运行直接为已登记Full seed11，配对原初始化+空Adam，不从Static最终点
加训。epoch0/5计算实际全类G、360反馈、gJ、Adam pullback、居中C和pi；epoch5
实际step=200；epoch10/400步唯一最终检查点和180greedy。全零保持pi继续，不补样。
1681/1645仅是当前Mapper的有限任务内状态数，不是穷尽理论商空间。

## 预算与科学判定

Static三次训练及540会话复用；新增六训练、4320随机反馈、1080最终greedy，共
5400会话、172800次generate上限。SFT序列token1,076,537,940、监督59,516,640，
另十二遍全类梯度215,307,588序列token；回放和重算资源另列。均是预算非已消费。
B/确认仍0。Full是唯一主候选，C-only不得顶替；二者均含prior KL。Novelty若无
激活不能判无效，也不补第三轮。dev参与元优化后不再称未参与学习的泛化检验。

已核对官方[自动微分](https://docs.pytorch.org/docs/2.7/autograd.html)、
[checkpoint](https://docs.pytorch.org/docs/2.7/checkpoint.html)及
[数值组织](https://docs.pytorch.org/docs/2.7/notes/numerical_accuracy.html)语义；
本地PyTorch/Transformers源码为具体实现依据，资源与梯度以实际运行证据为准。
