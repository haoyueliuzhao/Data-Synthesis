# FinQA V63 准备期GPU7临时占位

用户于2026-10-20在后继实验实现期间要求“先占用七号卡”。本操作仅为准备期资源占位，不是模型加载、反馈采样、训练或正式科学派发。

首次只读快照显示GPU7为UUID `GPU-ab6e97cc-19e4-64b8-f792-7b6920a45434`，空闲71423MiB，已有两个归属明确的GPU进程，未发现未知归属。此次只占用本项目原GPU7租约及64GiB空Tensor，不停止、迁移或修改其他项目；不宣称独占整张物理卡。

占位目录独立为 `v18_researcher_continuation_01/v63_resource_reservation_gpu7_20261020_01/`，不会提前创建尚未冻结的V63科学根。实际分配前再次检查归属和至少68GiB free，分配后要求仍有4GiB余量。占位最长3600秒；运行中free低于2GiB时释放自己的占位。SIGTERM/SIGINT正常释放，失败不自动重试。

正式派发前，核对本项目占位PID、birth及reserved记录，写入精确release请求；确认原身份退出、项目租约释放后，再让正式worker依新协议准入。占位保存的模型调用、optimizer更新均为0。资源许可不增加审计方案中的4200条反馈、1788次有效更新或7458条评价预算。

实施入口为 `scripts/finqa_v63_reservation.py`。实际成功以该目录 `reserved/record.json` 为准，释放以 `released/record.json` 与身份退出为准，源码准备不等于已占到显存。

首个64GiB实例PID3012254/birth490517357于15:19:41北京时间因申请前余量已经不足而退出，没有实际占位；其failure和released记录保持不变。随后显卡空闲仅38760MiB。为继续用户的GPU7占位请求，另登记唯一32GiB容量实例 `v63_resource_reservation_gpu7_20261020_02/`，原4GiB启动余量、2GiB运行free门和一小时上限不变；不重启01、不循环重试、不修改其他项目。新增参数只允许选择明确的01/64GiB或02/32GiB登记目录，没有任意卡或任意目录的派发范围。
