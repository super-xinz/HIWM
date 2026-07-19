# HIWM Interaction Demo

**人际互动世界模型（Human Interaction World Model, HIWM）的交互决策演示平台。**

[English](README.en.md) · [运行架构](docs/guides/hiwm-runtime.md) · [研究定义](docs/research/hiwm-definition.zh-CN.md) · [验收记录](docs/reports/acceptance-2026-07-18.zh-CN.md)

本项目把实时音视频、语音识别、结构化交互推演、语音合成和可选数字人管线组合成一个可运行的研究原型。系统基于用户明确同意采集当前会话的有限证据，为每轮对话生成三条候选沟通动作，依据目标、信息增益、风险与不确定性选择一条，在执行前写入可校验账本，并用下一轮实际回应更新工作信念。

> [!IMPORTANT]
> 这是交互决策 Demo，不是独立训练或可下载的 HIWM 基础模型，也不是经过真实人群校准的“读心”系统。当前模型概率属于未校准演示估计；项目不推断隐藏情绪、人格、欺骗、心理健康、受保护属性或就业适格性。

## 当前状态

- 项目版本：`0.1.0`
- 默认本地环境：Apple Silicon macOS，Python 3.11，Node.js 22
- 默认云服务：阿里云 Model Studio / DashScope（ASR、结构化多模态推演、TTS）
- 当前验收：后端、前端、隐私边界和本地闭环已有自动化覆盖；真实摄像头、麦克风、扬声器仍需人工设备验收
- 已知限制：当前加固版 HIWM 云端端到端闭环尚未完成重新付费验证，不能表述为已完成真实人群验证或生产级模型

## 两个项目，一个仓库

| 部分 | 位置 | 技术栈 | 职责 |
| --- | --- | --- | --- |
| 服务端 | 仓库根目录、`src/` | Python、FastAPI、WebRTC | ASR、HIWM 推演与规划、预测锁、TTS、会话和审计 API |
| 交互前端 | `frontend/` | Vue 3、TypeScript、Vite、Electron | 知情同意、摄像头/麦克风、派生证据、三分支决策与事件回放 |

第三方算法仍以固定提交的 Git 子模块保留在各 Handler 路径中。前端是本项目的一部分，不再连接原 WebUI 子模块，因此一次提交即可完整包含前后端改动。

## 核心流程

```text
用户同意 → WebRTC 音视频 → VAD / final ASR
        → 有界视觉与语气派生证据 + 用户确认背景
        → 三条候选动作 → 服务端风险/不确定性规划
        → JSONL + SHA-256 预测锁 → TTS 执行
        → 下一轮实际回应 → 反馈评估与工作信念更新
```

原始音频、视频、图片和完整人脸点位默认不写入回放；浏览器只保存有界文本和数值派生事件。服务端预测账本与浏览器事件时间线是两个不同的数据面。

## 快速开始（macOS）

首次获取代码后初始化第三方子模块：

```bash
git submodule update --init --recursive
bash scripts/setup_macos.sh
```

启动服务：

```bash
bash scripts/start_macos.sh
```

浏览器访问 <http://127.0.0.1:8283>，直接在合并后的启动页输入 DashScope API Key，并点击一次“同意、授权并进入下一步”。Key 只进入当前本机服务进程的内存，不写入 `.env` 或浏览器存储；服务重启后需要重新输入。首次使用摄像头或麦克风时，浏览器仍会显示系统权限确认。

需要无人值守启动时，仍可选择在被 Git 忽略且权限为 `0600` 的 `.env` 中配置 `DASHSCOPE_API_KEY`。更完整的说明见 [macOS 启动指南](docs/guides/macos-setup.md)。

## 开发与验证

后端测试：

```bash
.venv/bin/python -m pytest -q
```

前端检查与构建：

```bash
cd frontend
pnpm install --frozen-lockfile
pnpm run check
pnpm run build
```

文档站构建：

```bash
cd docs
npm ci
npm run docs:build
```

提交前请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。不要提交 `.env`、模型权重、日志、运行账本、构建产物或任何真实会话数据。

## 文档

- [HIWM 运行架构、隐私边界与数据位置](docs/guides/hiwm-runtime.md)
- [macOS 安装与启动](docs/guides/macos-setup.md)
- [HIWM 正式定义与研究依据](docs/research/hiwm-definition.zh-CN.md)
- [正式 Demo 设计方案](docs/research/hiwm-demo-design.zh-CN.md)
- [2026-07-18 软件验收记录](docs/reports/acceptance-2026-07-18.zh-CN.md)
- [安全报告流程](SECURITY.md)

## 上游与许可证

本项目 `0.1.0` 基于 [OpenAvatarChat](https://github.com/HumanAIGC-Engineering/OpenAvatarChat) `0.6.0`（基础提交 `dcfba11`）及 [OpenAvatarChat-WebUI](https://github.com/HumanAIGC-Engineering/OpenAvatarChat-WebUI)（基础提交 `a6182af`）开发，并进行了实质性修改。本项目不隶属于上述上游项目，也不代表其官方版本。

根项目继续使用 [Apache License 2.0](LICENSE)。上游来源、原作者引用和修改范围见 [UPSTREAM.md](UPSTREAM.md)，第三方组件及各自许可证见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。模型权重、人物素材和云服务受各自条款约束，不因本仓库许可证自动获得授权。
