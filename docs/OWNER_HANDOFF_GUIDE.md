# 画像感知陪伴 Demo：负责人运行、展示与验收手册

适用项目：

- `super-xinz/companion-profile-engine`：人物画像、证据、偏好、状态、版本和规则 API。
- `super-xinz/HIWM`：Vue 控制台、访问保护、DeepSeek Chat BFF、流式回复和会话存储。

本手册面向项目负责人、演示人员和部署人员。任何真实 API Key、数据库密码和访问口令都只能通过本地 `.env` 或部署平台 Secret 注入，不能提交到 Git、放入前端变量或粘贴到文档。

## 1. 当前产品形态

默认交付的是画像感知文字陪伴 Demo：

```text
Vue 浏览器控制台
  → HIWM FastAPI BFF
  → 读取或初始化 Profile Engine 画像
  → 组合受限的画像上下文
  → DeepSeek V4 Flash
  → SSE 流式回复
  → 用户消息写回 Profile Engine
  → SQLite 保存会话与画像更新结果
```

原实时音视频 HIWM 能力仍保留，但默认 `HIWM_COMPANION_ONLY=true`，不加载 RTC、VAD、Avatar 等资源。文字陪伴模式不需要 `DASHSCOPE_API_KEY`。

DeepSeek 官方配置：

```dotenv
LLM_API_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-v4-flash
```

官方参考：

- https://api-docs.deepseek.com/zh-cn/quick_start/pricing
- https://api-docs.deepseek.com/zh-cn/api/list-models/

## 2. 负责人需要准备

- Windows 10/11 PowerShell，或 Linux/macOS Shell。
- Conda；Profile Engine 使用仓库 `environment.yml`。
- Python 3.11；HIWM 使用独立 `.venv`。
- Node.js 22、Corepack、pnpm。
- 有余额且有 `deepseek-v4-flash` 权限的 DeepSeek API Key。
- 本地端口 `8000`、`8283` 未被占用。

若负责人使用当前已配置电脑，`companion-profile-engine/.env` 和 `HIWM/.env` 已存在，只需填写 `HIWM/.env` 的 `LLM_API_KEY`。若从 GitHub 重新克隆，`.env` 不会随 Git 下发，必须按第 4 节创建。

## 3. 获取代码

建议把两个独立仓库放在同一个父目录：

```powershell
New-Item -ItemType Directory companion-profile-demo
Set-Location companion-profile-demo
git clone https://github.com/super-xinz/companion-profile-engine.git
git clone https://github.com/super-xinz/HIWM.git
```

确认都在 `main` 且工作区干净：

```powershell
git -C companion-profile-engine status -sb
git -C HIWM status -sb
```

验收记录中应写下两个仓库实际使用的 commit SHA：

```powershell
git -C companion-profile-engine rev-parse HEAD
git -C HIWM rev-parse HEAD
```

## 4. 首次配置

### 4.1 Profile Engine

```powershell
Set-Location companion-profile-engine
conda env create -p .\.conda-env -f environment.yml
conda run -p .\.conda-env python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

本地验收使用：

```dotenv
PROFILE_DATABASE_URL=sqlite:///./data/profile_engine.db
PROFILE_API_KEY=local-development-key
PROFILE_TENANT_API_KEYS={}
PROFILE_ENVIRONMENT=development
PROFILE_SEMANTIC_EXTRACTOR=deterministic
PROFILE_ALLOW_EXTERNAL_SEMANTIC_PROCESSING=false
PROFILE_DEMO_TENANT_ID=demo-tenant
PROFILE_PORT=8000
```

默认确定性画像提取不需要第二个 LLM Key。生产环境必须改用 PostgreSQL、`PROFILE_ENVIRONMENT=production` 和独立随机租户 Key。

执行迁移：

```powershell
conda run -p .\.conda-env alembic upgrade head
```

### 4.2 HIWM + DeepSeek

```powershell
Set-Location ..\HIWM
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-zeabur.txt

corepack enable
Set-Location frontend
pnpm install --frozen-lockfile
pnpm run build
Set-Location ..

