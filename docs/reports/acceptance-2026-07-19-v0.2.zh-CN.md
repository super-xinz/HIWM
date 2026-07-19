# HIWM Interaction Engine 0.2.0 验收记录

日期：2026-07-19  
范围：项目自主化、公共契约迁移、机器人语音适配、前后端与文档回归

## 验收结论

本轮改造已达到代码级验收条件：项目身份、版本号、API 命名空间、浏览器存储和部署名称已统一为 HIWM；旧接口与旧本地数据保留兼容路径；机器人接口只发布由已校验预测账本派生的幂等语音命令，不开放任意物理运动控制。

## 自动化结果

| 检查 | 结果 |
| --- | --- |
| 后端非平台脚本测试 | `152 passed` |
| 前端单元测试 | `38 passed` |
| 前端 TypeScript / Vue 类型检查 | 通过 |
| 前端 ESLint | `0 errors`；保留 88 条既有 warning |
| 前端生产构建 | 通过，3634 个模块完成转换 |
| VitePress 文档构建 | 通过 |
| Python 新增模块 Ruff 检查 | 通过 |
| Python compileall / `git diff --check` | 通过 |

后端测试在 Windows 上排除了 `tests/scripts/`：该目录包含面向 macOS/POSIX 的 shell、`/bin/bash` 和 `os.fchmod` 验证，不属于当前平台可执行范围。曾出现的两项异步测试未执行是临时测试环境缺少 `pytest-asyncio`，补齐测试依赖后已全部通过。

## 已覆盖的关键契约

- `/version` 返回 HIWM 名称、slug、项目版本与 API 版本。
- `/api/v1/runtime/*` 和 `/api/v1/sessions/*` 为公共接口；pre-0.2 路由继续作为隐藏兼容别名。
- `hiwm.*` 浏览器存储可从旧键一次性迁移，认证 token 写入前会去除首尾空白。
- 机器人 capability、预测与安全回退映射、游标增量读取、未知游标拒绝和运行时鉴权均有自动化测试。
- 机器人命令带 `session_id:turn_id` 幂等键和来源预测锁摘要，交付语义明确为至少一次。

## 尚需真实环境验收

- 摄像头、麦克风、扬声器以及数字人渲染的设备级体验。
- DashScope 等付费云模型的端到端质量和额度行为。
- Linux/CUDA Docker 镜像与实体机器人适配器；当前 Windows 环境没有 Docker CLI 和机器人硬件。
- 前端主包约 1.47 MB，构建工具提示后续可按页面或能力做代码分包。
- VitePress 1.6.4 的开发依赖链仍报告 3 个暂无稳定版本修复路径的审计项，不影响运行时 Python 服务，但应在文档栈升级时复核。

