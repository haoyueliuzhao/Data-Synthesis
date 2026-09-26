# 官方源码 CPU 构建修订 02：缓存复用与两项演示链接排除

## 1. 原始实际结果与修订范围

`vision_source_build_01` 已合法接收 3 个固定对象，合计 4 个 HTTP 请求（含官方源码重定向）。原失败发生在安全解压遇到 gallery 演示 symlink 时，**尚未创建 venv、安装依赖或开始编译**；Student 运行时 metadata 未改变。原失败永久保留：

```text
protocol: cross_market_vision_source_build_protocol:fd6974d4db5c53dea6c9b498867fea6ff10e5d7f7c463e8097feeea5fc176486
summary: cross_market_vision_source_build_completed:d3dbd96af1ad789c47ed635384a3d041783cc9fbb904d725c557247b4517159e
status: SOURCE_BUILD_FAILED_NO_AUTOMATIC_RETRY
guard: cross_market.vision_build_no_archive_links_devices
```

真实接收源码 archive 大小 **13,267,110 bytes**，SHA-256：

```text
e5b2d896a8226f76cee8c7614d1a6ed834ba50607c3b0a2f2c03bde327447aad
```

这次只读 archive 成员检查已确认仅有两项非普通文件/目录，都是不参与构建的 gallery 演示链接。新阶段 `vision_source_cached_build_02` 仅改变它们的处理方式，不下载新文件、不修补真正编译的源文件、不改写原错误、不清理或复用原 partial 源码目录。

## 2. 精确跳过表：不创建、不跟随

固定顶层目录仍为 `vision-59a3e1f9f78cfe44cb989877cc6f4ea77c8a75ca`；只允许下列两个**精确名称、symlink 类型、零 size 和 linkname**匹配的成员被记录并跳过：

| 顶层目录内成员 | linkname |
| --- | --- |
| gallery/assets/coco/images/000000000001.jpg | ../../astronaut.jpg |
| gallery/assets/coco/images/000000000002.jpg | ../../dog2.jpg |

不创建符号链接、不解引用目标、不复制目标图片，也不读取实际图片内容。最后必须恰好记录到这两项；缺项、同名普通文件、同名硬链接、不同 linkname、重复项或第三条链接一律失败。它们仍计入 20,000 项的总成员上限。

其他规则维持原样：只接受固定 archive 根下的普通文件/目录，拒绝路径穿越、绝对路径、异常反斜杠路径、重复项、硬/软链接、设备/FIFO；普通文件合计仍不超过 2 GiB。不从 tar 恢复属主和可执行权限。所有正常源文件字节照原 archive 提取，构建配置未变。

## 3. 新的有限预算与缓存来源

登记时绑定原 protocol、原失败 summary、3 个原 artifact receipt 及各自路径/大小/SHA-256。原 archive 还须满足上述固定实际大小和 SHA-256；Pillow/setuptools 继续满足官方 wheel 哈希。新脚本必须提交冻结后才能登记。

运行只允许一次新的环境/CPU build 尝试、最多 3 次缓存复用。先写新 `attempt.json`，再把原已验证文件流式复制到新阶段 `downloads`，逐个核验实际复制字节与 SHA-256，持久化 **cached artifact reuse** 收据；不把复制伪称 HTTP 接收。新 attempt、各复用收据和 summary 均记录 `network_requests=0`、`HTTP_requests=0`。原文件只读，旧 partial 目录不动，新目录全新提取。

任何失败或遗留 attempt 不自动重做。此前消耗的 4 次 HTTP 和原失败不退款、不改状态；本阶段是新的明确授权预算，不是绕过原 no-retry 条款。

## 4. 复用冻结构建实现，不修改旧全局变量

新 runner 使用独立函数 namespace 绑定新的输出根；旧 `create_environment`、`pip_install`、`command`、`child_environment`、metadata/错误辅助函数的 code object 保持不变。旧模块的 `RAW`、函数和 flags 不修改；新 namespace 不提供 `acquire` 网络入口。

因此仍保持独立 `/data1` venv + 自有 `.pth` 只读继承 Student，固定本地 Pillow 12.3.0/setuptools 80.9.0 安装，`--no-index --no-deps --ignore-installed --no-compile`，子 Python `-I -B`；CPU 产物版本 `0.22.1+localcpu`，禁 CUDA 和非必需 codec，`MAX_JOBS=8`，无 ninja 时可能串行，1,800 秒构建超时和进程组终止不变。

成功前必须保留新产物真实 wheel hash，真实导入 torch/torchvision/Pillow，并通过同一内存合成 PIL 图像与 CPU 张量 resize。没有 VLM 权重、模型、PDF、真实图像或语义证书调用。

成功状态仍为 `CPU_VISION_ENVIRONMENT_READY_NOT_VLM_VALIDATED`；失败为 `CACHED_SOURCE_BUILD_FAILED_NO_AUTOMATIC_RETRY`。结束时重新验证原 protocol/失败 summary 字节未变，并检查 Student 运行时 metadata 不变。即使成功也只证明依赖和合成 CPU 烟测，不证明 VLM 已加载、真实财务页已读或全源审阅已完成。

## 5. 本文件写入时的执行状态

仅完成新 runner、合成测试和文档；未实际登记、复制真实缓存、解压真实 archive、创建环境、构建或安装。主 agent 提交冻结后可执行新 `register/run`，真实结果另记，不在此预报成功。
