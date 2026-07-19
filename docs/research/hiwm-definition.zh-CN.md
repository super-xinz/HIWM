# Human Interaction World Model（HIWM）正式定义与研究依据

> 版本：1.0  
> 日期：2026-07-15  
> 用途：产品定义、融资材料、B 端沟通、技术路线与 Demo 口径统一

## 0. 结论摘要

不建议继续单独使用 **Human World Model / 人类世界模型**。

推荐正式类别名：

> **Human Interaction World Model（HIWM）｜人际互动世界模型**

严格技术副标题：

> **A person-specific, multimodal, action-conditioned interaction dynamics model.**  
> **面向具体互动对象的、多模态、行动条件化交互动力学模型。**

产品价值名称：

> **Interaction Decision Simulator｜互动决策模拟器**

一句话定义：

> 人际互动世界模型是一类行动条件化的概率动力学模型。它从与具体对象的连续语言、语音、可观察行为和情境历史中，维护对任务相关互动状态的校准信念；预测不同候选沟通行动将如何改变后续可观察反应、互动状态与任务结果；并依据真实反馈持续更新，以支持行动前推演和模型式决策。

最直观的类比：

> **Physical World Model 推演“这样动，物理世界会怎样变化”；HIWM 推演“此刻这样说或这样做，这段互动可能怎样变化”。**

最适合融资沟通的表达：

> **今天的生成式 AI 擅长回答“下一句话怎么说”；HIWM 进一步回答：“这句话说出去以后，眼前这个人和这段互动可能发生什么变化？”**

---

## 1. 为什么不使用 Human World Model

“Human World Model”至少存在四种不同理解：

1. 人类自身拥有的内部世界认知；
2. 对完整人格、意识或“数字分身”的模拟；
3. 对人体动作、姿态或人类行为的生成模型；
4. 使用人类视频训练出来的机器人世界模型。

