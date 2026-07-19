# HIWM Interaction Demo 功能验收报告

验收日期：2026-07-18（Asia/Shanghai）  
最终复验：2026-07-18 08:01 CST  
基础版本：OpenAvatarChat 0.6.0  
本地入口：<http://127.0.0.1:8283/ui/index.html>

## 总体结论

当前 macOS 本地 Demo 的 P0 软件路径已逐项核对，后端测试、前端离线测试、
TypeScript 类型检查与生产构建均通过。第二轮对照原始 Markdown 发现的信息增益、服务端
安全硬边界和多模态派生证据回放缺口也已补齐。云端证据仅证明 ASR/TTS 两个 SDK 组件的
一次性低成本 smoke；当前加固版 HIWM 和完整 UI/RTC 应用链路没有再次付费做云端 E2E。
之后的测试全部使用本地、离线或合成输入，避免继续消耗账户余额。

这是一套可运行的交互决策 Demo，不应被描述成已经完成真实人群校准或独立训练的
“读心/情绪识别模型”。页面只呈现可观察的人脸点位、头部姿态、音高、能量、停顿等
特征，不推断隐藏情绪、人格、欺骗、心理健康或受保护属性。

## 逐项验收矩阵

| 编号 | 功能 | 验收结果 | 核验内容 |
| --- | --- | --- | --- |
| 1 | 知情同意与撤回 | 通过（代码与 Store） | 未勾选不能继续；撤回会停止 RTC/媒体轨道、清空派生状态并返回同意门。真实设备释放仍列入人工项。 |
| 2 | API 配置状态 | 通过 | 页面只显示白名单内的 ASR、HIWM、TTS 模型及“已加载（未验证）”状态，不显示密钥；该状态不探测 Key 权限、余额或有效性。 |
| 3 | 初始任务背景 | 通过（Store 与浏览器本地） | 保存、创建新 Store 后恢复、清除与清除后无该存储项均有回归；数据只在浏览器本地。 |
| 4 | 摄像头控制 | 通过（软件链路） | 媒体授权 12 秒安全超时与晚到流立即停止有自动测试；开关与真实摄像头释放需在物理设备上最终体验。 |
| 5 | 人脸点阵与姿态 | 已实现（派生帧测试） | MediaPipe 初始化、约 68 个显示点位、yaw/pitch、可见动作和跟踪质量代码已接入；Store 对模拟派生帧的有界化通过，真实 MediaPipe/真人摄像头仍待人工。 |
| 6 | 麦克风与语气特征 | 已实现（派生帧测试） | Web Audio 的波形、相对音高、RMS 能量、发声、停顿、语速与个人基线代码已接入；Store 对模拟 `ProsodyFrame` 的有界化通过，真实麦克风/扬声器待人工。 |
| 7 | ASR 实时/确认文本 | 通过（映射路径） | partial/final 保留且 invalid/cancelled 被过滤；UI 映射为“实时/已确认”。完整 RTC 字幕、内容依据和语速同步仍依赖真实会话人工体验。 |
| 8 | TTS 回声门控 | 通过 | TTS 发声时语气分析归零且不生成语气证据；解除门控后的下一有效派生帧可恢复。 |
| 9 | 内容信号抽取 | 通过（契约支持） | schema 与 UI 支持需求、顾虑、承诺、问题、未知项五类；不宣称每轮一定产生全部五类。 |
| 10 | 工作信念 | 通过（契约支持） | known、working_hypothesis、unknown 三类及证据/不确定性均受 schema 与 UI 支持。 |
| 11 | 三分支预测与选择 | 通过 | 每轮严格 3 条且关键字符串字段不重复；服务端用 `w_goal×目标 + w_info×信息增益 - w_risk×风险 - w_uncertainty×不确定性` 的 v2 评分（权重 1/0.35/1.25/0.6）。信息增益与概率均是未校准模型估计，不是熵或真实准确率；全部高风险时强制 clarify/wait。 |
| 12 | 预测锁定与执行 | 通过 | 预测先 append、flush、`fsync` 到逐记录 SHA-256 可验证账本，再进入输出/TTS。它是本地 append-only 审计文件，不是不可删除的 WORM 存储。 |
| 13 | 下一轮反馈更新 | 通过 | 后端两轮反馈契约以及前端 actual/evaluated/profile 事件序列均有回归，实际回应、匹配程度、解释和变化形成新事件。 |
| 14 | 时间线与回放 | 通过（有界派生回放） | 内容、视觉、语气派生证据、评分、预测锁、反馈和画像变化进入浏览器本地追加、运行时冻结的时间线；刷新恢复、去重和 200 条上限有测试。localStorage 不是防篡改存储；不保存、也不伪称可播放原始媒体。 |
| 15 | 多会话管理 | 通过 | 创建、切换、导出、刷新恢复、删除均有软件路径；删除当前会话后自动选择最新剩余会话。浏览器派生时间线与服务端预测账本是两个不同数据面。 |
| 16 | 非法结构保护 | 通过 | 后端与前端均拒绝 2 条或 4 条动作等非法快照，显示受控错误且既有已接受时间线保持不变。 |
| 16A | 服务端安全硬边界 | 通过（确定性防线） | 中英文规则拒绝隐藏情绪、人格、欺骗、诊断、敏感属性或高影响就业结论；否定警示允许，用户原始自述保留。按 `max_attempts` 决定重试；当前低费用 macOS profile 为 1 次，违规即安全 fallback。 |
| 16B | 严格证据引用 | 通过 | 空、重复、未知引用被拒绝；内容、动作、反馈必须引用当前 final ASR，belief 可只引用合法历史证据；不再静默替换虚构引用。 |
| 17 | 预测账本 HTTP API | 通过 | HTTP TestClient 已覆盖空 GET、验证后读取、DELETE、幂等删除、非法 ID 与禁用状态；该 API 返回服务端预测/fallback 账本，不是浏览器完整派生时间线。 |
| 18 | 健康检查 | 通过 | `/liveness` 与 `/readiness` 现场返回 HTTP 200、`status=ok`。readiness 只证明进程与引擎已初始化，不探测云 Key、余额、RTC 或供应商可用性。 |
| 19 | 自动重启 | 通过 | watchdog 日志记录两次 SIGTERM 退出，分别按 10 秒、20 秒退避拉起并恢复健康；日志未保存退出原因，因此不对两次重启分别做故障/部署归因。 |
| 20 | 隐私与密钥 | 通过（受测范围） | setup/start 使用 `umask 077` 且对新建/既有 `.env` 强制 `0600`；watchdog、云结果、attempt locks 均为 owner-only。日志 canary、配置脱敏和排除受保护 `.env` 的扫描通过。 |
| 21 | 云端 ASR | 直接 SDK 云 smoke 通过 | `fun-asr-realtime` 对 2.135 秒合成语音返回非空识别文本，约 526 ms；不是完整 UI/RTC E2E。 |
| 22 | 云端 TTS | 直接 SDK 云 smoke 通过 | `cosyvoice-v3-flash` 返回 125,760 字节音频，约 810 ms；不是完整 UI/RTC E2E。 |
| 23 | 云端 HIWM | 当前未通过；离线通过 | 唯一持久聚合证据为 `status=failed / RuntimeError`。随后完成本地化动作规范化、信息增益、严格引用和安全硬校验并通过离线回归；为保护余额未再次付费，不宣称当前版云闭环通过。 |
| 24 | 一次性费用保护 | 通过 | full/retry/adapter/envelope 四个显式模式分别在读取 Key 前以 `O_CREAT|O_EXCL` 创建永久 one-shot lock；同模式重复、并发或调用后崩溃均不会再次请求。四个历史锁已补建为 `0600`，目录 `0700`。 |

