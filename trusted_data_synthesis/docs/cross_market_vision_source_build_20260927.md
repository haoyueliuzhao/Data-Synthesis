# 独立视觉环境：一次有限的官方源码 CPU 构建

## 1. 范围与状态

本文件登记的是环境准备，不是 VLM 试读、实验结果或独立语义证书。新增 `build_cross_market_vision_environment_20260927.py`，由主 agent 提交冻结后才执行 `register/run`。本次实现和合成测试不下载真实文件、不创建环境、不安装或构建。

父阶段为 `vision_runtime_provision_01/protocol.json`，固定模型 `OpenGVLab/InternVL3_5-8B-HF` 的 metadata 清单；父协议自己的下载/安装权限仍为 false，新阶段不改写它。新输出位于同一 `/data1` 实验缓存的 `original_evidence_revision_02/vision_source_build_01`。Student 环境和已冻结实验模块不修改。

此次尝试是从 [PyTorch 官方公开源码](https://github.com/pytorch/vision/tree/59a3e1f9f78cfe44cb989877cc6f4ea77c8a75ca) 构建新的本地 wheel，**不访问此前 HTTP 403 的预编译 wheel 地址，也不换代理、节点或镜像重试它**。GitHub/codeload 是官方源码正常归档链路，不冒充被拒 wheel 的镜像。torchvision [v0.22.1 release](https://github.com/pytorch/vision/releases/tag/v0.22.1) 对应 torch 2.7.1。

## 2. 三个固定获取对象

仅下列 3 个对象各最多一次初始 GET；只允许每项最多 2 个官方重定向，总 HTTP 请求上限 9。无 HEAD、无自动重试、无代理环境继承，TLS 使用默认校验。任何 403/429、连接错误、大小/哈希错误均停止本轮，不转路。接收超时单 socket 60 秒，每项流式接收最多 600 秒。

| 对象 | 固定内容 | bytes / 上限 | SHA-256 |
| --- | --- | ---: | --- |
| torchvision 源码 archive | commit `59a3e1f9f78cfe44cb989877cc6f4ea77c8a75ca` | 最多 256 MiB，实际大小未知 | 接收后记录真实 hash；事前未知 |
| Pillow 12.3.0 | cp312 manylinux_2_27/2_28 x86_64 wheel | 精确 6,940,830 | `78cb2c6865a35ab8ff8b75fd122f6033b92a62c82801110e48ddd6c936a45d91` |
| setuptools 80.9.0 | py3-none-any wheel | 精确 1,201,486 | `062d34222ad13e0cc312a4c02d73f059e86a4acbfbdea8f8f76b28c99f306922` |

源码固定 URL 为 `https://github.com/pytorch/vision/archive/59a3e1f9f78cfe44cb989877cc6f4ea77c8a75ca.tar.gz`；仅允许 `github.com` → `codeload.github.com` 官方 HTTPS 路径。两个 wheel 的完整 PyPI 文件 URL 来自官方版本 metadata，精确保存于新脚本和协议。未替换 torch、Transformers、numpy 或 wheel；没有下载 InternVL 权重。

归档的 SHA-256 在接收成功后**先持久化收据，再提取任何成员**。没有事先已知的归档 digest，因此不声称第三方签名或预先独立 checksum 已验证。两个依赖 wheel 则须同时满足精确大小和官方 SHA-256。

## 3. 安全提取、一次性尝试与失败保留

启动前保留全局 `attempt.json`，一次性预约 3 个 artifact 尝试和 1 次环境/构建尝试。每个 HTTP 请求另有先写入的 request 记录；成功 artifact 收据包含实际大小、SHA-256、响应状态和请求次数。失败 summary 或遗留 attempt 都不会自动退款重做。

解压只接受固定顶层目录 `vision-59a3e1f9f78cfe44cb989877cc6f4ea77c8a75ca` 下的普通文件与目录，拒绝绝对路径、`..`、反斜杠路径、重复项、符号链接、硬链接、FIFO 和设备文件。最多 20,000 个成员、普通文件合计最多 2 GiB；不沿用归档中的属主或可执行权限。部分下载、提取和编译产物在失败时保留以供审计，不覆盖或自动清理。

初始磁盘空闲至少 20 GiB；所有 artifact、源码、venv、日志、pip/HF/torch 缓存和临时目录均落在独立 `/data1` 阶段目录，不把权重或构建产物放到 `/tmp` 根盘。构建命令最长 1,800 秒；超时会终止其进程组，避免遗留编译子进程继续占用资源。

## 4. 独立环境与固定构建设置

使用现有 Python 3.12 创建 `--system-site-packages` venv，在新环境内新增 `.pth` 只读继承 Student site-packages。固定继承 torch 2.7.1+cu128、Transformers 5.14.1、numpy 2.5.1、wheel 0.47.0；只在新环境本地安装 Pillow 12.3.0 和 setuptools 80.9.0。

setuptools 80.9.0 的[官方源码仍包含 pkg_resources](https://github.com/pypa/setuptools/blob/v80.9.0/pkg_resources/__init__.py)，满足旧 torchvision setup.py 的真实导入需求；Student 的 setuptools 83.0.0 保持原样。所有 pip 操作只用已校验本地 wheel，加 `--no-index --no-deps --ignore-installed --no-compile`，不让解析器升级底座或尝试卸载父环境包。子进程使用 `-I -B`，避免普通导入回写父环境 `.pyc`。

依据[该版本官方 setup.py](https://github.com/pytorch/vision/blob/59a3e1f9f78cfe44cb989877cc6f4ea77c8a75ca/setup.py) 已存在的设置，前瞻固定：

```text
BUILD_VERSION=0.22.1+localcpu
CUDA_VISIBLE_DEVICES=
FORCE_CUDA=0
FORCE_MPS=0
MAX_JOBS=8
TORCHVISION_USE_PNG=0
TORCHVISION_USE_JPEG=0
TORCHVISION_USE_WEBP=0
TORCHVISION_USE_NVJPEG=0
TORCHVISION_USE_VIDEO_CODEC=0
TORCHVISION_USE_FFMPEG=0
```

仅构建 CPU `_C`/image 扩展；图像解码由 Pillow 完成，禁用非必需原生 codec。CUDA 隐藏仅作用于本次构建/烟测子进程，不改变用户 shell、Student、GPU 调度或其他任务。现有 CUDA toolkit 12.4 与 torch cu128 的差异不通过更换 torch 处理，而是本次不编译 CUDA 扩展。

源码 archive 无 `.git`，构建子进程设置 Git 搜索上界以阻止 `setup.py` 误读外层 Data-Synthesis 的 commit。源码来源以 archive receipt 和固定官方 commit 为准；上游生成的 `torchvision.version.git_version` 可能为 `Unknown`，不伪造该字段。产物版本明确为 **`0.22.1+localcpu`**，绝不冒充官方 `0.22.1+cu128` wheel，保存新产物的真实 SHA-256。

本机没有 ninja；不新增 ninja 依赖。`MAX_JOBS=8` 是有界请求，不是已使用 8 个编译进程的证据。torch BuildExtension 在缺 ninja 时有标准 distutils 回退，实际可能串行，保留日志和实测用时。

## 5. 成功条件与不能推出的结论

构建必须产生唯一、最多 256 MiB 的 `torchvision-0.22.1+localcpu-*.whl`；先记录其 hash，再本地安装。烟测仅执行真实 `torch`、`torchvision`、`PIL` 导入，检查 native ops 扩展载入，并用内存新建的 10×8 RGB 图片和 CPU 零张量做 5×4 resize。不开原始图片、PDF、模型文件或网络图像，不运行 Student/DeepSeek/VLM。

完整成功状态为 `CPU_VISION_ENVIRONMENT_READY_NOT_VLM_VALIDATED`，只表示 CPU 依赖准备和有限合成烟测通过；不表示 InternVL 权重已下载、完整 processor/model 已加载、GPU 推理已成功、财务页可读性已确认或全源独立审阅已完成。失败使用 `SOURCE_BUILD_FAILED_NO_AUTOMATIC_RETRY`，保留实际错误类别与日志；若父运行时 metadata 改变则单独标记待调查，不掩盖异常。

模型文件获取另立独立有限预算，可根据构建进度与资源风险并行准备；但实际模型加载和视觉试读必须等待环境验证与权重校验均完成。不得本阶段扩展到语义认证、选题、正式面板或降低既定门槛。
