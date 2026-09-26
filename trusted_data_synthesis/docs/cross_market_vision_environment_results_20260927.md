# 独立视觉依赖环境实际结果：CPU 构建成功，VLM 尚未就绪

## 1. 审计结论与范围

官方 torchvision 源码的第二个、独立登记的缓存构建阶段已实际成功。北京时间 **2026-09-27 02:08:34.939872** 完成，阶段总耗时 **325.569 秒（约 5 分 26 秒）**。它成功创建隔离环境、构建并安装 `torchvision 0.22.1+localcpu`，通过真实 torch/torchvision/Pillow 导入、native ops 加载以及合成 PIL 图片和 CPU 张量 resize 烟测。

正式状态严格为：

```text
CPU_VISION_ENVIRONMENT_READY_NOT_VLM_VALIDATED
```

**这不是独立 VLM 已启动或实验审阅已完成。** 该阶段新增 HTTP 请求、模型权重下载、模型加载、GPU 进程、真实图像/PDF 读取和语义证书均为 0。原失败保留且字节引用未改变；Student 环境未安装或升级包，运行时 metadata 前后相同。

本文只读取已保存的两个小型 summary，并从既有日志提取 CPU 配置、ninja 回退和烟测行；没有重新构建、测试、加载模型、探测网络或重新打开实验材料。权重阶段的最新受限状态来自主 agent 同轮执行通报，单独列于第 8 节，不把它计入本次 CPU 构建结果。

## 2. 可复核记录

缓存根为：

```text
/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/cross_market_calibration_cache_20260926/original_evidence_revision_02/
```

以下相对路径均相对于该根。

| 阶段 | 结果文件 | 完成时间，北京时间 | 阶段耗时 | 真实结果 |
| --- | --- | --- | ---: | --- |
| 原始源码构建 01 | `vision_source_build_01/summary.json` | 2026-09-27 01:48:59.970985 | 12.166 秒 | 安全解压遇 symlink 后停止，未建环境/编译 |
| 缓存构建修订 02 | `vision_source_cached_build_02/summary.json` | 2026-09-27 02:08:34.939872 | 325.569 秒 | CPU 依赖环境及有限合成烟测成功 |

01 原协议与失败记录 ID：

```text
cross_market_vision_source_build_protocol:fd6974d4db5c53dea6c9b498867fea6ff10e5d7f7c463e8097feeea5fc176486
cross_market_vision_source_build_completed:d3dbd96af1ad789c47ed635384a3d041783cc9fbb904d725c557247b4517159e
```

02 新协议与完成记录 ID：

```text
cross_market_vision_cached_build_protocol:e232528c5e57601afd33efeaf7166ed8cfef06cc7fc2589ee32fe4e037536b16
cross_market_vision_cached_build_completed:7abf22351b448e64e5b13eb2c1e75f45aa940b07965edfaa539d8275cb41b593
```

本报告的 325.569 秒是缓存复用、提取、环境准备、构建、安装、烟测组成的**整个 02 阶段墙钟时间**，不能直接称作单独的 C++ 编译耗时，也不能外推为模型下载或全量视觉审阅时间。

## 3. 01 为什么失败，哪些步骤已经真实完成

01 从官方公开来源接收源码 archive、Pillow wheel 和 setuptools wheel，共 3 个固定对象、4 个 HTTP 请求（包括正常源码重定向）。它并没有再次访问此前被拒的预编译 torchvision wheel 地址。

归档固定官方源码 commit：

```text
59a3e1f9f78cfe44cb989877cc6f4ea77c8a75ca
```

实际接收归档为 13,267,110 bytes，SHA-256：

```text
e5b2d896a8226f76cee8c7614d1a6ed834ba50607c3b0a2f2c03bde327447aad
```

归档收据在提取前已经保存。原规则拒绝所有链接，在 gallery 示例目录遇到 symlink 后停止；失败状态和原因仍是：

```text
SOURCE_BUILD_FAILED_NO_AUTOMATIC_RETRY
ValueError / cross_market.vision_build_no_archive_links_devices
```

