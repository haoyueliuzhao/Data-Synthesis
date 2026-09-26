# 独立 VLM 部署准备：固定文件计划，尚未下载或启动

## 1. 截至本次只读准备的结论

拟使用官方 `OpenGVLab/InternVL3_5-8B-HF` 原生 Transformers 格式，固定 revision：

```text
741a7d03020411e666c6109218ab71e08151ef86
```

本次取得官方文件元数据，并完成只读环境、资源和源码依赖核查。**没有下载权重或 wheel，没有创建 venv、安装包、克隆/构建源码、加载模型、分配 GPU、渲染实验页或签发语义审阅证书。** 新脚本仅支持 `plan/register/status`；注册只保存离线计划，下载、安装、环境创建和源码构建均显式为 `false`，没有可执行实现。

当前标准加载准备尚未完成：匹配的 torchvision 官方 wheel 地址在一次 HEAD 请求中返回 HTTP 403，已停止该地址访问，没有 GET 重试、换代理、换节点或更换 wheel 镜像。该事实不等于整个 Hugging Face 不可访问，也不等于所有合法 VLM 部署路径不可行；公开官方源码构建是另一项待登记、待验证的正常软件构建方案，见第 6 节。

## 2. 官方来源、联网边界与许可

[官方模型页](https://huggingface.co/OpenGVLab/InternVL3_5-8B-HF) 和 [官方文件树](https://huggingface.co/OpenGVLab/InternVL3_5-8B-HF/tree/741a7d03020411e666c6109218ab71e08151ef86) 提供公开 Apache-2.0 模型。服务器本轮固定文件准备只进行了以下元数据请求，默认 TLS 校验、显式直连、不读取或输出代理凭据：

| 请求 | 结果 | 响应体 | 耗时 |
| --- | --- | ---: | ---: |
| 官方 HF model API `?blobs=true` | HTTP 200 | 5,219 bytes | 2.118 秒 |
| 官方 PyPI Pillow 12.3.0 JSON | HTTP 200 | 84,184 bytes | 0.714 秒 |
| 官方 PyTorch cu128 torchvision index | HTTP 200 | 107,212 bytes | 0.407 秒 |
| 官方 index 所列 torchvision wheel HEAD | HTTP 403 | 未读取 wheel 内容 | 未保留独立计时值 |

之前的独立网络诊断已证明同一官方 HF config 直连 HTTP 200，2,998 bytes，0.672 秒；该诊断只使用一个 GET，未触发 7897 备用请求。先前默认代理请求的 `URLError` 根因仍未确定。

HF API 返回 `private=false`、`gated=false`、`license=apache-2.0`。这些元数据支持按官方许可正常获取公开模型；未验证大型权重实际传输、CDN/Xet 链路、吞吐量或权重加载。页面可访问与服务器大文件下载成功必须分开表述。

新脚本本身联网预算为 0；上述仅为其冻结前元数据发现记录，而非后续可以重放的下载许可。

## 3. 文件级固定计划

只规划 4 个权重分片、14 个 README/config/tokenizer/processor/index 文件；排除示例图片/视频、`.gitattributes`、所有远程 Python 代码。每项精确文件名、大小、官方预期哈希和固定 revision URL 均写在新脚本 `MODEL_FILES`，登记时进入不可变 protocol。

权重总计 **17,056,744,056 bytes**，低于前瞻性 20,000,000,000 bytes 上限；辅助文件总计 **16,011,200 bytes**，低于 32 MiB 上限；模型文件合计 17,072,755,256 bytes。这里是十进制 bytes，不把 17.1 GB 混称为 17.1 GiB。

| 文件 | bytes | 官方哈希类别 |
| --- | ---: | --- |
| model-00001-of-00004.safetensors | 4,906,355,392 | LFS SHA-256 |
| model-00002-of-00004.safetensors | 4,915,962,480 | LFS SHA-256 |
| model-00003-of-00004.safetensors | 4,915,962,496 | LFS SHA-256 |
| model-00004-of-00004.safetensors | 2,318,463,688 | LFS SHA-256 |
| README.md | 43,006 | Git blob SHA-1 |
| added_tokens.json | 913 | Git blob SHA-1 |
| chat_template.jinja | 481 | Git blob SHA-1 |
| config.json | 2,998 | Git blob SHA-1 |
| generation_config.json | 121 | Git blob SHA-1 |
| merges.txt | 1,671,853 | Git blob SHA-1 |
| model.safetensors.index.json | 79,937 | Git blob SHA-1 |
| preprocessor_config.json | 666 | Git blob SHA-1 |
| processor_config.json | 72 | Git blob SHA-1 |
| special_tokens_map.json | 877 | Git blob SHA-1 |
| tokenizer.json | 11,424,484 | LFS SHA-256 |
| tokenizer_config.json | 7,614 | Git blob SHA-1 |
| video_preprocessor_config.json | 1,345 | Git blob SHA-1 |
| vocab.json | 2,776,833 | Git blob SHA-1 |

四个权重分片的官方 SHA-256 依次为：

```text
541b630d4a991a0f9502b87b7e7fa3a4a3b03bc0fec4a9057eeb0af35873beae
1dd4d7629deff34807654ca198f45166a532fdbc1bbda3fd80e5e69eebdcdcd4
595f3b9043d046ae612f2dbf7cbfcd2465a1c001fcb58e93f78dcaf7cc5976e1
1935bfbc7774be5e64adf7ecec5cbefc7c18dae24d498ba4609301c3423b21fd
```

**Git blob SHA-1 不等于文件内容 SHA-1，更不等于 SHA-256。** 未来获取应按对应类型校验：Git 项使用 `SHA1("blob " + 十进制文件长度 + NUL + 原始内容)`；LFS 项使用原始内容 SHA-256，并另外保存实际文件 SHA-256、大小和 HTTP 接收记录。现阶段没有以“元数据哈希已知”冒充“文件下载后已校验”。

## 4. 隔离环境和资源快照

拟将模型缓存、独立 venv、pip cache、HF cache、临时构建目录全部放在项目 `/data1` 范围内，例如：

```text
/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/artifacts/qa_vnext_fixed_kernel_value/cross_market_calibration_cache_20260926/original_evidence_revision_02/vision_runtime_provision_01/
```

既有 Student 环境不修改。未来 venv 采用 `--system-site-packages`，但从已有 venv 的 Python 创建这种环境**不会自动继承父 venv 的包目录**；须在新环境内单独固定 `.pth`，只读指向已核验的父 site-packages。新环境本地包优先；不得在 Student 目录执行 pip。

只读运行时：Python 3.12.13、torch 2.7.1+cu128、Transformers 5.14.1、accelerate 1.7.0、safetensors 0.8.0。Pillow、torchvision、flash-attn 和 bitsandbytes 均不在该环境。拟保留 torch/Transformers 原版本，使用原生 HF 类、`trust_remote_code=False`、BF16/SDPA；不以更换模型或升级底座解决依赖问题。

资源快照为 8 张 A100-SXM4-80GB；GPU0 当时已占用 67,789 MiB，GPU1–7 各空闲 81,154 MiB。`/data1` 可用 953,787,166,720 bytes；根分区 `/tmp` 所在盘仅可用约 19.5 GB。资源随时变化，未来启动前仅需重新核查拟用 GPU 与目标磁盘；本阶段未占用 GPU。建议未来预留至少 50 GiB `/data1` 空间，初始试读按单卡 32 GiB 预算准备，后者是未实测的工程估计，不是已测显存峰值。

## 5. torchvision 依赖为何仍待解决

官方 PyPI 给出 Pillow 12.3.0 cp312 manylinux wheel 大小 6,940,830 bytes，SHA-256：

```text
78cb2c6865a35ab8ff8b75fd122f6033b92a62c82801110e48ddd6c936a45d91
```

官方 PyTorch cu128 index 给出 `torchvision-0.22.1+cu128-cp312-cp312-manylinux_2_28_x86_64.whl`，SHA-256：

```text
f64ef9bb91d71ab35d8384912a19f7419e35928685bc67544d58f45148334373
```

但该文件的 HEAD 被拒，因此大小仍记录 `null`，不猜测、不声称已获取；同址未进一步请求。

本地 Transformers 5.14.1 源码确有 `GotOcr2ImageProcessorPil`：`models/auto/image_processing_auto.py:104` 为 InternVL 映射 PIL 后端，`image_processing_backends.py:428` 的 `PilBackend` 只要求 vision/Pillow。可是 `models/internvl/processing_internvl.py:43` 的完整处理器还包含 `video_processor`；`processing_utils.py:1726,1806` 按签名加载全部子组件，`models/internvl/video_processing_internvl.py` 直接导入 torchvision，`BaseVideoProcessor` 也声明该依赖。因此 `backend="pil"` 或旧参数 `use_fast=False` **不能单独证明完整原生 AutoProcessor 可以省略 torchvision**。未修改库代码、伪造视频对象或自写未验证图像输入来绕过这一约束。

## 6. 合法替代：官方源码构建的有限可行性

公开 [TorchVision 0.22.1 release](https://github.com/pytorch/vision/releases/tag/v0.22.1) 明确对应 PyTorch 2.7.1；tag 指向完整 commit：

```text
59a3e1f9f78cfe44cb989877cc6f4ea77c8a75ca
```

[官方该版本构建说明](https://github.com/pytorch/vision/blob/v0.22.1/CONTRIBUTING.md) 给出源码构建路径；若采用 pip 构建，文档要求避免隔离构建自动另装底座。官方 [setup.py](https://github.com/pytorch/vision/blob/59a3e1f9f78cfe44cb989877cc6f4ea77c8a75ca/setup.py) 支持 C++/CPU 扩展与可选图像/视频 codec。这是从正常公开源码制作新的本地 wheel，**不是改路重试被拒的预编译 wheel**，来源和最终产物必须另立登记，不能冒充上述官方 wheel SHA-256。

本机只读核实：gcc/g++ 13.3.0、GNU Make 4.3、Python.h、wheel 0.47.0、numpy 2.5.1 可用；ninja、cmake、pkg-config 不在当前 PATH。torch `BuildExtension` 有无 ninja 时的标准 distutils 回退，故缺 ninja 本身不是已证实的硬阻碍。尚未做实际编译，不能据此保证 ABI、链接和导入成功。

两项必须在新构建协议中解决：

1. 当前 setuptools 83.0.0 不提供 `pkg_resources`，而该版本 torchvision 的 `setup.py` 顶层直接导入它。需要在**独立构建环境**固定仍提供该模块的兼容 setuptools；不得降级 Student 环境。后续元数据核查已选定80.9.0及其官方wheel SHA-256；本文件准备阶段仍未获取或安装该依赖，实际执行另立方案。
2. 本机 CUDA toolkit 是 12.4.131，而 torch 是 cu128。为图片/PIL 预处理可考虑只构建 CPU torchvision 扩展，模型本体仍使用现有 GPU torch；构建时对子进程禁用 CUDA、NVJPEG 和不需要的视频 codec，具体参数与产物特性需前瞻冻结。此为待测试方案，未认定 CPU wheel 已兼容所有未来调用。

未来最小步骤是先登记固定源码 commit、源码大小/哈希、兼容构建依赖、资源/时限和单次构建预算，再在 `/data1` 独立环境执行构建及有限 import/processor 检查。当前不 clone、不 build、不 install，也不打开额外模型下载权限。若依赖路线确实成功，再立新的有限模型获取和视觉试读协议。

## 7. 独立性与审阅含义

InternVL 使用不同的 OpenGVLab checkpoint 和本地执行过程，可与现有 DeepSeek scanner、Qwen Student 作操作层隔离；但[官方模型卡](https://huggingface.co/OpenGVLab/InternVL3_5-8B-HF)说明其语言骨干为 Qwen3-8B，部分训练推理样本使用 DeepSeek-R1。因此不得宣称谱系、训练数据或误差相关性完全独立。未来应明确这一局限，冻结模型、提示、输入页、输出与人工/独立审阅责任，不能仅因“用了另一个模型”自动签发独立语义证书。

本阶段不改变 3 组各 60 的目标，不选择题、不把 composition 的 pending 改为通过，也不以小模型未经验证的输出补足审阅。真实视觉试读、可读性、遗漏率、显存峰值和吞吐未测，因此没有给出全量独立审阅的完成时间。