Copy-Item .env.example .env
```

编辑 `HIWM/.env`：

```dotenv
LLM_API_BASE_URL=https://api.deepseek.com
LLM_API_KEY=<在本机粘贴真实 DeepSeek Key>
LLM_MODEL=deepseek-v4-flash
LLM_TIMEOUT_MS=60000

PROFILE_ENGINE_BASE_URL=http://127.0.0.1:8000
PROFILE_ENGINE_API_KEY=local-development-key
PROFILE_ENGINE_TENANT_ID=demo-tenant
PROFILE_ENGINE_TIMEOUT_MS=30000
PROFILE_CONTEXT_MAX_CHARS=8000

DEMO_ACCESS_CODE=<生成一个仅供本次验收使用的随机口令>
DEMO_DEFAULT_USER_ID=demo-xu
DEMO_SESSION_TTL_SECONDS=28800
DEMO_COOKIE_SECURE=false

COMPANION_DATABASE_URL=sqlite:///./temp/companion-chat.db
HIWM_COMPANION_ONLY=true
PORT=8283
```

本地 HTTP 必须使用 `DEMO_COOKIE_SECURE=false`；部署到 HTTPS 时必须改为 `true`。

## 5. DeepSeek Key 独立检查

在启动完整服务前，先验证 Key、账户模型权限和最小 Chat Completion：

```powershell
Set-Location HIWM
.\.venv\Scripts\python.exe scripts\check_deepseek.py
```

成功标准：

```text
DeepSeek connection passed: model=deepseek-v4-flash
```

此探测不会输出 Key，但会产生极少量 token 费用。

常见结果：

| 结果 | 含义 |
| --- | --- |
| `LLM_API_KEY is empty` | 尚未把 Key 写入 `HIWM/.env` |
| 401/AuthenticationError | Key 错误、失效或读取了错误账号的 Key |
| 模型不可见 | 当前账号没有 `deepseek-v4-flash` 权限 |
| 429 | 余额、配额或限流问题 |
| ConnectionError/Timeout | 网络、代理、DNS 或 DeepSeek 服务异常 |

## 6. 启动顺序

必须先启动 Profile Engine，再启动 HIWM。

终端一：

```powershell
Set-Location companion-profile-engine
conda run --no-capture-output -p .\.conda-env profile-engine
```

终端二：

```powershell
Set-Location HIWM
.\.venv\Scripts\python.exe src\companion_demo.py
```

入口：

| 功能 | 地址 |
| --- | --- |
| 负责人 Demo | http://127.0.0.1:8283 |
| HIWM 聚合健康 | http://127.0.0.1:8283/api/health |
| HIWM Swagger | http://127.0.0.1:8283/docs |
| Profile 健康 | http://127.0.0.1:8000/health |
| Profile Swagger | http://127.0.0.1:8000/docs |

`/api/health` 中 `llm=configured` 只证明变量已填写，不能替代第 5 节和完整聊天验收。

## 7. 自动验收

### 7.1 Profile Engine

```powershell
Set-Location companion-profile-engine
.\scripts\smoke-test.ps1 `
  -BaseUrl "http://127.0.0.1:8000" `
  -ApiKey "local-development-key" `
  -TenantId "demo-tenant"
```

成功结果必须包含 `Smoke test passed` 和 `version=2`。

### 7.2 完整画像聊天链路

```powershell
Set-Location ..\HIWM
.\scripts\smoke-test.ps1 `
  -BaseUrl "http://127.0.0.1:8283" `
  -AccessCode "<与 DEMO_ACCESS_CODE 完全相同>"
```

正式合格输出：

```text
Smoke test passed
before_profile_version=1
after_profile_version=2
profile_update=updated
model=deepseek-v4-flash
```

如果 `model=mock-model`，只能证明兼容协议和本地链路正常，不能作为真实 DeepSeek 验收结果。

## 8. 负责人现场展示脚本

建议控制在 8 分钟：

