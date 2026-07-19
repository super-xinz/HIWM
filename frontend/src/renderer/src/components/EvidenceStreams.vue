<script setup lang="ts">
import { computed } from 'vue'

import { isDisplayableChatRecord } from '@/utils/evidenceStreamUtils'

type EvidenceInput = Record<string, unknown>

type EvidenceView = {
  id: string
  title: string
  value: string
  detail: string
  timestampMs: number | null
  source: EvidenceInput
}

type ChatView = {
  id: string
  role: string
  message: string
  status: '实时' | '已确认'
  timestampMs: number | null
  source: EvidenceInput
}

const props = withDefaults(
  defineProps<{
    visionEvidence?: readonly EvidenceInput[]
    prosodyEvidence?: readonly EvidenceInput[]
    chatRecords?: readonly EvidenceInput[]
    activeTimestampMs?: number | null
  }>(),
  {
    visionEvidence: () => [],
    prosodyEvidence: () => [],
    chatRecords: () => [],
    activeTimestampMs: null,
  }
)

const emit = defineEmits<{
  seek: [timestampMs: number, source: EvidenceInput]
}>()

// These terms represent conclusions the evidence stream must not claim. Incoming
// items carrying them are omitted rather than silently relabelled as facts.
const prohibitedInference = /(真实情绪|情绪识别|人格|性格|撒谎|说谎|测谎|心理诊断|内心状态)/i

const firstString = (item: EvidenceInput, keys: readonly string[]): string => {
  for (const key of keys) {
    const value = item[key]
    if (typeof value === 'string' && value.trim()) return value.trim()
  }
  return ''
}

const firstNumber = (item: EvidenceInput, keys: readonly string[]): number | null => {
  for (const key of keys) {
    const value = item[key]
    if (typeof value === 'number' && Number.isFinite(value)) return value
  }
  return null
}

const timestampMs = (item: EvidenceInput): number | null => {
  const direct = firstNumber(item, ['timestamp_ms', 'time_ms', 'start_ms', 'created_at_ms'])
  if (direct !== null) return direct
  const seconds = firstNumber(item, [
    'observed_at',
    'occurred_at',
    'timestamp',
    'created_at',
    'start_time',
  ])
  if (seconds === null) return null
  return seconds > 100_000_000_000 ? seconds : seconds * 1000
}

const printableValue = (item: EvidenceInput): string => {
  const value = item.value ?? item.delta ?? item.score ?? item.count
  if (typeof value === 'number' && Number.isFinite(value)) {
    const unit = typeof item.unit === 'string' ? item.unit : ''
    return `${Math.round(value * 1000) / 1000}${unit ? ` ${unit}` : ''}`
  }
  return typeof value === 'string' ? value : ''
}

const normalizeEvidence = (items: readonly EvidenceInput[], prefix: string): EvidenceView[] =>
  items.flatMap((item, index) => {
    const title =
      firstString(item, ['label', 'name', 'feature', 'kind', 'type']) || `可观察信号 ${index + 1}`
    const detail = firstString(item, ['detail', 'description', 'summary', 'content', 'source'])
    const value = printableValue(item)
    if (prohibitedInference.test(`${title} ${detail} ${value}`)) return []
    return [
      {
        id:
          firstString(item, ['evidence_id', 'id', 'event_id']) ||
          `${prefix}-${index}-${timestampMs(item) || 'undated'}`,
        title,
        value,
        detail,
        timestampMs: timestampMs(item),
        source: item,
      },
    ]
  })

const visionItems = computed(() => normalizeEvidence(props.visionEvidence, 'vision'))
const prosodyItems = computed(() => normalizeEvidence(props.prosodyEvidence, 'prosody'))