## 自动化验证结果

```text
Python / pytest:                131 passed, 1 deprecation warning
Frontend Node tests:            22 passed
Frontend Web typecheck:          passed
Frontend Node typecheck:         passed
Targeted ESLint:                 passed
Full ESLint:                     0 errors, 91 upstream-style warnings
Vite production build:           passed
Python compileall:               passed
Shell syntax / YAML parse:       passed
git diff --check:                passed
```

唯一 Python 警告来自上游 `websockets.legacy` 弃用提示。Vite 另有单个大于 500 kB 的
bundle 提示；它们都不影响当前功能运行。完整 ESLint 的警告主要是原项目既有的返回类型、
`any` 和 Vue 默认属性风格问题，没有错误。

## 连续运行与 08:00 终检

- Watchdog JSON 日志覆盖北京时间约 01:52:27–08:01:10，共 374 条合法事件；其中
  `health_ok` 364 次，`health_failed` 与 `watchdog_error` 均为 0。
- 非健康事件只有一次受控 supervisor 替换，以及两次 SIGTERM 子进程退出；后两次分别按
  10 秒、20 秒退避拉起并恢复健康。日志没有保存退出原因，因此这里只陈述可验证的时间序列。
- 独立监控完成 74 次 liveness/readiness/进程检查和 32 次页面/bundle/权限检查，失败均为 0；
  最终 supervisor PID 14653、服务 PID 48445。
- 08:01 现场 `/liveness`、`/readiness` 均返回 `status=ok`；页面和
  `assets/main.BlPdmSoD.js` 均为 HTTP 200，HTML 引用与构建产物一致。
