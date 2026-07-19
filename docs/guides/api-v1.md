# HIWM API v1

`0.2.0` 起，新代码使用 HIWM 自有的 `/api/v1` 命名空间。旧 `/openavatarchat/*` 读取与控制路径暂时作为兼容别名保留，客户端不再主动调用它们。

## 身份与健康

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/version` | 项目名称、slug、项目版本和 API 版本 |
| GET | `/liveness` | 进程存活 |
| GET | `/readiness` | Chat Engine 已完成初始化；不代表云 Key、余额或媒体设备可用 |

## 运行时与会话

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/v1/runtime/config` | 严格白名单、无密钥的模型和能力配置 |
| POST | `/api/v1/runtime/api-key` | 将 DashScope Key 写入当前服务进程内存；不落盘、不返回 |
| GET | `/api/v1/sessions/{session_id}/timeline` | 读取并校验最多 200 条服务端预测/安全回退记录 |
| DELETE | `/api/v1/sessions/{session_id}` | 删除该会话的服务端预测账本；幂等 |

服务绑定非回环地址时，控制类接口需要 `Authorization: Bearer <HIWM_RUNTIME_CONTROL_TOKEN>`。浏览器只保存运行时控制 Token；DashScope Key 不进入浏览器存储。

## 机器人适配

### 能力发现

`GET /api/v1/robot/capabilities`

当前仅支持 `speak`，不支持移动、抓取或任意设备命令。返回值明确说明账本顺序、至少一次轮询语义、去重方法以及原始媒体不会暴露。

### 拉取已锁定行动

`GET /api/v1/robot/sessions/{session_id}/commands`

可选查询参数 `after_turn_id`。机器人应保存上次成功消费的 `turn_id`，下次只取更新命令；未知或已经离开 200 条有界窗口的游标会返回 `400`，避免调用方误以为没有新命令。

示例响应：

```json
{
  "schema_version": "1.0",
  "session_id": "session-123",
  "delivery": "at_least_once",
  "next_cursor": "turn-456",
  "commands": [
    {
      "schema_version": "1.0",
      "cursor": "turn-456",
      "idempotency_key": "session-123:turn-456",
      "session_id": "session-123",
      "turn_id": "turn-456",
      "issued_at": 1784476800.0,
      "command": {
        "type": "speak",
        "strategy": "clarify",
        "text": "可以再说明一下你的时间约束吗？",
        "fallback": false
      },
      "source_lock": {
        "algorithm": "sha256",
        "sha256": "<64 位十六进制摘要>",
        "prediction_id": "turn-456",
        "action_id": "clarify-a"
      }
    }
  ]
}
```

命令只会从已通过 SHA-256 校验的服务端账本生成。接口是 at-least-once 轮询，不保证 exactly-once；执行器必须按 `idempotency_key` 去重。它也不代表机器人已经成功播报，后续需要独立的设备回执协议。

## 兼容迁移

| 旧标识 | 新标识 | 策略 |
| --- | --- | --- |
| `/openavatarchat/initconfig` | `/api/v1/runtime/config` | 服务端保留兼容别名 |
| `/openavatarchat/runtime-api-key` | `/api/v1/runtime/api-key` | 服务端保留兼容别名 |
| `/openavatarchat/hiwm/sessions/*` | `/api/v1/sessions/*` | 服务端保留兼容别名 |
| `auth_openavatarchat` | `hiwm.runtime-control.auth.v1` | 浏览器首次读取时迁移并删除旧键 |
| `openavatarchat.hiwm.timeline.v1` | `hiwm.timeline.v1` | 浏览器首次读取时迁移并删除旧键 |
| `openavatarchat.hiwm.initial-profile.v1` | `hiwm.initial-profile.v1` | 浏览器首次读取时迁移并删除旧键 |

兼容别名只用于平滑升级，不应出现在新集成中。删除日期应在未来版本的 Changelog 中另行公告。
