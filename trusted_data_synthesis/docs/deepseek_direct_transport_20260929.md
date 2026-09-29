# DeepSeek API项目入口直连修订

## 用户要求与边界

用户明确要求DeepSeek API直连，绕开其设置的反向代理。本次仅调整finance_research中现有DeepSeek专用httpx客户端/传输器的构造参数，将环境信任设置为 `trust_env=False`。

源码修订没有修改全局代理、.env、密钥、其他服务、模型名、提示、请求体、输出容量、重试规则、矩阵、钱包或网络UNKNOWN资格规则。不自动切回代理。新实验API模型仍严格为deepseek-flash。当前冻结长批另外通过仅新进程有效的NO_PROXY/no_proxy环境项切换，见下文；系统及用户全局环境不变。

## 具体修改范围

| 文件 | AsyncClient | 显式AsyncHTTPTransport |
|---|---:|---:|
| probe_provider.py | 1 | 1 |
| v6_review_provider.py | 1 | 1 |
| providers.py（DeepSeekFlashProvider） | 1 | 0 |
| probe_collection.py | 1 | 0 |
| v6_collection.py | 2 | 0 |
| v6_review_revision.py | 1 | 0 |
| v6_decomposed_review.py | 1 | 0 |
| v7_review_mask_trial.py | 1 | 0 |
| v8_collection.py | 1 | 0 |
| v8_review_validation.py | 1 | 0 |
| v9_production_review.py | 1 | 0 |
| 合计 | **12** | **2** |

源码功能差异仅为以上14处构造的 `trust_env=False` 关键字。两个已有显式传输器保留 `retries=0`；其他客户端仍用httpx原默认零重试传输器。没有设置 `verify=False` 或自行更换证书验证逻辑，TLS证书和主机名验证保持启用。严格审阅的beta endpoint、普通chat endpoint、认证header及原有超时均不变。

注意：httpx的trust_env同时禁止从环境读取代理及SSL证书路径等客户端环境配置；使用其默认可信CA与完整TLS校验，不通过关闭验证规避直连证书问题。

## 当前生产入口与外部client边界

本次源码版本的 `v9_production_review.run` 没有外部client注入参数，始终创建本次配置的专用客户端；因此从此版本启动的正常生产入口不会继承127.0.0.1:7897反向代理，也不会从失败直连回退到代理。当前长批仍运行原冻结版本，不混用这次修改后的源码。

这是项目现有真实入口的路由选择，不是重新设计通用安全API，也不声称阻止外部调用者在自己的代码中显式创建代理client。底层provider的既有mock/client注入接口保持不变；没有加入会破坏离线测试或第三方自有客户端的通用host guard。其他服务若仍使用自己的默认httpx客户端，继续按原环境代理运行。

## 验证

新增 `test_finance_deepseek_direct.py` 使用安装环境中的真实httpx/httpcore对象，测试过程不发送任何HTTP请求、不读取密钥、不访问实钱包、不初始化GPU：

1. 枚举现有12个专用客户端与2个显式传输器，全部要求trust_env=False；
2. 将测试进程的大小写HTTP/HTTPS/ALL_PROXY临时设置为127.0.0.1:7897；
3. 检查普通及beta DeepSeek URL实际选择的连接池为直接 `AsyncConnectionPool`，不是HTTP代理池；
4. 检查TLS证书验证、主机名验证和retries=0；
5. 检查测试过程中代理环境变量未被构造器修改；
6. 对照普通其他服务的默认客户端仍选用环境代理池；
7. 检查当前生产入口没有client注入参数。

验收结果：新增17项离线直连/host-only绕过控制及必要provider/controller回归合计53项通过，Ruff通过。对照基线4c6182c1c3逐文件移除上述构造中的trust_env关键字后，11个修改源码的AST完全相同；未修改任何非网络构造逻辑。

最小复现命令（在包含本次提交的工作树执行）：

```bash
PYTHONPATH=trusted_data_synthesis/src \
/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/.venv/bin/python \
-m pytest -q \
trusted_data_synthesis/tests/test_finance_deepseek_direct.py \
trusted_data_synthesis/tests/test_finance_v6_review_provider.py \
trusted_data_synthesis/tests/test_finance_research_probe_provider.py \
trusted_data_synthesis/tests/test_finance_v9_production_review.py
```

这些是离线路由/构造检查，不是已完成的模型调用、付费推理或实验结果。实际无鉴权网络连通性、旧进程在途收口及同一矩阵恢复由主执行流程另行记录。现有长批不新增源代码执行修订，而是保留其原执行绑定，仅登记用户明确要求的传输环境变化。

## 对已有运行的影响

正在运行的旧进程不会因文件变化自动替换已构造的客户端。必须先保留旧进程的真实返回与UNKNOWN、停止新派发并收口在途，再按同一原矩阵及既有恢复规则续跑。不能为应用直连而重发已发送请求、重置调用身份或丢弃UNKNOWN预留。本模块修订不自行操作任何正在运行的进程。