例如，RSS 2023 的 [Structured World Models from Human Videos](https://arxiv.org/abs/2308.10901) 使用了 `human-world-model` 作为项目地址，但它研究的是从人类操作视频中学习机器人操控动力学，并不是人际互动建模。

因此，本项目不应宣称建立“一个人的完整模型”。真正的建模单元是：

> **具体的人 × 具体的互动对象 × 具体任务 × 具体情境 × 具体时间窗口。**

学术上，HIWM 可以被归入正在形成的 **Social World Model** 方向；产品上，使用 Human Interaction World Model 能更准确地限定对象和价值。

---

## 2. Physical World Model 的共同内核

Physical World Model 并没有一个全球统一的产品标准。World Labs 仍将 “world model” 称为 AI 领域最重要、也最被过度使用的术语之一。但在 model-based reinforcement learning、机器人和 embodied AI 中，已经形成相对稳定的功能共识。

一个有决策价值的 Physical World Model 通常包含：

1. **状态估计**：从不完整的传感器观察中形成当前世界状态的内部表示；
2. **动力学建模**：学习世界随时间如何自然演化；
3. **行动条件化预测**：预测采取不同动作后世界如何变化；
4. **未来推演**：在真实行动前展开一个或多个可能未来；
5. **规划支持**：由 planner 使用预测结果选择行动；
6. **现实校准**：新观察到来后修正状态和动力学。

最小形式可以写成：

\[
b_t(s)=P(s_t\mid o_{\leq t},a_{<t})
\]

\[
P(s_{t+1},o_{t+1},y_{t+1}\mid s_t,a_t)
\]

其中：

- \(o_t\)：摄像头、雷达、触觉等观察；
- \(s_t\)：位置、速度、接触关系等任务相关潜在状态；
- \(a_t\)：移动、转向、抓取等动作；
- \(y_t\)：任务结果、风险或代价；
- \(b_t\)：部分可观测条件下，对当前状态的概率信念。

它的直接价值不是“生成一段逼真的视频”，而是：

> **让系统在采取高成本、危险或不可逆动作前，先在内部模型中比较不同动作的可能后果。**

这套共同结构可见于 [World Models](https://arxiv.org/abs/1803.10122)、[Yann LeCun 的 AMI 架构](https://openreview.net/pdf?id=BZ5a1r-kVsf)、[Meta V-JEPA 2](https://ai.meta.com/blog/v-jepa-2-world-model-benchmarks/)、[Google DeepMind Genie 3](https://deepmind.google/blog/genie-3-a-new-frontier-for-world-models/)、[NVIDIA Cosmos](https://research.nvidia.com/publication/2025-01_cosmos-world-foundation-model-platform-physical-ai) 和 [World Labs 的功能分类](https://www.worldlabs.ai/blog/taxonomy-of-world-models) 中。

---

## 3. HIWM 的正式定义

### 3.1 建模对象

HIWM 不建模一个人的“本质”，而建模特定情境中的互动动力学：

- 当前参与者是谁；
- 双方各自扮演什么角色；
- 当前共同任务是什么；
- 对方已经看到、听到和理解了什么；
- 当前存在哪些已知约束与未知变量；
- 我方采取不同沟通行动后，互动更可能如何发展。

### 3.2 形式化描述

设：

- \(c\)：业务情境、双方角色、目标和约束；
- \(u\)：当前互动对象及其获授权使用的历史；
- \(o_t\)：第 \(t\) 时刻的语言、语音、轮次、可观察行为和业务反馈；
- \(a_t\)：提问、解释、举证、报价、等待、转人工等沟通行动；
- \(z_t\)：任务相关、不可直接观察的互动状态；
- \(r_t\)：双方关系、共同认知和信任等关系状态；
- \(y\)：后续可观察反应或业务结果。

模型维护的不是唯一心理结论，而是状态信念：

\[
b_t(z,r)=P(z_t,r_t\mid c,u,o_{\leq t},a_{<t})
\]

对候选行动进行未来推演：

\[
P(o_{t+1:t+H},z_{t+1:t+H},r_{t+1:t+H},y
\mid b_t,a_{t:t+H-1},c,u)
\]

规划器在 HIWM 之外使用这些预测：

\[
a_t^*=\arg\max_a
\left[
\mathbb E(U(y)\mid b_t,a)-\lambda Risk(a)
\right]
\]

这一区分非常重要：

> **HIWM 负责预测行动后果；Planner 负责依据目标、风险和约束选择行动；LLM 或机器人负责执行和表达。**

### 3.3 状态空间

状态只应包含与当前任务有关、能够被后续证据检验的变量。

以企业销售咨询为例：

- 需求与产品适配度；
- 对方案价值的理解程度；
- 当前优先级和时间紧迫度；
- 预算约束及其不确定性；
- 实施、迁移和组织协作风险；
- 决策权和利益相关方结构；
- 共同认知与信任稳定度；
- 下一步行动准备度；
- 仍然未知、需要主动澄清的信息。

不应将以下内容作为未经验证的事实输出：

- “真实情绪”；
- 人格本质；
- 是否撒谎；
- 忠诚度；
- 心理疾病；
- 是否“适合被裁”；
- 基于受保护属性的判断。

---

## 4. Physical World Model 与 HIWM 的严格映射

| Physical World Model | Human Interaction World Model |
|---|---|
| 摄像头、雷达、触觉观察 | 语言、语音韵律、轮次、可观察行为和业务上下文 |
| 物体位置、速度、接触状态 | 需求、理解、约束、共同认知、决策阶段和关系状态 |
| 转向、移动、抓取 | 提问、解释、举证、报价、等待、转人工 |
| 物理状态转移 | 人及互动关系对沟通行动产生的概率响应 |
| 推演候选运动轨迹 | 推演不同沟通策略下的反应与结果分布 |
| 规划与控制 | 选择下一步互动策略 |
| 用传感器反馈校正状态 | 用真实回答、行为和业务结果校正状态 |
| Physical foresight | Interaction foresight |

二者也存在本质差异：

- 人具有目标、策略和自主性，会根据对方的行为改变自己的行为；
- 人的互动动力学比物理规律更情境化、更非平稳；
- 人会观察并反向建模系统，具有反身性；
- “互动状态”是可检验假设，不是可以直接测量的客观心理真相；
- 沟通目标必须受到用户自主性、隐私、公平和合规约束。

因此，HIWM 必须比很多物理模型更重视概率、不确定性、放弃判断和人工覆盖。

---

## 5. 与现有模型和产品的边界

| 类别 | 主要回答的问题 | 与 HIWM 的区别 |
|---|---|---|
| LLM | 下一段文本或回答是什么 | 不天然维护可校准的个体互动状态，也不保证学习行动条件化状态转移 |
| 普通 Chatbot / Copilot | 当前应该回复什么 | 通常没有“先模拟多个行动后果再选择”的必要结构 |
| 情绪识别 | 当前输入像哪类情绪 | 是描述性分类，没有动力学、未来轨迹和规划 |
| Theory of Mind | 对方可能相信、想要或意图什么 | 偏潜在状态推断；HIWM 还必须预测行动如何改变未来 |
| 用户模拟器 / Generative Agent | 某个画像的人可能说什么或做什么 | 多追求可信度或 persona 相似度；HIWM 要求概率校准、行动分支和决策效用 |
| 推荐系统 | 哪个固定选项更可能被点击或购买 | 通常是固定动作空间和单步结果预测，可视为很窄的特例 |
| CRM 评分 | 当前客户转化概率是多少 | 通常不回答“分别采取 A/B/C 后会怎样” |
| Digital Twin | 现实实体的同步数字表示 | 强调表示与同步，未必包含行动条件化动力学 |
| Agent Policy | 现在应该采取什么动作 | Policy 预测动作；HIWM 预测采取动作后的未来 |
| 数字人 / 机器人 | 以什么形态与人交互 | 是输入输出载体，不是互动决策智能本身 |

### HIWM 与 LLM 的准确关系

不应简单宣称“LLM 不理解人”。LLM 可以承担：

- 语言和上下文编码；
- 人口级社会知识先验；
- 候选沟通动作生成；
- 选定策略的自然语言表达；
- 结构化解释和总结。

但普通 LLM 的生成目标不保证：

- 对具体真人的反应分布具有校准性；
- 持续维护显式个体状态；
- 比较不同候选行动造成的状态转移；
- 使用真实反馈修正互动动力学；
- 在真实业务结果上优于直接生成。

因此，准确的表述是：

> **LLM 生成一个可能的回答；HIWM 预测多个候选行动可能造成的后果，并对预测承担可验证责任。**

---

## 6. 研究基础与当前成熟度

截至 2026-07-15，相关研究部件已经出现，但尚未形成成熟统一的产业类别。

### 6.1 Machine Theory of Mind 与逆向规划

- MIT 的 Bayesian inverse planning 将目标和意图推断形式化为“反演一个人的规划过程”；
- DeepMind 的 [Machine Theory of Mind / ToMnet](https://proceedings.mlr.press/v80/rabinowitz18a.html) 使用群体先验，并根据少量行为观察快速适配到具体 Agent；
- 这条路线奠定了“从可观察行为维护潜在状态信念”的计算基础，但多数验证仍位于简化环境。

### 6.2 人类行为与认知基础模型

[Centaur](https://www.nature.com/articles/s41586-025-09215-4) 基于 160 个心理实验、超过 6 万名参与者和 1,000 万次选择训练，证明跨任务预测人类行为具有可行性。但其数据主要来自受控心理实验，不是实时、多模态、个体化互动。

### 6.3 Generative Agents 与个体模拟

- [Generative Agents](https://arxiv.org/abs/2304.03442) 展示了基于记忆、反思和规划生成可信人类式行为；
- [Generative Agent Simulations of 1,000 People](https://arxiv.org/abs/2411.10109) 使用深度访谈模拟 1,052 名真实参与者的调查和实验回答；
- 这些工作证明了个体模拟的价值，但“像某个人”不等于能够校准地预测不同干预的结果。

### 6.4 Social World Models

[Social World Models](https://arxiv.org/abs/2509.00559) 将社会互动表示为 state、observation、action 和 mental state，并让模型预测下一社会状态与其他 Agent 的行动。这是 HIWM 的重要学术上位概念。

### 6.5 最接近 HIWM 的直接研究

- [HumanLM](https://arxiv.org/abs/2603.03303) 表明，先对齐潜在用户状态再生成回复，优于只模仿表面语言；
- [PUMA](https://arxiv.org/abs/2605.24647) 将多轮个性化对话形式化为部分可观测决策问题，维护隐藏用户状态、学习行动条件化状态转移，并据此选择对话行动；
- [See, Infer, Intervene / PIWM](https://arxiv.org/abs/2606.03371) 直接研究零售场景中的客户状态和干预动作。该工作同时显示，从视频可靠落到用户状态仍是当前部署瓶颈。

因此不能把创新点放在“第一次提出隐藏用户状态或行动条件化对话”上。更可守住的差异是：

> **把这些能力整合成一个在真人、实时、多模态数据上可校准、可在线更新、能在真实业务干预中改善决策结果的闭环系统。**

---

## 7. 什么系统才有资格称为 HIWM

建议把以下条件设为产品和研究门槛：

1. **时序状态**：维护随互动演化的状态，而不是分析孤立句子或单帧画面；
2. **个体与情境落地**：依据当前对象的实际互动历史更新，而不是只有通用画像；
3. **行动条件化动力学**：显式预测候选行动 A/B/C 对未来产生的不同影响；
4. **多步推演**：至少预测下一反应、状态变化和阶段性任务结果；
5. **概率与不确定性**：输出分布、区间或可校准概率，而不是唯一心理结论；
6. **反馈闭环**：实际反应到来后更新状态、动力学和下一步策略；
7. **可用于规划**：预测接口能够比较至少两个真实可执行行动；
8. **真实世界验证**：在留出的真人互动或真实干预数据上检验，而不是只让另一个 LLM 判断是否合理；
9. **多模态增量证明**：如果声称多模态，音频或视频必须在留出数据上提供超越纯文本的增量价值；
10. **安全退出**：不确定性过高或风险过大时能够请求澄清、转人工或拒绝建议。

缺少其中核心项时，产品应称为多模态互动 Copilot、状态分析器或用户模拟器，而不是完整世界模型。

---

## 8. 因果与反事实边界

行动条件化预测不自动等于严格因果反事实。

如果只有历史对话日志，模型学习到的是：

> 在历史数据分布中，采取行动 A 后通常观察到什么。

它不自动证明：

> 在同一时刻对同一个人改用行动 B，一定会得到更好结果。

要严谨使用“因果反事实”，需要至少具备一种条件：

- 随机化干预或 A/B 实验；
- 自然实验或可靠的识别假设；
- 经过验证的离线策略评估；
- 可重复的受控互动实验。

在此之前，对外建议使用：

- 行动条件化预测；
- 候选行动推演；
- 情景分支模拟；
- 预测性互动规划。

---

## 9. 可证伪的验证体系

评估数据单元应是完整互动轨迹：

\[
E=(context,user,\{observation_t,action_t,outcome_t\}_{t=1}^{T})
\]

训练集和测试集至少应按人、时间和场景拆分，防止同一对象信息泄漏。

### 9.1 个体化价值

比较：

- 通用模型；
- 只有人口画像的模型；
- LLM + 历史记忆；
- HIWM 在线个体状态模型。

指标：下一反应 NLL、Brier Score、任务结果预测误差、随观察轮数增加的学习曲线。

### 9.2 多模态增量

比较：

- 仅转录文本；
- 文本 + 语音；
- 文本 + 语音 + 可观察视频行为。

必须进行模态消融、缺失模态和跨设备测试。

### 9.3 行动条件化预测

在相近状态中随机或准随机分配不同沟通动作，检验模型能否正确排列这些动作的实际结果。

指标可包括：Action Ranking Accuracy、Kendall’s \(\tau\)、uplift/Qini、离线策略评估与真实 A/B 结果的一致性。

### 9.4 概率校准

指标可包括：Brier Score、Negative Log-Likelihood、Expected Calibration Error、预测区间覆盖率和最差组校准。

### 9.5 闭环更新

测量：

- 新反馈到来后状态误差是否下降；
- 不确定性是否合理收缩；
- 错误判断能否被后续证据纠正；
- 分布变化后需要多少轮恢复校准。

### 9.6 最终决策价值

必须比较：

- HIWM 规划策略；
- 强 LLM 直接生成；
- 专家规则；
- 人类专家。

最终验收是：

> **如果行动排序不能带来比强 LLM 或专家规则更好的真实结果，系统只是一个更复杂的界面，而不是有决策价值的世界模型。**

---

## 10. 科学、安全与合规边界

### 10.1 不把可观察线索等同于真实心理

语言、语音、停顿、注视和可观察面部动作只能作为情境相关证据。系统应输出：

- 状态假设；
- 概率和不确定性；
- 支持证据与反证据；
- 仍需确认的信息。

界面应使用“互动状态估计”“可观察行为证据”，避免“心理诊断”“真实情绪”“读心”等表述。

### 10.2 HR 场景

欧盟《AI Act》已禁止在工作场所基于生物特征推断情绪，招聘、员工管理、晋升和终止劳动关系相关 AI 也属于高风险用途。正式产品需要结合部署地区进行专项法律评估。

因此 HR 场景应优先使用：

- 明确对话内容；
- 可验证工作证据；
- 岗位要求与能力证据；
- 内部转岗和沟通辅助；
- 人工最终决策与审计。

不应以“AI 判断该裁谁”作为卖点。

### 10.3 使用原则

- 明示正在使用 AI；
- 获得适用场景所需的知情和授权；
- 限制敏感属性和未经授权历史的使用；
- 支持人工覆盖、放弃建议和转人工；
- 保存模型版本、证据、预测、执行动作和真实结果的审计记录；
- 不以提高转化为唯一目标，同时优化用户自主性、长期价值和风险。

正式法规来源：[Regulation (EU) 2024/1689 — Artificial Intelligence Act](https://eur-lex.europa.eu/legal-content/en/TXT/?uri=CELEX%3A32024R1689)。

---

## 11. 对外统一表达

### 11.1 标准定义版

> Physical World Model 学习物理环境在行动作用下如何演化，使机器人能够在真正行动前推演未来。Human Interaction World Model 将同一范式应用于人际互动：它从与具体对象的连续语言、语音、可观察行为和情境信息中维护一个带有不确定性的互动状态，模拟不同沟通行动可能带来的反应与结果，并依据真实反馈持续修正。它不是读取一个人的内心，而是为高成本互动建立一个可校准、可验证的决策模拟器。

### 11.2 融资版

> 今天的 LLM 擅长生成一句看起来正确的话，但不真正对“这句话会让眼前这段互动发生什么变化”负责。我们构建的是人际互动世界模型：让 AI 在开口之前，先模拟不同沟通动作对具体对象可能产生的后果，再根据真实反馈更新判断。

### 11.3 B 端产品版

> HIWM 是位于企业沟通工具与大模型之间的互动决策层。它不只总结过去或生成话术，而是维护当前互动状态、比较不同下一步行动的结果，并用真实业务反馈持续校准，帮助销售、客户成功和服务团队减少高成本试错。

### 11.4 一句话价值

> **把生成式 AI 从“生成下一句话”，升级为“预测这句话会对这段互动产生什么后果”。**

---

## 12. 主要参考资料

### Physical World Model

- Ha, D. & Schmidhuber, J. [World Models](https://arxiv.org/abs/1803.10122), 2018.
- LeCun, Y. [A Path Towards Autonomous Machine Intelligence](https://openreview.net/pdf?id=BZ5a1r-kVsf), 2022.
- Meta AI. [Introducing V-JEPA 2](https://ai.meta.com/blog/v-jepa-2-world-model-benchmarks/), 2025.
- Google DeepMind. [Genie 3: A New Frontier for World Models](https://deepmind.google/blog/genie-3-a-new-frontier-for-world-models/), 2025.
- NVIDIA. [Cosmos World Foundation Model Platform for Physical AI](https://research.nvidia.com/publication/2025-01_cosmos-world-foundation-model-platform-physical-ai), 2025.
- World Labs. [A Functional Taxonomy of World Models](https://www.worldlabs.ai/blog/taxonomy-of-world-models), 2026.

### Human、User 与 Social Modeling

- Rabinowitz et al. [Machine Theory of Mind](https://proceedings.mlr.press/v80/rabinowitz18a.html), ICML 2018.
- Park et al. [Generative Agents: Interactive Simulacra of Human Behavior](https://arxiv.org/abs/2304.03442), 2023.
- Park et al. [Generative Agent Simulations of 1,000 People](https://arxiv.org/abs/2411.10109), 2024–2026.
- Binz et al. [A Foundation Model to Predict and Capture Human Cognition](https://www.nature.com/articles/s41586-025-09215-4), Nature 2025.
- Zhou et al. [Social World Models](https://arxiv.org/abs/2509.00559), 2025–2026.
- Wu et al. [HumanLM: Simulating Users with State Alignment Beats Response Imitation](https://arxiv.org/abs/2603.03303), 2026.
- Luo et al. [Know You Before You Speak: PUMA](https://arxiv.org/abs/2605.24647), 2026.
- Zhang et al. [See, Infer, Intervene](https://arxiv.org/abs/2606.03371), 2026.

### 合规

- European Union. [Regulation (EU) 2024/1689 — Artificial Intelligence Act](https://eur-lex.europa.eu/legal-content/en/TXT/?uri=CELEX%3A32024R1689).
