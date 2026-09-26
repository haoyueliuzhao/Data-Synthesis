# 固定视觉模型文件：独立有限获取阶段

## 阶段性质与来源

本实现只获取官方固定内容，不安装依赖、不创建Python运行环境、不导入模型库、不加载模型／GPU、不打开PDF、不渲染页面，也不生成语义或视觉审阅证书。源码与测试须先提交冻结，再由控制端明确执行`register`及`run`；编写代码或执行合成测试不会触发下载。

父计划为已冻结的`provision_cross_market_vision_pilot_20260927.py`，其真实协议为`cross_market_vision_provision_protocol:5cabaaa30c3c0297eb6c1434fc1a145b49ee874ac209798f1ab58caca5519f06`，父阶段commit为`9312da133f`。父计划的下载／安装授权为false且网络请求为0，只描述其离线准备范围。本阶段另立获取协议和网络预算，不修改父协议，不把父0预算解释为已下载权限或已发生数据传输。

唯一模型为官方仓库`OpenGVLab/InternVL3_5-8B-HF`，固定revision `741a7d03020411e666c6109218ab71e08151ef86`。直接复用父`manifest()`的18项文件名、精确字节、URL、角色及哈希，不查询模型列表，不在运行时重查API或自动解析最新版。

18项中4个safetensors权重共17,056,744,056 bytes，其余14项为元数据。元数据包括`tokenizer.json`，该项使用清单给定的SHA-256；其他非LFS元数据使用Git blob SHA-1，并非普通文件SHA-1。校验方式依每项`hash_kind`，不根据文件角色擅自替换算法。不下载任何`.py`；脚本没有`trust_remote_code`、自动模型发现或代码执行路径。

## 明确有限预算

| 项目 | 固定上限／约束 |
|---|---|
| 文件范围 | 父清单原样18项；4权重、14元数据 |
| 初始GET | 每文件最多1次，总计最多18次 |
| 重定向 | 每文件最多4次，因此总物理HTTP预约最多90次 |
| 并发 | 最多2个文件获取线程 |
| 应用层响应流读取 | 每文件最多清单精确字节+1；多读的1字节仅为超长哨兵，不能通过 |
| 权重总量 | 父清单之和且不超过20,000,000,000 bytes |
| 元数据总量 | 父清单之和且不超过32 MiB |
| 磁盘 | 登记和每次控制端运行前至少50,000,000,000可用bytes |
| socket超时 | 每次打开连接／阻塞网络操作最多120秒 |
| 文件时间界限 | 3,600秒deadline，在请求和每次流读取前检查；正在进行的阻塞读取仍受socket超时约束 |
| 自动重试／断点续传 | 均为0；没有Range请求 |
| 模型／GPU／PDF／安装 | 均为0 |

HTTP预约数是保守上界，不保证每个预约都真的到达服务器：进程可能在先记账、后发送之间中断。此类不确定尝试不退预算、不自动重放。初始文件attempt也可能因本地I/O、总HTTP预算或中断而未实际发送，但仍保留已占用记录。

读取上限指应用层消费并持久化的artifact body；它不是底层TCP缓存或网络链路字节计费证明。重定向／错误响应不读取正文。完整响应必须为HTTP 200；206部分响应、不符合声明的Content-Length、非identity Content-Encoding、短流、超长流或哈希不符均不能发布final文件。

## 网络约束

固定direct连接，显式空proxy handler，使用系统默认TLS证书校验；不使用环境代理，不读取`.env`，不提供认证／Cookie／Bearer token。初始URL取自父清单，只有HTTPS、443或默认端口且无userinfo的目标可请求。

重定向仅允许冻结清单中的官方域：`huggingface.co`、`cdn-lfs.huggingface.co`、`cdn-lfs.hf.co`、`cdn-lfs-us-1.hf.co`、`cdn-lfs-eu-1.hf.co`、`cas-bridge.xethub.hf.co`、`us.aws.cdn.hf.co`。这是一份有限执行allowlist，不声称涵盖官方将来可能使用的所有CDN；遇到其他域直接失败，不自动扩展名单或改用镜像。