当前已冻结长批采用单独记录的运行环境切换：保留原冻结源及全部runtime/protected语义字节，仅在新controller子进程环境中将api.deepseek.com合并到NO_PROXY和no_proxy，原HTTP(S)_PROXY/ALL_PROXY及其他既有绕过项保持。它不是修改全局环境，也不是运行新的研究协议。停止、在途收口、环境记录及同矩阵恢复均由主执行流程实施。

新增离线控制使用安装版本的原默认httpx.AsyncClient构造：NO_PROXY/no_proxy含api.deepseek.com时，DeepSeek的models、普通chat和beta chat路由均为直连池；example.com仍指向原127.0.0.1:7897代理池，TLS验证与零重试保持。该控制不联网。上述14处trust_env=False是后续项目入口的持久修复，不写入正在运行的旧冻结树。

## 2026-09-29 实际切换记录

北京时间16:00左右，唯一一次无鉴权直连GET访问 `https://api.deepseek.com/models`：HTTP 401、TLS校验结果0、未建立代理CONNECT、远端36.150.72.122、耗时0.094475秒。401是未发送认证的预期响应，证明当时直连TCP/TLS和服务可达，不证明模型推理成功，也不能证明历史连接中断全部由代理造成。没有为测试额外发起推理或重试。

旧PID1905550原本继承指向127.0.0.1:7897的大小写HTTP/HTTPS代理。执行流程等待自然停止派发、在途调用结算；检测到零在途后，按原启动记录校验PID和进程启动tick，短暂停住旧进程，再次确认零在途才终止。若复核发现竞争派发，则立即继续旧进程等待下一安全点。实际停止后再次核对派发/预留计数、结算金额、UNKNOWN数与保留金额，均未改变。

北京时间16:15:20.977，启动新PID2901919，继续原 `resume` 入口：

- 仍从 `e6da9a422dd1726ef2a2f42e6aa2fb27a31468c6` 的原冻结工作树执行，运行时及受保护研究语义字节未改变；
- 从旧进程复制环境，仅合并 `NO_PROXY=api.deepseek.com` 和 `no_proxy=api.deepseek.com`；原HTTP/HTTPS代理值保留，其他服务不受本次切换影响；
- 相同13,022个登记工作、deepseek-flash、并发32、1200元总上限，未改请求体、评分、资格、UNKNOWN处置或训练准入；
- 停止时生产已派发4548次、获得真实返回4487次；61次生产连接UNKNOWN另列，另有历史UNKNOWN 1次，共62次永久保留；新进程使用既有用户授权处理尚未登记为终态的连接UNKNOWN，不重发这些请求；
- 停止点累计结算上界329.355871元、UNKNOWN保留138.149888元、剩余可承担敞口732.494241元。在途为0，所以该点保留额不含在途预留。费用是冻结峰值单价下的账本上界，不是供应商发票。

产物目录为 `trusted_data_synthesis/artifacts/finance_research_20260928/finqa_v6_01/conditional_five_arm_v9_01/`：

| 记录 | 内容身份 |
|---|---|
| `direct_route_change_01/record.json` | `59cb40799c8d4fde77a09d16a318a8301e7202975d22a75b39a8e7594c54c947` |
| `controller_direct_launch_01/record.json` | `6cc762acd7f8361ad3d7953b531eef9d3bb12e20db554ac9294788ef23c22f05` |
| `direct_route_verification_01/record.json` | `cfab249e3927a81f4c199c72cbfe5bf1c4221694bc7aaf24821b6fda2a9ce283` |

原 `controller_resume_launch_01` 和所有历史返回、失败、预留保持原样。新日志为 `controller_direct_01.log`；恢复阶段先核验旧材料，暂时没有新HTTP连接不等同于失败。此修订不启动GPU训练，不宣称实验已经完成。

### 实际生产直连验证

北京时间16:18:14，对新PID所属socket逐一核对，观察到已建立的公网443连接：36.150.72.122、36.150.244.216、223.109.219.89。观察期间未发现该PID连接本机7897/7890转发。其实际进程环境同时包含大小写NO_PROXY=api.deepseek.com，原HTTP/HTTPS代理变量仍存在；结合安装版本的真实httpx主机路由控制，可确认当前生产入口绕过环境代理。

该时点生产状态为 `PRODUCTION_SLOT_RUNNING`：派发4580、真实返回4488、生产网络UNKNOWN终态61、终态合计4549/13022；账本显示31项在途，与4580−4549相符。相较切换前已收到1项新的真实返回，原UNKNOWN总数62（含历史1项）没有增加。所有新调用均来自原矩阵尚未发送项，额外付费连通性试验为0。16:19:06的后续只读状态已推进至4600派发、4508真实返回、61生产UNKNOWN。

这是短时生产恢复及路由证据，不是长期错误率评估。不能据此宣称历史RemoteProtocolError均由代理导致、直连绝不出错或实验资格已经全部确认。若后续出现已授权范围内的连接UNKNOWN，继续保留预留、登记真实终态、不重发；其他错误仍按既有安全边界停止。
