# Zeabur 部署手册

本文以 2026-08-01 的官方 Zeabur 文档和两个真实仓库为准。Zeabur 支持按 Git push 自动部署、手动 Redeploy、Root Directory、Watch Paths、Dockerfile 路径、环境变量引用、生成 `.zeabur.app` 域名和持久化卷。Zeabur 不直接从 `docker-compose.yml` 部署，本项目正式方案不使用 Compose。

官方参考：[Dockerfile 部署](https://zeabur.com/docs/en-US/deploy/methods/dockerfile)、[环境变量](https://zeabur.com/docs/en-US/deploy/config/environment-variables)、[持久化卷](https://zeabur.com/docs/en-US/data-management/volumes)、[公网域名](https://zeabur.com/docs/en-US/deploy/networking/public-networking)。

## 1. 前置条件

- 对 `HIWM` 与 `companion-profile-engine` 两个 GitHub 仓库的读取/部署权限；生产分支建议 `main`。
- Zeabur 账号和目标区域资源。
- 一个 OpenAI-compatible 模型的 Base URL、Key、模型名。
- 为画像服务生成的独立长随机 API Key，以及 Demo 访问口令。
- 可选：`companion.agenttwin.cn` 等未占用的子域名。不要覆盖现有主站。
- 若启用 HIWM 实时互动，还需 `DASHSCOPE_API_KEY` 和可选 TURN 配置。

## 2. 创建 Project

在 Zeabur 新建 Project：`Companion Profile Demo`。所有服务放在同一 Project 和同一 Environment，便于变量引用、日志和回滚。

## 3. 创建服务

依次点击 Deploy New Service：

1. 从 GitHub 选择 `companion-profile-engine`，服务命名 `profile-engine`。
2. 添加 Zeabur PostgreSQL，命名 `profile-db`。
3. 从 GitHub 选择 `HIWM`，服务命名 `web-chat-api`。

不再创建独立 Node Chat API：HIWM 的 FastAPI 已同源承载 Vue 和 BFF。PostgreSQL 不是公共 Web 服务。

## 4. Root Directory 与 Dockerfile

两个仓库彼此独立，Root Directory 都是仓库根目录 `.`，不要把父工作区当成 Monorepo 上传。

| Service | Root Directory | 配置 |
| --- | --- | --- |
| `profile-engine` | `.` | `zbpack.json` → `Dockerfile` |
| `web-chat-api` | `.` | `zbpack.json` → `Dockerfile.zeabur` |

Dockerfile path 相对 Service build root。若控制台未读取 `zbpack.json`，分别设置 `ZBPACK_DOCKERFILE_PATH=Dockerfile` 与 `ZBPACK_DOCKERFILE_PATH=Dockerfile.zeabur`。

## 5. 构建与启动命令

使用 Dockerfile 时不要在控制台覆盖构建命令。有效命令为：

| Service | Build | Start |
| --- | --- | --- |
| `profile-engine` | Zeabur 构建根目录 `Dockerfile` | `sh -c "alembic upgrade head && profile-engine"` |
| `web-chat-api` | Zeabur 多阶段构建 `Dockerfile.zeabur`（pnpm frozen lockfile + Vite，随后安装 Python CPU 依赖） | `./scripts/start_zeabur.sh` |

两者均监听 `0.0.0.0` 和平台 `PORT`。不要用 `vite --host`、`uvicorn --reload` 或 `npm run dev` 作为生产命令。

## 6. 环境变量

### `profile-engine`

| 变量 | 必需 | 敏感 | 说明 |
| --- | ---: | ---: | --- |
| `PROFILE_ENVIRONMENT=production` | 是 | 否 | 关闭开发 Key 回退 |
| `PROFILE_DATABASE_URL` | 是 | 是 | 从 `profile-db` 暴露的 PostgreSQL connection string 映射；代码会把 `postgres://` 转 psycopg3 |
| `PROFILE_TENANT_API_KEYS` | 是 | 是 | JSON，例如 `{"demo-tenant":"<长随机值>"}` |
| `PROFILE_RULE_SOURCE_DIR=/app/rules` | 是 | 否 | 镜像内真实目录 |
| `PROFILE_SEMANTIC_EXTRACTOR` | 是 | 否 | `deterministic` 或 `qwen` |
| `PROFILE_QWEN_API_KEY` | 使用 qwen 时 | 是 | 画像语义提取 Key |
| `PROFILE_QWEN_BASE_URL` | 使用 qwen 时 | 否 | OpenAI-compatible URL |
| `PROFILE_QWEN_MODEL` | 使用 qwen 时 | 否 | 模型名 |
| `PROFILE_ALLOW_EXTERNAL_SEMANTIC_PROCESSING=true` | 使用 qwen 时 | 否 | 仅在取得外发授权后启用 |
| `PROFILE_DEMO_ACCESS_CODE` | 暴露内置工作台时 | 是 | 内置 `/demo`/`/rules` 的口令 |
| `PROFILE_DEMO_TENANT_ID=demo-tenant` | 是 | 否 | 必须与 HIWM tenant 一致 |
| `LOG_LEVEL=info` | 否 | 否 | 平台日志级别 |

`PORT` 由 Zeabur 注入，不手工固定。数据库连接值以 PostgreSQL Service 实际显示/暴露的变量为准，不复制到仓库。

### `web-chat-api`

| 变量 | 必需 | 敏感 | 说明 |
| --- | ---: | ---: | --- |
| `LLM_API_BASE_URL=https://api.deepseek.com` | 是 | 否 | DeepSeek 官方 OpenAI-compatible Base URL |
| `LLM_API_KEY` | 是 | 是 | 只在 FastAPI 服务端读取 |
| `LLM_MODEL=deepseek-v4-flash` | 是 | 否 | DeepSeek V4 Flash API 模型标识 |
| `LLM_TIMEOUT_MS=60000` | 是 | 否 | LLM 总超时 |
| `PROFILE_ENGINE_BASE_URL` | 是 | 否 | profile Service 的项目内 URL；无内部 URL时使用其受 Key 保护的 HTTPS 域名 |
| `PROFILE_ENGINE_API_KEY` | 是 | 是 | 必须与 `PROFILE_TENANT_API_KEYS[demo-tenant]` 相同 |
| `PROFILE_ENGINE_TENANT_ID=demo-tenant` | 是 | 否 | 租户隔离 |
| `PROFILE_ENGINE_TIMEOUT_MS=30000` | 是 | 否 | 画像超时 |
| `PROFILE_CONTEXT_MAX_CHARS=8000` | 是 | 否 | 注入模型的画像上限 |
| `DEMO_ACCESS_CODE` | 是 | 是 | 徐老师输入的访问口令 |
| `DEMO_DEFAULT_USER_ID=demo-xu` | 是 | 否 | 默认用户 |
| `DEMO_SESSION_TTL_SECONDS=28800` | 是 | 否 | 登录有效期 |
| `DEMO_COOKIE_SECURE=true` | 是 | 否 | Zeabur HTTPS 必须为 true |
| `COMPANION_DATABASE_URL=sqlite:////data/companion-chat.db` | 是 | 否 | 会话 SQLite，目录必须挂卷 |
| `HIWM_COMPANION_ONLY=true` | 是 | 否 | Zeabur 默认启动轻量文字陪伴服务；需要完整 RTC/VAD 运行时再改为 `false` |
| `GIT_COMMIT_SHA=${ZEABUR_GIT_COMMIT_SHA}` | 建议 | 否 | 健康检查版本 |
| `DASHSCOPE_API_KEY` | 实时互动时 | 是 | ASR/TTS/HIWM；文字聊天可仅配 LLM Key |
| `HIWM_RUNTIME_CONTROL_TOKEN` | 远程运行控制时 | 是 | 长随机 Bearer Token |
| `HIWM_TURN_URLS`/用户名/凭据 | 跨网 RTC 时 | 是 | 可选 TURN |

密钥不得使用 `VITE_`、`NEXT_PUBLIC_` 等前端公开前缀。Zeabur Variables 页支持 Raw 编辑和 `${VARIABLE}` 引用；保存变量后执行 Redeploy。

DeepSeek V4 Flash 使用官方模型标识 `deepseek-v4-flash`。部署前可在本地 `.env` 填入同一 Key 后运行 `python scripts/check_deepseek.py`；线上则以完整 Chat 冒烟脚本为最终连通性标准。健康检查中的 `llm=configured` 仅表示变量存在，不代表 Key、余额和模型权限已验证。

## 7. 持久化

1. `profile-db` 使用 Zeabur PostgreSQL，并启用平台数据库备份。
2. 打开 `web-chat-api` → Volumes → Mount Volume：Volume ID `companion-data`，Mount Directory `/data`。
3. 确认 `COMPANION_DATABASE_URL=sqlite:////data/companion-chat.db` 后再首次写入。

官方文档说明容器默认是无状态的，挂卷后目录可跨重启保留；挂载会清空目标目录，已有数据必须先备份。挂卷服务重启会有短暂中断，不再是零停机切换。

## 8. 域名

- `web-chat-api` → Domains → Generate Domain，生成唯一 `*.zeabur.app`；这是交付给徐老师的唯一公开入口。
- 可选绑定 `companion.agenttwin.cn`，按控制台给出的 DNS 记录配置。
- `profile-db` 不得配置公共 Web 域名。
- `profile-engine` 优先使用项目内 Service URL；若当前 Project 无可用内部 HTTP 地址，可生成后端域名，但不对普通用户宣传，并保持 API Key、多租户和 Demo 口令。

网页与 BFF 同源，因此无需 `Access-Control-Allow-Origin: *`。画像访问发生在服务端，也不需要浏览器 CORS。

## 9. 首次部署验收

按依赖顺序部署：PostgreSQL → profile-engine → web-chat-api。

1. Build Logs：确认 profile 镜像完成 pip 安装；HIWM 完成 pnpm/Vite 和 Python CPU 依赖。
2. Runtime Logs：确认没有 Key、Cookie、Authorization、数据库密码；确认 `PORT` 和启动完成。
3. profile 健康：`GET https://<profile>/health`，`services.database=ok`。
4. web 健康：`GET https://<web>/api/health`；`profile_engine=ok`、`llm=configured`、`database=ok`、`access_protection=configured`。
5. 打开 web HTTPS，必须先看到口令页；错误口令不得进入。
6. 输入口令后发送两轮消息，观察 SSE 逐段输出、画像版本和更新摘要；刷新页面应恢复会话。
7. 在页面确认后重置画像；确认新画像回到 v1、当前测试会话清空。
8. 执行 `scripts/smoke-test.sh` 或 `.ps1`。

## 10. 自动部署、更新与 Watch Paths

两个服务分别关联自己的 `main` 分支。Git push 默认触发新部署；也可在 Dashboard 点 Redeploy。因为不是 Monorepo，每个服务 Watch Path 可留空；如仓库另有不触发部署的文档约定，再按团队规则缩小。

环境变量或卷修改后手动 Redeploy。先部署 profile-engine 的向后兼容版本，再部署 HIWM。不要同时进行数据库破坏性迁移和应用回滚。

## 11. 回滚

1. 在 GitHub/Zeabur Deployment History 找到上一个测试通过的 commit SHA。
2. 将对应仓库回退/重新部署到该 SHA；先回滚 HIWM，再评估画像 API 是否需要回滚。
3. 恢复当时环境变量版本，但不要把密钥写进 Git commit。
4. 检查 Alembic schema 与旧应用兼容；数据库迁移不可直接靠代码回滚猜测。
5. 验证 `/health`、口令、两轮聊天、画像读取/更新和持久化。

## 12. 故障排查

| 现象 | 检查 |
| --- | --- |
| Zeabur 选错 builder/Dockerfile | Root=`.`；检查 `zbpack.json`，必要时设置 `ZBPACK_DOCKERFILE_PATH` |
| 启动后无端口 | 不覆盖 EntryPoint；确认日志中的 `$PORT`，服务监听 `0.0.0.0` |
| profile 启动失败 | PostgreSQL URL、Alembic 日志、`PROFILE_TENANT_API_KEYS` JSON |
| 页面白屏 | HIWM frontend-builder 是否生成 `/app/frontend/dist`；浏览器 Network/Console |
| 口令正确仍循环登录 | HTTPS 下 `DEMO_COOKIE_SECURE=true`；本地 HTTP 改 false；检查 Cookie 被浏览器接受 |
| 前端无法聊天 | `/api/health`、BFF 日志 request_id、LLM 三个变量 |
| LLM 401 | Key/Base URL/模型供应商权限；不要在浏览器调试输出 Key |
| 画像 401 | tenant 名称和 JSON Key 映射是否一致；HIWM Key 是否相同 |
| 画像读取成功、更新失败 | 查看右栏版本/错误；点一次重试；若 409，重新开始新 turn |
| 重启后会话丢失 | `/data` 是否挂卷，SQLite URL 是否四斜线绝对路径 |
| 重启后画像丢失 | `PROFILE_DATABASE_URL` 是否确实指向 Zeabur PostgreSQL，而非容器 SQLite |
| SSE 一次性出现/中断 | 代理缓冲、60 秒 LLM 超时、浏览器 Network；响应已设置 no-buffer header |
| CORS | 正式模式应同源；不要用通配 CORS + 凭据，检查是否错误指向另一个域名 |

## 当前线上状态

代码与配置已准备，本地测试见 `IMPLEMENTATION_REPORT.md`。当前执行环境没有 Zeabur 账号/目标 GitHub 部署权限，因此公开域名、线上健康和自动部署触发尚待部署人员按本文完成，不得标记为已上线。