1. 打开 `http://127.0.0.1:8283`，先展示访问口令保护。
2. 登录后介绍左侧画像、中间流式聊天、右侧服务状态和耗时。
3. 发送：`以后回答短一点，先听我把话说完。我最近在准备一个重要决定。`
4. 观察逐段回复、`profile_update=updated` 和画像版本 v1→v2。
5. 再发送：`请根据你目前了解的我，简短给出三个下一步建议。`
6. 刷新页面，确认会话与画像版本仍保留。
7. 演示关闭画像、新会话、清空会话和二次确认重置画像。
8. 打开浏览器 Network/Application，确认不存在 LLM Key、Profile Key 或正确访问口令。

## 9. API 与 Postman

详细接口：

- Profile Engine：`companion-profile-engine/docs/API_USAGE.md`
- HIWM BFF：`HIWM/docs/API_USAGE.md`
- 双 API 时序：`HIWM/docs/CHATBOT_INTEGRATION.md`

Postman Collection：

```text
companion-profile-engine/postman/companion-profile-engine.postman_collection.json
```

导入后设置：

| 变量 | 本地值 |
| --- | --- |
| `profileBaseUrl` | `http://127.0.0.1:8000` |
| `chatBaseUrl` | `http://127.0.0.1:8283` |
| `profileApiKey` | `local-development-key` |
| `tenantId` | `demo-tenant` |
| `accessCode` | 与 `DEMO_ACCESS_CODE` 相同 |
| `userId` | 建议使用独立测试 ID |

执行顺序：Health → Initialize profile → Read profile → Ingest conversation turn → HIWM aggregate health → HIWM access login → HIWM chat。Postman 会保存登录接口设置的 HttpOnly Cookie。

## 10. 测试命令

Profile Engine：

```powershell
Set-Location companion-profile-engine
$env:PYTHONPATH="src"
conda run -p .\.conda-env python -m pytest -q
```

HIWM 新增服务测试：

```powershell
Set-Location ..\HIWM
.\.venv\Scripts\python.exe -m pytest -q `
  tests/service/test_companion_service.py `
  tests/service/test_companion_demo.py
```

前端：

```powershell
Set-Location frontend
pnpm run typecheck
pnpm run test
pnpm run build
```

## 11. Zeabur 部署摘要

完整步骤见 `HIWM/docs/DEPLOYMENT_ZEABUR.md`。同一 Project 建议创建：

1. `profile-db`：PostgreSQL。
2. `profile-engine`：画像仓库。
3. `web-chat-api`：HIWM 仓库，只给该服务公开域名。

`web-chat-api` 至少需要以下平台变量：

```text
LLM_API_BASE_URL=https://api.deepseek.com
LLM_API_KEY=<Zeabur Secret>
LLM_MODEL=deepseek-v4-flash
PROFILE_ENGINE_BASE_URL=<profile-engine 服务地址>
PROFILE_ENGINE_API_KEY=<与画像租户映射一致的随机 Key>
PROFILE_ENGINE_TENANT_ID=demo-tenant
DEMO_ACCESS_CODE=<独立随机口令>
DEMO_COOKIE_SECURE=true
COMPANION_DATABASE_URL=sqlite:////data/companion-chat.db
HIWM_COMPANION_ONLY=true
```

给 `web-chat-api` 挂载 `/data` 持久化卷。Profile Engine 生产环境必须连接 PostgreSQL，不能使用容器内 SQLite。

## 12. 最终签字标准

以下项目全部满足后才可标记“可交付”：

- [ ] 两个仓库 commit SHA 已记录，工作区干净。
- [ ] DeepSeek 独立检查返回 `deepseek-v4-flash`。
- [ ] Profile `/health` 的数据库状态为 `ok`。
- [ ] HIWM `/api/health` 的 application/profile_engine/database 均为 `ok`，LLM 为 `configured`。
- [ ] 完整冒烟返回实际模型 `deepseek-v4-flash`。
- [ ] 第一轮画像从 v1 更新为 v2。
- [ ] SSE 回复可见，刷新后消息仍存在。
- [ ] 重置画像需要二次确认并回到 v1。
- [ ] 浏览器和日志中没有任何 Key、Authorization、Cookie 或完整画像泄露。
- [ ] 部署重启后画像和会话仍存在。

未通过真实模型冒烟时，只能标记为“代码与 mock 链路通过”，不能标记为“DeepSeek 已连接”或“线上已验收”。
