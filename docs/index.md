---
layout: home
hero:
  name: HIWM Interaction Engine
  text: 人际互动世界模型的交互决策演示平台
  tagline: 经同意获取有限证据，生成三条候选动作，先锁定再执行，并用真实反馈更新工作信念
  actions:
    - theme: brand
      text: macOS 快速开始
      link: /guides/macos-setup
    - theme: alt
      text: 查看运行架构
      link: /guides/hiwm-runtime
    - theme: alt
      text: API v1
      link: /guides/api-v1
    - theme: alt
      text: 研究定义
      link: /research/hiwm-definition.zh-CN
features:
  - title: Consent first
    details: 未明确同意不进入会话；用户可以关闭媒体、撤回同意并结束会话。
  - title: Evidence bounded
    details: 只保存有界文本和数值派生事件，默认不把原始音频、视频、图片或完整人脸点位写入回放。
  - title: Prediction before action
    details: 三条候选动作经风险与不确定性规划，选中预测先写入可校验账本，再进入语音执行。
  - title: Honest research boundary
    details: 这是未校准的交互决策 Demo，不宣称读心、隐藏情绪识别、人格判断或真实人群验证。
---

## 项目边界

当前实现使用通用云端多模态模型完成结构化推演，并不是独立训练的 HIWM 权重。真实设备体验、真实人群校准、长期效果和跨设备泛化仍属于后续研究工作。

项目基于 OpenAvatarChat `0.6.0` 和 OpenAvatarChat-WebUI 开发，但不是上游官方发行版。完整来源与许可证信息见仓库根目录的 `UPSTREAM.md`、`THIRD_PARTY_NOTICES.md` 和 `LICENSE`。
