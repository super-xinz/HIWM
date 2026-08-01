# 双 API Chatbot 集成说明

## 职责与数据流

Vue 浏览器端只持有 `user_id`、`session_id`、`turn_id`、消息和 UI 状态。它不会获得 `LLM_API_KEY`、`PROFILE_ENGINE_API_KEY` 或正确访问口令。

```text
Vue CompanionDashboard
  └─ POST /api/v1/companion/chat/stream (HttpOnly Demo Session)
       └─ ChatOrchestrator
            ├─ ProfileEngineClient → companion-profile-engine
            ├─ Prompt Composer     → 有限、分区、不可执行的画像上下文
            ├─ LLMClient           → OpenAI-compatible 原模型 API
            └─ SessionStore        → SQLite 会话与 turn 去重
```

## 每轮时序

1. 前端生成唯一 `turn_id`，提交最大 4000 字消息。
2. Session Store 查询 `(session_id, turn_id)`；相同请求直接返回缓存，不同消息复用同一 ID 返回 409。
3. 开启画像增强时，Adapter 读取 `/v1/profiles/{user_id}`；404 则调用 `/v1/profiles:init`。
4. Composer 仅选择 portrait、MBTI 连续维度、已确认九型、当前状态、互动偏好、最近 10 条记忆和版本，受 `PROFILE_CONTEXT_MAX_CHARS` 限制。
5. 画像内容包在 `<profile_context>` 系统边界中，被声明为参考数据而非指令；用户消息始终作为独立 `user` role。
6. LLM Adapter 通过服务端 `AsyncOpenAI` 请求 `LLM_API_BASE_URL`，SSE 逐段返回 `meta`、`delta` 和 `final`。
7. 完整回复生成后，Adapter 把用户消息、最近最多 12 条对话、版本、session/turn 映射到真实 `messages:ingest` Schema。
8. 画像更新结果和两条消息一起落入 SQLite；下一轮重新读取画像。

画像引擎真实 Schema 不接收 `assistant_message` 字段，因此回答通过 `context.recent_turns` 进入后续上下文，而当前用户文本放入 `text`。这是适配而非修改画像核心。

## SSE 事件

```text
data: {"type":"meta","request_id":"...","profile_used":true}

data: {"type":"delta","content":"你好"}

data: {"type":"final","response":{...ChatResponse}}
```

Nginx/代理场景需关闭 SSE 缓冲；同源 Zeabur 部署无需浏览器 CORS。`X-Accel-Buffering: no` 与 `Cache-Control: no-cache` 已设置。

## 失败降级

| 故障 | 行为 |
| --- | --- |
| 画像未配置/读取失败 | 继续调用原模型；`profile_used=false`，状态面板标记降级 |
| 画像为空/404 | 自动初始化一份无敏感推断授权的空白画像 |
| LLM 未配置/失败 | HTTP 502 或 SSE `error`；不生成虚假回复 |
| 画像写回失败 | 已生成回答照常显示/保存，右栏给出错误和“重试画像更新” |
| 版本冲突 | 写回失败可重试；重试仍受画像幂等与版本保护 |
| 流中断 | 前端保留已显示分片并标记中断；用户可重新发送新 turn |
| 数据库失败 | 聚合健康检查 `database=unavailable`，不会返回密钥/堆栈 |

## 会话数据

SQLite 保存 `session_id`、`user_id`、`turn_id`、role、content、时间、model、profile_version、request_id；不保存 API Key、访问口令、Authorization 或 Cookie。`companion_turns` 的联合主键承担幂等控制。

## API 路由

完整请求体见 `docs/API_USAGE.md`。前端使用：

- `POST /api/v1/companion/chat/stream`
- `GET /api/v1/companion/profile/{user_id}`
- `GET /api/v1/companion/sessions/{session_id}/messages`
- `DELETE /api/v1/companion/sessions/{session_id}`
- `POST /api/v1/companion/profile/{user_id}/reset`
- `POST /api/v1/companion/sessions/{session_id}/turns/{turn_id}/profile-update:retry`
- `GET /api/v1/companion/health`
