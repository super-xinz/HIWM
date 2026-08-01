# HIWM Companion Chat BFF API

Base URL 与网页同源。若配置 `DEMO_ACCESS_CODE`，先通过登录接口取得 HttpOnly Cookie；浏览器 fetch 自动发送同源 Cookie。

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
  "status":"degraded",
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
