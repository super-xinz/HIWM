# HIWM × Companion Profile Engine 代码审计

审计日期：2026-08-01。两个目录是独立 Git 仓库，不是 Monorepo。真实旧前端为 Vue 3 + TypeScript + Vite + Pinia，并非提示词预估的 React/Next.js/Tailwind；HIWM 后端为 FastAPI/FastRTC，画像引擎也是 FastAPI。

## 采用的架构

- `HIWM`：一个 Zeabur `web-chat-api` Service。FastAPI 同源提供构建后的 Vue 页面、访问口令、Chat BFF、会话持久化、SSE，并继续承载原实时音视频能力。
- `companion-profile-engine`：一个独立 `profile-engine` Service，保持画像、规则、证据、审计和专家工作台边界。
- Zeabur PostgreSQL：画像生产数据库。
- HIWM `/data` 持久化卷：`companion-chat.db` 会话数据库。

这样浏览器只请求 HIWM 同源 `/api/v1/companion/*`；LLM Key 与画像 Key 都只存在于服务端环境变量。

## 可复用实现

- 后端入口：`src/demo.py`；`scripts/start_zeabur.sh` 已使用 `0.0.0.0:$PORT`。
- 前端注册：`src/service/frontend_service`；Vite 产物由同一 FastAPI 进程提供。
- 原模型代码：`src/handlers/llm/openai_compatible` 和 `src/handlers/hiwm/world_model.py`。
- 前端：`App.vue`、`VideoChat`、聊天记录、状态、Cognitive Stream、画像输入、媒体与三栏控制中心语言。
- 现有部署：`Dockerfile.zeabur`、`zbpack.json`、CPU Zeabur 依赖集。

## 新增边界

`src/service/companion_service` 包含配置、访问 Session、画像 Adapter、LLM Adapter、画像上下文 Composer、SQLite Session Store、Orchestrator 和 FastAPI 路由。前端新增 `CompanionDashboard.vue`、`AccessGate.vue` 与 `store/companion.ts`。

对话顺序固定为读取/初始化画像 → 白名单压缩画像 → 原模型流式生成 → 返回回复 → 写回画像 → 持久化消息。读取失败允许无画像聊天；写回失败保留回复并提供有限人工重试；LLM 失败绝不伪造回答。

## 不修改的核心

HIWM 的 RTC、VAD、ASR、TTS、头像渲染、HIWM 世界模型与安全规划器均未被重写；画像引擎的规则编译、画像评分、证据、九型策略、语义提取和专家发布流也保持原实现。

## 风险

- 未持有 Zeabur/GitHub 部署权限，当前只完成可部署代码和本地验证，未声称线上已发布。
- 实时音视频还依赖供应商 ASR/TTS、浏览器媒体权限和可选 TURN；文字画像聊天不依赖摄像头。
- 生产必须配置访问口令、持久化卷和 PostgreSQL，不能使用容器临时磁盘。
- 访问 Session 在进程内存中；重新部署后重新登录是预期行为。