这属于前瞻安全提取规则对官方 archive 中演示链接的拒绝，**不是源代码编译失败、torch ABI 失败、模型失败或 GPU 显存不足**。当时尚未创建新 venv、安装依赖或开始编译。原保留的 partial 提取目录没有用于 02，也没有因修订被删除或覆盖。

## 4. 02 的有限修订与实际提取结果

02 只改变两条已列明、不参与构建的 gallery 演示链接的处理方式：从“一律拒绝”改为“精确校验 header 后记录并跳过”。固定 archive 根为 `vision-59a3e1f9f78cfe44cb989877cc6f4ea77c8a75ca`。

| 根目录内成员 | 原始 linkname | 02 实际处理 |
| --- | --- | --- |
| `gallery/assets/coco/images/000000000001.jpg` | `../../astronaut.jpg` | 记录并跳过；未创建、未跟随 |
| `gallery/assets/coco/images/000000000002.jpg` | `../../dog2.jpg` | 记录并跳过；未创建、未跟随 |

名字、symlink 类型、linkname、零 size 均须与登记一致；其他链接、路径穿越、硬链接、设备文件、重复项与原大小/成员数上限继续拒绝。这不是打开一般链接支持，也没有把链接目标的图片读取或复制出来。真正编译的普通源文件仍来自同一 archive 的原始内容，没有为让构建通过修改源码。

本次真实提取清单：

- archive 成员 **1,005 项**（包含目录和两条被跳过链接），不是 1,005 个全部写出的普通文件。
- 写出普通文件合计 **18,799,129 bytes**。
- 精确记录并跳过 **2** 条声明链接。
- `links_created=0`，`links_followed=0`。
- 成员数低于 20,000 上限，普通文件总量低于 2 GiB 上限。

## 5. 独立环境与实际构建配置

新环境 Python：

```text
vision_source_cached_build_02/venv/bin/python
```

环境使用 Python 3.12.13，采用独立 venv 与自身 `.pth`，只读继承已有 Student site-packages。执行记录中的包版本与来源如下：

| 包 | 实际版本 | 来源 |
| --- | --- | --- |
| torch | 2.7.1+cu128 | 只读继承 Student 环境 |
| Transformers | 5.14.1 | 只读继承 Student 环境 |
| numpy | 2.5.1 | 只读继承 Student 环境 |
| wheel | 0.47.0 | 只读继承 Student 环境 |
| setuptools | 80.9.0 | 新 venv 本地 |
| Pillow | 12.3.0 | 新 venv 本地 |
| torchvision | 0.22.1+localcpu | 新 venv 本地、本次源码构建 |

本地 pip 使用已校验文件和 `--no-index --no-deps --ignore-installed --no-compile`。未在 Student 环境安装、卸载或升级任何包。02 完成记录明确保存 `parent_runtime_unchanged=true`；这是实际包 metadata 与路径来源比较及隔离执行的证据，不冒充对 Student 全目录逐字节审计。

已保存构建日志确认：

```text
FORCE_CUDA = False
BUILD_CUDA_SOURCES = False
USE_PNG = False
USE_JPEG = False
USE_WEBP = False
USE_NVJPEG = False
USE_CPU_VIDEO_DECODER = False
USE_GPU_VIDEO_DECODER = False
Building wheel torchvision-0.22.1+localcpu
```

因此 torch 的版本字符串仍含 `cu128` 不代表这次执行了 GPU 编译或 GPU 推理。torchvision 本次是 CPU 扩展构建，Pillow 负责本次合成图片路径，原生 codec 未启用。

日志还真实记录 **ninja 不存在，回退到 distutils backend**。`MAX_JOBS=8` 是冻结的有界请求，不能据此宣称实际八路编译，更不能把单阶段耗时当成八核效率测量。

## 6. 真实产物与烟测

唯一 wheel：

```text
vision_source_cached_build_02/source/vision-59a3e1f9f78cfe44cb989877cc6f4ea77c8a75ca/dist/torchvision-0.22.1+localcpu-cp312-cp312-linux_x86_64.whl
```

大小 **1,299,524 bytes**，SHA-256：

```text
1c7464752d895470a89539180b40f6cbb2f0fc15213cdb291de025f813e8cc1d
```

这是新构建的本地 CPU wheel，**不是**此前被拒的官方 `+cu128` wheel，也不沿用它的 SHA-256。体积较小不构成模型或精度结论；本次未构建 CUDA 和非必需 codec。