const chatItems = computed<ChatView[]>(() =>
  props.chatRecords.flatMap((item, index) => {
    if (!isDisplayableChatRecord(item)) return []
    const message = firstString(item, ['message', 'content', 'text', 'transcript'])
    if (!message) return []
    const partial =
      item.final === false ||
      item.end_of_speech === false ||
      item.mode === 'increment' ||
      item.status === 'partial'
    const roleValue = firstString(item, ['role', 'speaker'])
    const role =
      roleValue === 'human' || roleValue === 'user'
        ? '用户'
        : roleValue === 'avatar' || roleValue === 'assistant'
          ? '虚拟人'
          : roleValue || '对话'
    return [
      {
        id:
          firstString(item, ['stream_key', 'id', 'request_id']) ||
          `chat-${index}-${timestampMs(item) || 'undated'}`,
        role,
        message,
        status: partial ? '实时' : '已确认',
        timestampMs: timestampMs(item),
        source: item,
      },
    ]
  })
)

const convergenceSources = computed(() => [
  {
    key: 'vision',
    label: '视觉辅助',
    count: visionItems.value.length,
    pulseKey: visionItems.value.at(-1)?.id || 'empty',
  },
  {
    key: 'prosody',
    label: '语气辅助',
    count: prosodyItems.value.length,
    pulseKey: prosodyItems.value.at(-1)?.id || 'empty',
  },
  {
    key: 'chat',
    label: '内容主要依据',
    count: chatItems.value.length,
    pulseKey: chatItems.value.at(-1)
      ? `${chatItems.value.at(-1)?.id}-${chatItems.value.at(-1)?.status}-${chatItems.value.at(-1)?.message.length}`
      : 'empty',
  },
])