每个HTTP hop都先落盘预约，再发送唯一一次GET。支持301／302／303／307／308的有限跟随；第5次重定向不会发送后续请求。重定向日志保留目的scheme／host／path及完整URL的hash，但不持久化可能包含短期签名的query。报错只保存类型、HTTP状态及程序内部固定原因；不保存远端错误正文或signed URL细节。

任一文件收到403或429即保留该失败，并设置共享停发标志；未开始文件不再请求，已在途最多2个线程可能完成或按中断状态退出。后续再次执行同阶段时，只要已有403／429记录，仍不会开启剩余新请求。没有换出口、换域、重新签名、改源或重试逻辑；若访问条件需要改变，应明确处理阻断，而不是把本阶段当作循环探测器。

## 保存、恢复与隔离

唯一新输出根为：

`cross_market_calibration_cache_20260926/original_evidence_revision_02/vision_model_acquisition_01/`

最终模型目录为其下`models/741a7d03020411e666c6109218ab71e08151ef86/`。不使用`/tmp`或HOME作为真实模型缓存，不写Student环境，不修改父provision目录。合成测试使用pytest临时目录及字节级假响应，并不调用真实获取。

目录职责如下：

- `protocol.json`：代码commit/hash、父协议完整引用、固定manifest和全部预算；登记后只读复核。
- `attempts/<filename>.json`：每文件唯一attempt，在任何网络发送前不可变保存。
- `HTTP_requests/<filename>/<hop>.json`：每个有限GET／redirect预约。
- `models/<revision>/<filename>.partial`：唯一原始流文件；失败后原样保留，不自动续传、删除或覆盖。
- `models/<revision>/<filename>`：精确字节及清单哈希通过之后，才由同目录原子rename发布；不得覆盖已有final。
- `receipts/<filename>.json`：完整、失败、中断、未知尝试或本地恢复的不可变回执。
- `runs/<content-id>.json`：每次控制端运行的不可变总结；`summary.json`是原子更新的最新总结，旧版本仍保留在`runs/`。

权重校验SHA-256；Git blob SHA-1按`b"blob " + ASCII(字节数) + b"\0" + 原始内容`计算。同时记录最终文件SHA-256用于统一审计。所有计算都流式进行，不需把约4.9GB权重整块载入内存。

已有成功回执的文件必须重新验证本地精确字节及清单hash，再复用该回执；验证失败不能自动重下载或篡改旧成功记录。若进程已经发布完整final但尚未保存receipt，恢复时可对该final进行精确哈希校验并补充“本地完整内容恢复”回执，不再发请求。若本目录已有相同固定内容但没有获取历史，只能声明本地内容身份匹配，不能虚构其下载来源／时间。

已有attempt但缺final／receipt，或仅有`.partial`，均记录为`UNSETTLED_OR_PARTIAL_NOT_REPLAYED`；不得把缺失receipt理解为“请求没有发出”。失败回执永久复用，不重新尝试。SIGINT／SIGTERM设置停发标志，正在读取的线程在安全检查点结束并保存回执；SIGKILL／断电无法承诺即时receipt，下一次恢复仍按未结算尝试处理，不重放。

若一次中断发生在部分文件尚未取得任何attempt之前，正常恢复只可能处理这些未开始且仍在原18项预算内的文件；已经失败／未知的文件不恢复下载。403／429具有更严格的整个阶段停发规则。

## 完成条件与测试范围

只有18个固定文件全部哈希通过，summary才能写`PINNED_MODEL_FILES_VERIFIED_NOT_LOADED`。部分成功、拒绝、超时、中断、哈希错误或未知尝试均保持`MODEL_ACQUISITION_NOT_READY_FAILED_OR_INTERRUPTED`。文件获取成功不等于依赖安装、模型运行兼容、视觉识读质量或独立审阅成立；官方源码build和后续有限模型能力测试属于另行冻结的阶段。

合成测试覆盖固定文件／预算、允许／拒绝HTTPS目标、签名query不落盘、GET前持久化、SHA-256与Git blob SHA-1、4跳／第5跳上限、403／429停发、精确字节+1、短流／错hash／Content-Length／encoding、超时／中断回执、未知attempt和partial不重放、本地完整文件恢复、已有文件损坏拒绝、磁盘门槛、路径隔离、direct/TLS/无认证及无未登记网络活动守卫。所有网络sender均为合成注入；本文编写时本阶段没有实际下载。
