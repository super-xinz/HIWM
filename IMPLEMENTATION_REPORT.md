# HIWM 画像聊天实施报告

日期：2026-08-01

## 交付结论

HIWM 已新增一套可部署的画像感知陪伴聊天体验，默认首页为响应式三栏控制台。实现基于仓库真实技术栈 Vue 3 + TypeScript + Vite + Pinia + FastAPI，没有另起一套与现有项目割裂的 Next.js/Node 服务。FastAPI 同时托管前端、访问控制、Chat BFF、会话存储和健康检查；原实时互动功能在运行时可用时仍可切换。

## 真实调用链

每轮严格执行：读取或初始化画像 → 组合边界清晰、长度受限的画像上下文 → 调用配置的 OpenAI-compatible 模型 → 把原始用户消息和最近上下文写回画像引擎 → 持久化用户消息、助手回复、模型名、耗时、画像版本与更新结果。SSE 接口提供 `meta`、`delta`、`final` 事件；相同 `turn_id` 重放缓存结果，不重复调用模型或画像写入。

## 后端与安全

- 新增 `src/service/companion_service/`：配置、访问控制、SQLite 会话库、画像客户端、模型客户端、提示词组合、编排器与路由。
- 新增轻量生产入口 `src/companion_demo.py`，Zeabur 默认以 `HIWM_COMPANION_ONLY=true` 启动，无需加载 RTC/VAD/音视频模型即可提供核心 Demo。
- 模型 Key、画像 Key 与访问口令只存在服务端环境变量；浏览器只获得 HttpOnly、SameSite=Strict 会话 Cookie。
- 访问口令做服务端校验和失败频率限制；日志不输出凭证、Prompt、原始消息或完整画像。
- 模型失败不会伪造回复；画像读取失败可降级聊天；画像写回失败保留回复并可从持久化 payload 单独重试。

## 前端体验

- 左栏：真实画像版本、置信度、特质、互动偏好与当前状态。
- 中栏：持久化会话、流式回复、停止生成、新会话与清空会话。
- 右栏：应用/模型/画像/数据库状态、模型名、画像更新摘要、分阶段耗时、画像开关、重试与二次确认重置。
- 独立访问口令页；桌面三栏、平板两栏、移动端单栏响应式布局。

## 验证结果

- 新增后端专项测试：`5 passed`，覆盖真实编排顺序、Prompt 注入、写回失败、幂等 turn、服务端访问 Cookie 与轻量入口。
- 前端单元测试：`41 passed`，包含拆分 SSE chunk、重复事件、无效 JSON 与首次会话刷新恢复；TypeScript typecheck、Vite production build 均通过。
- ESLint：0 errors；仓库仍有既有代码 warning，本次新增前端文件已用项目 Prettier 格式化。
- 端到端本地冒烟：访问登录、健康检查、画像初始化、模型回复、两条消息持久化、画像刷新全部通过，画像 v1 → v2。
- 仓库全量 Python 测试在当前 Windows/Python 3.13 通用环境无法收集既有 RTC/macOS 测试：缺少 `loguru`、`librosa`，且 `fcntl` 仅存在于 POSIX。这不是本次画像聊天专项测试失败；正式 HIWM 全量回归应在项目声明的 Python 3.11/macOS 或对应完整依赖环境执行。

## 部署状态与后续

Dockerfile、环境变量、`/data` 会话卷、健康检查、冒烟脚本以及更新/回滚/故障排查手册均已准备。当前工作区没有目标 Zeabur/GitHub 发布权限，所以公开域名和线上状态仍由部署人员按 `docs/DEPLOYMENT_ZEABUR.md` 完成；建议依次发布 PostgreSQL、profile-engine、web-chat-api，再跑 `scripts/smoke-test.sh` 或 `.ps1`。
