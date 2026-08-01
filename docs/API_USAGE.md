# HIWM Companion Chat BFF API

Base URL 与网页同源。若配置 `DEMO_ACCESS_CODE`，先通过登录接口取得 HttpOnly Cookie；浏览器 fetch 自动发送同源 Cookie。

## 从零启动

要求 Python 3.11、Node.js 22、pnpm，以及一个真实可用的 OpenAI-compatible LLM Key。Profile Engine 必须先按其 `docs/API_USAGE.md` 启动在 `http://127.0.0.1:8000`。

Windows PowerShell：

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-zeabur.txt

corepack enable
Set-Location frontend
pnpm install --frozen-lockfile
pnpm run build
Set-Location ..

Copy-Item .env.example .env
```

编辑 `.env`，至少填入：

```dotenv
LLM_API_BASE_URL=https://api.deepseek.com
LLM_API_KEY=<真实且有效的服务端密钥>
LLM_MODEL=deepseek-v4-flash
PROFILE_ENGINE_BASE_URL=http://127.0.0.1:8000
PROFILE_ENGINE_API_KEY=local-development-key
PROFILE_ENGINE_TENANT_ID=demo-tenant
DEMO_ACCESS_CODE=<自行生成的测试访问口令>
DEMO_COOKIE_SECURE=false
COMPANION_DATABASE_URL=sqlite:///./temp/companion-chat.db
HIWM_COMPANION_ONLY=true
PORT=8283
```

`.env` 只用于本地且已被 Git 忽略；不得提交真实密钥。启动轻量文字陪伴服务：

粘贴 Key 后可以先执行一次最小供应商探测；脚本不会输出 Key，只会确认鉴权、模型可见性和一次最小 Chat Completion：

```powershell
.\.venv\Scripts\python.exe scripts\check_deepseek.py
```

成功输出必须为 `DeepSeek connection passed: model=deepseek-v4-flash`。该探测会产生极少量 token 费用。

```powershell
.\.venv\Scripts\python.exe src\companion_demo.py
```

Linux/macOS 使用 `.venv/bin/python src/companion_demo.py`。打开 `http://127.0.0.1:8283`；OpenAPI 位于 `http://127.0.0.1:8283/docs`。

## 必须执行的连接验收

`GET /api/health` 中的 `llm=configured` 只表示 Base URL、Key、模型名均已填写，不代表供应商已经接受请求。真实连通必须完成一次 Chat 调用。保持 Profile Engine 和 HIWM 运行，然后执行：

```powershell
.\scripts\smoke-test.ps1 -BaseUrl "http://127.0.0.1:8283" -AccessCode "<与 DEMO_ACCESS_CODE 相同>"
```

Linux/macOS：

```bash
DEMO_ACCESS_CODE='<与服务端相同的访问口令>' ./scripts/smoke-test.sh http://127.0.0.1:8283
```

唯一合格标准是脚本退出码为 0，并同时出现非空 `reply`、实际 `model=deepseek-v4-flash`、`profile_update=updated`、两条持久化消息和画像版本 v1→v2。HTTP 401/403 表示模型 Key/权限问题，404 通常是 Base URL 或模型名错误，429 是额度/限流，5xx 或超时表示供应商或网络不可用。

## 访问保护

### `GET /api/v1/access/status`

无需登录。返回 `authorized`、`required` 和 `default_user_id`，不返回正确口令。

### `POST /api/v1/access/login`

```json
{"code":"用户输入的口令"}
```

成功设置 `HttpOnly; SameSite=Strict` Cookie；Zeabur 必须 `DEMO_COOKIE_SECURE=true`。同一来源 5 分钟最多 5 次失败。口令不放 URL、不记日志。

### `POST /api/v1/access/logout`

删除服务端 Session 与 Cookie。

## 聚合健康检查

`GET /api/health` 无需登录，`GET /api/v1/companion/health` 需要登录：

```json
{
  "status":"ok",
  "services":{"application":"ok","profile_engine":"ok","llm":"configured","database":"ok"},
  "version":"git-sha",
  "access_protection":"configured"
}
```

## 聊天

`POST /api/v1/companion/chat` 返回一次性 JSON；`POST /api/v1/companion/chat/stream` 使用相同请求体并返回 SSE。

```json
{
  "user_id":"demo-xu",
  "session_id":"session-uuid",
  "turn_id":"turn-uuid",
  "message":"最近做决定时我总是想太久。",
  "profile_enabled":true,
  "frontend_context":{}
}
```

标识只能含字母、数字、下划线、点和连字符。`frontend_context` 当前不会进入模型或幂等指纹，为向后兼容保留。

JSON 响应：

```json
{
  "request_id":"...","turn_id":"...","session_id":"...","user_id":"demo-xu",
  "reply":"...","model":"qwen-plus","profile_used":true,"profile_version_used":1,
  "profile_update":{"status":"updated","profile_version":2,"summary":["SET_PREFERENCE"],"retryable":false},
  "latency_ms":{"profile_read":18.2,"llm":430.1,"profile_update":22.4,"total":471.8},
  "cached":false
}
```

## 画像

- `GET /api/v1/companion/profile/{user_id}`：返回前端白名单视图，不返回完整数据库或全部证据。
- `POST /api/v1/companion/profile/{user_id}/reset`，body `{"confirm":true}`：重置画像并清空 BFF 中该用户测试会话。前端必须先弹确认框。

## 会话

- `GET /api/v1/companion/sessions/{session_id}/messages?limit=100`
- `DELETE /api/v1/companion/sessions/{session_id}`
- `POST /api/v1/companion/sessions/{session_id}/turns/{turn_id}/profile-update:retry`

重试只用于已有回答但画像状态为失败的 turn；不会重新请求 LLM，也不会无限自动重试。

## 错误

| HTTP | 原因 | 处理 |
| ---: | --- | --- |
| 401 | 未登录或 Session 过期 | 重新输入 Demo 口令 |
| 409 | `turn_id` 被不同消息复用 | 新建 turn ID |
| 422 | 请求字段/确认非法 | 修正输入 |
| 429 | 口令错误次数过多 | 五分钟后再试 |
| 502 | LLM 不可用 | 检查模型地址、Key、模型名 |
| 503 | 画像/数据库服务不可用 | 查看聚合健康和 Zeabur 日志 |