- 最终浏览器 DOM 验证同意门默认禁用、三项模型脱敏状态、行动分支、三路证据汇聚、反馈
  闭环和派生事件回放均存在；页面没有真实 Key、合成注入或验收控制项。
- `.env`、watchdog、云结果和四个 attempt lock 最终均为 `0600`，锁目录为 `0700`；
  排除受保护 `.env` 后，仓库与运行日志的真实 Key 前缀扫描为 0 命中。
- 监控与最终复验没有读取 `.env` 内容，也没有发起新的云 API 调用。

08:01 再次执行的全量结果仍为 Python 131/131、Frontend Node 22/22，两套 TypeScript
检查通过；最终生产构建转换 3,641 个模块并成功输出。

## 验收中修复的问题

1. 摄像头或麦克风授权一直没有返回时，开始按钮会卡死：加入 12 秒安全超时、晚到媒体流
   立即停止，并加入离线回归测试。
2. 删除当前会话且仍有其他会话时，页面短暂进入空白状态：现在会自动选择最新剩余会话，
   删除非当前会话则保持现有页面不变。
3. 被取消的聊天记录被误算成确认内容依据：现在同时过滤 `invalid` 与 `cancelled` 记录。
4. 云验收结果文件权限过宽：写入改为私有 `0600` 权限并加入权限测试。
5. 前端 Node 类型检查的未使用参数/import 错误：已清理，Node 与 Web 两套检查均通过。
6. P0 自动选择缺少显式信息增益：加入 `[0,1]` 信息增益、0.35 权重、v2 可审计评分和旧 v1
   ledger 哈希兼容。
7. 回放没有视觉/语气证据：现在冻结内容、视觉、语气的有界派生快照和评分分量；原始媒体
   仍不落盘。
8. 模型越界结论与虚构 evidence ID 主要依赖提示词：加入服务端中英文硬校验和严格引用，
   违规响应整体拒绝并进入安全 fallback。
9. 页面规范缺少字幕重点和动态对比：加入纯文本可追溯短语高亮、三分支逐级展开/未选中
   置灰、真实计数证据汇聚提示，并支持 `prefers-reduced-motion`。
10. 云 smoke 只有调用完成后的 marker，存在并发或调用后崩溃重复计费窗口：现在每种显式
    模式都在读取 Key 前原子、持久化地领取永久 one-shot lock，并补并发和崩溃测试。
11. `.env` 首次复制或既有文件可能继承宽权限：setup/start 现在使用 `umask 077` 并无条件
    收紧到 `0600`，隔离运行测试覆盖新建与既有 `0644` 两种情况。
12. 反馈事件、非法 2/4 分支、导出/刷新恢复以及 HTTP GET/空时间线缺专门回归：现已补齐。

## 明确边界与待人工项

- 浏览器自动化环境没有真实硬件授权，因此真实摄像头、真实麦克风、真人面部和实际扬声器
  仍需在使用者电脑上做最后一次人工体验；目前自动化覆盖的是媒体超时以及有界派生帧，
  不把它描述成真实 MediaPipe/AudioContext 硬件 E2E。
- MediaPipe 面部模型默认从配置的 CDN 加载；未把模型资产本地化时，首次点阵跟踪需要网络。
- 尚未完成受试者招募、标注一致性、held-out 校准、ECE/Brier、跨设备/光照/口音、模态
  消融与长期效果研究。这些是研究验证，不是本地软件测试可以替代的结论。
- 实体机器人、远程视频和独立数字人驱动属于设计文档中的可选扩展，不在当前 macOS Demo
  的完成范围内。
- 当前推演器使用阿里云 Model Studio API 服务，并非可以下载到本地的独立 HIWM 权重；
  当前云 HIWM 验收也未通过。真正可发布的专用 HIWM 仍需要合规数据、训练与独立评测。

## 本地复验

```bash
cd "<repository-root>"
.venv/bin/python -m pytest -q

cd frontend
node_modules/.bin/vue-tsc --noEmit -p tsconfig.web.json --composite false
node_modules/.bin/tsc --noEmit -p tsconfig.node.json --composite false
node --experimental-strip-types --test tests/*.test.ts
node_modules/.bin/eslint . --ext .js,.jsx,.cjs,.mjs,.ts,.tsx,.cts,.mts,.vue
node_modules/.bin/vite build

cd "<repository-root>"
.venv/bin/ruff check scripts tests src/handlers/hiwm
.venv/bin/python -m compileall -q src scripts tests
bash -n scripts/setup_macos.sh
bash -n scripts/start_macos.sh
git diff --check
```

启动及配置方式见 `docs/guides/macos-setup.md` 和
`docs/guides/hiwm-runtime.md`。不要提交 `.env`，也不要把真实
密钥复制到截图、日志或 issue 中。