const formatTime = (value: number | null): string => {
  if (value === null) return '无时间戳'
  if (value >= 100_000_000_000) {
    return new Intl.DateTimeFormat('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    }).format(new Date(value))
  }
  const safeValue = Math.max(0, value)
  const minutes = Math.floor(safeValue / 60_000)
  const seconds = Math.floor((safeValue % 60_000) / 1000)
  const milliseconds = Math.floor(safeValue % 1000)
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}.${String(milliseconds).padStart(3, '0')}`
}

const seek = (value: number | null, source: EvidenceInput): void => {
  if (value === null) return
  emit('seek', value, source)
}

const isActive = (value: number | null): boolean =>
  value !== null &&
  props.activeTimestampMs !== null &&
  Math.abs(value - props.activeTimestampMs) < 500
</script>

<template>
  <section class="evidence-streams" aria-label="交互证据流">
    <header class="panel-header">
      <div>
        <span class="eyebrow">OBSERVABLE EVIDENCE</span>
        <h2>交互证据流</h2>
      </div>
      <p>仅展示可观察信号与对话内容，不把信号解读为对个人内在状态的事实结论。</p>
    </header>

    <div class="stream-grid">
      <article class="stream-column">
        <header>
          <div>
            <span class="stream-dot vision" aria-hidden="true"></span>
            <h3>视觉特征</h3>
          </div>
          <small>{{ visionItems.length }} 条</small>
        </header>
        <ul v-if="visionItems.length">
          <li
            v-for="item in visionItems"
            :key="item.id"
            :class="{ active: isActive(item.timestampMs) }"
          >
            <button
              type="button"
              class="time"
              :disabled="item.timestampMs === null"
              :title="item.timestampMs === null ? '该条目没有可定位时间' : '跳转到该时刻'"
              @click="seek(item.timestampMs, item.source)"
            >
              {{ formatTime(item.timestampMs) }}
            </button>
            <div>
              <strong>{{ item.title }}</strong>
              <span v-if="item.value">{{ item.value }}</span>
              <p v-if="item.detail">{{ item.detail }}</p>
            </div>
          </li>
        </ul>
        <p v-else class="empty">等待面部点位、头部姿态等本地派生信号。</p>
      </article>

      <article class="stream-column">
        <header>
          <div>
            <span class="stream-dot prosody" aria-hidden="true"></span>
            <h3>语音韵律</h3>
          </div>
          <small>{{ prosodyItems.length }} 条</small>
        </header>
        <ul v-if="prosodyItems.length">
          <li
            v-for="item in prosodyItems"
            :key="item.id"
            :class="{ active: isActive(item.timestampMs) }"
          >
            <button
              type="button"
              class="time"
              :disabled="item.timestampMs === null"
              :title="item.timestampMs === null ? '该条目没有可定位时间' : '跳转到该时刻'"
              @click="seek(item.timestampMs, item.source)"
            >
              {{ formatTime(item.timestampMs) }}
            </button>
            <div>
              <strong>{{ item.title }}</strong>
              <span v-if="item.value">{{ item.value }}</span>
              <p v-if="item.detail">{{ item.detail }}</p>
            </div>
          </li>
        </ul>
        <p v-else class="empty">等待语速、停顿、音高和能量变化等本地派生信号。</p>
      </article>

      <article class="stream-column chat-column">
        <header>
          <div>
            <span class="stream-dot chat" aria-hidden="true"></span>
            <h3>对话内容</h3>
          </div>
          <small>{{ chatItems.length }} 条</small>
        </header>
        <ul v-if="chatItems.length">
          <li
            v-for="item in chatItems"
            :key="item.id"
            :class="{ active: isActive(item.timestampMs) }"
          >
            <button
              type="button"
              class="time"
              :disabled="item.timestampMs === null"
              :title="item.timestampMs === null ? '该条目没有可定位时间' : '跳转到该时刻'"
              @click="seek(item.timestampMs, item.source)"
            >
              {{ formatTime(item.timestampMs) }}
            </button>
            <div>
              <div class="chat-meta">
                <strong>{{ item.role }}</strong>
                <span :class="{ partial: item.status === '实时' }">{{ item.status }}</span>
              </div>
              <p>{{ item.message }}</p>
            </div>
          </li>
        </ul>
        <p v-else class="empty">暂无可显示的实时或已确认转录。</p>
      </article>
    </div>

    <div class="evidence-convergence" aria-live="polite">
      <div class="convergence-tracks" aria-label="证据汇聚状态">
        <div
          v-for="source in convergenceSources"
          :key="source.key"
          class="convergence-track"
          :class="[`is-${source.key}`, { active: source.count > 0 }]"
        >
          <span>{{ source.label }}</span>
          <i :key="`${source.key}-${source.pulseKey}`" aria-hidden="true"></i>
          <small>{{ source.count }} 条</small>
        </div>
      </div>
      <div class="convergence-target">
        <span aria-hidden="true">→</span>
        <div>
          <small>OBSERVABLE INPUTS</small>
          <strong>汇入上方「当前关键判断」</strong>
          <p>内容与业务事实为主要依据；视觉和语气仅作辅助。</p>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped lang="less">
.evidence-streams {
  --line: #dfe7e3;
  width: 100%;
  padding: 15px;
  color: #17231f;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: #ffffff;
  box-shadow: 0 10px 30px rgba(32, 58, 49, 0.05);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 13px;

  h2 {
    margin: 2px 0 0;
    font-size: 16px;
  }

  p {
    max-width: 560px;
    margin: 0;
    color: #5d6e68;
    font-size: 12px;
    line-height: 1.6;
    text-align: right;
  }
}

.eyebrow {
  color: #148267;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.12em;
}

.stream-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.stream-column {
  min-width: 0;
  border: 1px solid var(--line);
  border-radius: 11px;
  background: #fafcfb;

  > header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 11px 12px;
    border-bottom: 1px solid var(--line);

    > div {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    h3 {
      margin: 0;
      font-size: 13px;
    }

    small {
      color: #5f706a;
      font-size: 11px;
    }
  }

  ul {
    max-height: 258px;
    margin: 0;
    padding: 5px;
    overflow: auto;
    list-style: none;
  }

  li {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    gap: 9px;
    padding: 9px 7px;
    border-radius: 8px;

    & + li {
      border-top: 1px solid #edf1ef;
    }

    &.active {
      background: #edf8f4;
      box-shadow: inset 2px 0 #148267;
    }

    strong {
      font-size: 12px;
      font-weight: 620;
    }

    div > span {
      float: right;
      color: #148267;
      font:
        11px ui-monospace,
        monospace;
    }

    p {
      margin: 3px 0 0;
      overflow-wrap: anywhere;
      color: #5d6e68;
      font-size: 11px;
      line-height: 1.55;
    }
  }
}

.stream-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #148267;
  box-shadow: 0 0 8px currentColor;

  &.prosody {
    color: #526fc7;
    background: #6e89dc;
  }

  &.chat {
    color: #9a6417;
    background: #d79a45;
  }
}

.time {
  height: fit-content;
  padding: 2px 4px;
  color: #148267;
  border: 0;
  border-radius: 4px;
  background: transparent;
  font:
    11px ui-monospace,
    monospace;
  cursor: pointer;

  &:hover:not(:disabled),
  &:focus-visible {
    background: #e6f4ef;
    outline: none;
  }

  &:disabled {
    color: #5f746e;
    cursor: default;
  }
}

.chat-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;

  span {
    float: none !important;
    padding: 1px 5px;
    border: 1px solid rgba(112, 225, 193, 0.2);
    border-radius: 99px;
    font-family: inherit !important;

    &.partial {
      color: #8c5b16;
      border-color: rgba(154, 100, 23, 0.28);
      background: #fff9ef;
    }
  }
}

.empty {
  margin: 0;
  padding: 22px 13px;
  color: #5f706a;
  font-size: 12px;
  line-height: 1.6;
}

.evidence-convergence {
  display: grid;
  grid-template-columns: minmax(260px, 1fr) minmax(260px, 0.72fr);
  align-items: center;
  gap: 14px;
  padding: 11px 12px;
  margin-top: 11px;
  border: 1px solid #e7eeeb;
  border-radius: 10px;
  background: #fafcfb;
}

.convergence-tracks {
  display: grid;
  gap: 6px;
}

.convergence-track {
  display: grid;
  grid-template-columns: 92px minmax(40px, 1fr) 42px;
  align-items: center;
  gap: 8px;
  color: #5f706a;
  font-size: 10px;

  > span {
    white-space: nowrap;
  }

  i {
    position: relative;
    height: 1px;
    overflow: visible;
    background: #dfe7e3;
  }

  small {
    color: inherit;
    font:
      10px ui-monospace,
      monospace;
    text-align: right;
  }

  &.active {
    color: #148267;

    i {
      background: linear-gradient(90deg, rgba(112, 225, 193, 0.16), currentColor);

      &::after {
        position: absolute;
        top: -2px;
        left: 0;
        width: 5px;
        height: 5px;
        border-radius: 50%;
        background: currentColor;
        box-shadow: 0 0 8px currentColor;
        animation: evidence-converge 0.7s ease-out both;
        content: '';
      }
    }
  }

  &.is-prosody.active {
    color: #526fc7;
  }

  &.is-chat.active {
    color: #9a6417;
  }
}

.convergence-target {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  padding-left: 12px;
  border-left: 1px solid #dfe7e3;

  > span {
    color: #148267;
    font-size: 18px;
  }

  small,
  strong,
  p {
    display: block;
  }

  small {
    color: #148267;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.1em;
  }

  strong {
    margin-top: 2px;
    color: #25342f;
    font-size: 12px;
  }

  p {
    margin: 3px 0 0;
    color: #5f706a;
    font-size: 10px;
    line-height: 1.5;
  }
}

@keyframes evidence-converge {
  from {
    left: 0;
    opacity: 0;
    transform: scale(0.75);
  }

  35% {
    opacity: 1;
  }

  to {
    left: calc(100% - 5px);
    opacity: 0;
    transform: scale(1);
  }
}

@media (max-width: 960px) {
  .stream-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .chat-column {
    grid-column: 1 / -1;
  }
}

@media (max-width: 620px) {
  .evidence-streams {
    padding: 12px;
  }

  .panel-header {
    display: block;

    p {
      margin-top: 6px;
      text-align: left;
    }
  }

  .stream-grid {
    grid-template-columns: 1fr;
  }

  .chat-column {
    grid-column: auto;
  }

  .evidence-convergence {
    grid-template-columns: 1fr;
    gap: 10px;
    padding: 10px;
  }

  .convergence-target {
    padding-top: 9px;
    padding-left: 0;
    border-top: 1px solid rgba(149, 220, 199, 0.15);
    border-left: 0;
  }
}

@media (prefers-reduced-motion: reduce) {
  .convergence-track.active i::after {
    display: none;
    animation: none;
  }
}
</style>