真实烟测输出包括：

```json
{
  "torch": "2.7.1+cu128",
  "torchvision": "0.22.1+localcpu",
  "Pillow": "12.3.0",
  "native_ops_loaded": true,
  "PIL_output_size": [5, 4],
  "tensor_shape": [3, 4, 5],
  "tensor_device": "cpu",
  "synthetic_images_only": true,
  "source_git_version": "Unknown"
}
```

烟测只用内存合成的 RGB 图片和 CPU 零张量做 resize；没有打开财务报告图片、PDF、原始实验图像或模型。`native_ops_loaded=true` 加上 resize 通过，证明了本次有限依赖路径实际可执行，但没有验证所有 torchvision 算子或完整 InternVL processor。

`source_git_version="Unknown"` 如实保留：公开 archive 没有 `.git`，且构建阻止向上误读外层项目 Git HEAD。来源证据是固定官方 commit、原 archive 收据和新构建产物 hash，不把上游生成的 Unknown 字段伪造为来源验证。

日志引用：

| 记录 | bytes | SHA-256 |
| --- | ---: | --- |
| `vision_source_cached_build_02/logs/build_CPU_torchvision.log` | 190,265 | `6cb388b48e251c66171ac9519e962374065f45e13b0ab5f60b5ad7eb9c4fa142` |
| `vision_source_cached_build_02/logs/synthetic_CPU_smoke.log` | 267 | `3f86d968fff03be0abf7e647c47dd9a6dd196c258f23e684287ca1197e600149` |

## 7. 预算、保存和旧失败保留

02 summary 实际记录：

| 项目 | 数量或状态 |
| --- | --- |
| 新环境/构建预约 | 1 次 |
| 缓存复用预约 / 实际完成 | 3 / 3 |
| 新 HTTP / 网络请求 | 0 / 0 |
| 模型权重下载 / 模型加载 | 0 / 0 |
| GPU 进程 | 0 |
| 真实图像读取、实验 PDF 调用 | 0 |
| 语义证书 | 0 |
| Student 运行时 metadata | 前后相同 |
| 原 protocol / 原失败引用 | 保持不变 |

原 01 的 4 次 HTTP 仍属于原 01，不能因为 02 是缓存构建就把整条准备链路称为“从未联网”；同样，不能把缓存复制数当作新 HTTP 数。旧失败没有退款重置，02 是独立授权、登记和预约的一次新尝试。实际 `parent_failed_result_unchanged=true` 表明旧失败已保留，后续成功不回写旧阶段为成功。

## 8. 当前尚未完成的 VLM 权重条件

主 agent 的同轮真实执行通报：权重获取的 cooldown02 阶段仍遇 **HTTP 429**；已成功取得 **4 个 metadata 文件，合计 47,398 bytes，权重文件为 0**。本报告没有重新请求这些地址、执行第三次匿名尝试或更换代理/出口，也没有将 4 个文件数量推断为该阶段全部 HTTP 请求数。

因此不能把本次 CPU 环境成功表述成“独立 VLM 已就绪”。目前仍需合规可用的模型权重来源：主 agent 正在请求用户提供有授权的 HF_TOKEN，或有官方来源与固定版本/hash 证据的模型 snapshot。凭据或来源补齐前，不安排新的匿名下载尝试，也不绕过 429。

即使后续权重取得，还需要另行记录固定 revision/hash、完整原生 processor/model 实际加载、有限合成/真实页试读的可读性与吞吐，再讨论正式独立视觉审阅。CPU resize 烟测不能代替以上任何一项。

## 9. 对实验进度的含义

本轮解决了一个真实的软件依赖准备障碍，并保留可复核的失败→修订→成功轨迹；尚未增加任何已审阅财务页、已认证 composition 任务、已编译面板或 Student 实验结果。三组各 60 的任务定义与门槛不变，原 pending 不因依赖环境成功而变成通过。

本报告不提供全量实验完成 ETA：尚无成功权重获取、VLM 实际推理或独立全源视觉审阅吞吐数据。325.569 秒只属于本次有明确结束点的依赖构建阶段，不能外推剩余实验时长。
