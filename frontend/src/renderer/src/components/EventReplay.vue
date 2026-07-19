<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import type {
  HiwmActualResponsePayload,
  HiwmEvidenceObservedPayload,
  HiwmEvaluatedPayload,
  HiwmLockedPayload,
  HiwmPredictionGeneratedPayload,
  HiwmProfileUpdatedPayload,
  HiwmRobotResponsePayload,
  HiwmTimelineEvent,
  HiwmTimelineEventType,
} from '@/store/hiwm'

const props = withDefaults(
  defineProps<{
    events: readonly HiwmTimelineEvent[]
    sessionId?: string
    sessionIds?: readonly string[]
    sessionSelectionDisabled?: boolean
    deletionDisabled?: boolean
    stepDurationMs?: number
    playbackRate?: number
  }>(),
  {
    sessionId: '',
    sessionIds: () => [],
    sessionSelectionDisabled: false,
    deletionDisabled: false,
    stepDurationMs: 1300,
    playbackRate: 1,
  }
)

const emit = defineEmits<{
  seek: [timestampSeconds: number, event: HiwmTimelineEvent]
  'event-change': [event: HiwmTimelineEvent, index: number]
  'select-session': [sessionId: string]
  export: [sessionId: string]
  'delete-session': [sessionId: string]
}>()

const activeIndex = ref(0)
const playing = ref(false)
let playbackTimer: ReturnType<typeof setTimeout> | undefined

const activeEvent = computed(() => props.events[activeIndex.value] || null)
const canGoBack = computed(() => activeIndex.value > 0)
const canGoForward = computed(() => activeIndex.value < props.events.length - 1)

const stageLabels: Record<HiwmTimelineEventType, string> = {
  content_evidence_observed: '内容证据已冻结',
  visual_evidence_observed: '视觉证据已冻结',
  prosody_evidence_observed: '语气证据已冻结',
  prediction_generated: '预测已生成',
  locked: '预测已锁定',
  robot_response: '已锁定待播回应',
  actual_response: '实际回应已到达',
  evaluated: '预测已评估',
  profile_updated: '当前理解已更新',
}

const comparisonLabels: Record<HiwmEvaluatedPayload['comparison'], string> = {
  matched: '一致',
  partial: '部分一致',
  miss: '未命中',
  indeterminate: '无法判定',
}

const summary = (event: HiwmTimelineEvent): string => {
  switch (event.type) {
    case 'content_evidence_observed':
    case 'visual_evidence_observed':
    case 'prosody_evidence_observed':
      return (event.payload as HiwmEvidenceObservedPayload).label
    case 'prediction_generated': {
      const payload = event.payload as HiwmPredictionGeneratedPayload
      const selected = payload.actions.find(
        (action) => action.action_id === payload.selected_action_id
      )
      const informationGain =
        payload.planner?.formula === 'goal-information-gain-risk-uncertainty-v2'
          ? '，含信息增益评分'
          : ''
      return `${payload.actions.length} 个候选行动${selected ? `，选择“${selected.strategy}”` : ''}${informationGain}`
    }
    case 'locked': {
      const payload = event.payload as HiwmLockedPayload
      return `行动 ${payload.action_id} 已锁定，后续不覆写`
    }
    case 'robot_response': {
      const payload = event.payload as HiwmRobotResponsePayload
      return payload.utterance
    }
    case 'actual_response': {
      const payload = event.payload as HiwmActualResponsePayload
      return payload.content
    }
    case 'evaluated': {
      const payload = event.payload as HiwmEvaluatedPayload
      return `${comparisonLabels[payload.comparison]}：${payload.explanation}`
    }
    case 'profile_updated': {
      const payload = event.payload as HiwmProfileUpdatedPayload
      return `${payload.beliefs.length} 项当前理解发生变化`
    }
  }
}

const activeEvidencePayload = computed<HiwmEvidenceObservedPayload | null>(() => {
  if (
    activeEvent.value?.type !== 'content_evidence_observed' &&
    activeEvent.value?.type !== 'visual_evidence_observed' &&
    activeEvent.value?.type !== 'prosody_evidence_observed'
  ) {
    return null
  }
  return activeEvent.value.payload as HiwmEvidenceObservedPayload
})

const formatMeasurement = (value: string | number | boolean | null): string => {
  if (value === null) return '未提供'
  if (typeof value === 'boolean') return value ? '是' : '否'
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(3)
  return value
}

const formatTime = (seconds: number): string => {
  const date = new Date(seconds * 1000)
  if (!Number.isFinite(date.getTime())) return '--:--:--'
  return new Intl.DateTimeFormat('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(date)
}

const clearPlaybackTimer = (): void => {
  if (playbackTimer !== undefined) {
    clearTimeout(playbackTimer)
    playbackTimer = undefined
  }
}

const selectEvent = (index: number): void => {
  if (!props.events.length) return
  const boundedIndex = Math.min(Math.max(index, 0), props.events.length - 1)
  activeIndex.value = boundedIndex
  const event = props.events[boundedIndex]
  emit('event-change', event, boundedIndex)
  emit('seek', event.occurred_at, event)
}

const schedulePlayback = (): void => {
  clearPlaybackTimer()
  if (!playing.value || !props.events.length) return
  if (!canGoForward.value) {
    playing.value = false
    return
  }
  const rate = Math.max(0.25, props.playbackRate)
  const delay = Math.max(160, props.stepDurationMs / rate)
  playbackTimer = setTimeout(() => {
    selectEvent(activeIndex.value + 1)
    schedulePlayback()
  }, delay)
}

const togglePlayback = (): void => {
  if (!props.events.length) return
  if (!playing.value && !canGoForward.value) selectEvent(0)
  playing.value = !playing.value
}

const restart = (): void => {
  playing.value = false
  selectEvent(0)
}

watch(
  [playing, () => props.events.length, () => props.stepDurationMs, () => props.playbackRate],
  schedulePlayback
)

watch(
  () => props.events,
  (events) => {
    if (!events.length) {
      playing.value = false
      activeIndex.value = 0
      return
    }
    activeIndex.value = Math.min(activeIndex.value, events.length - 1)
  }
)

watch(
  () => props.sessionId,
  () => {
    playing.value = false
    activeIndex.value = 0
  }
)

onBeforeUnmount(clearPlaybackTimer)
</script>

<template>
  <section class="event-replay" aria-label="HIWM 互动记录回放">
    <header class="replay-header">
      <div>
        <span class="eyebrow">DERIVED EVENT REPLAY</span>
        <h2>事件回放</h2>
      </div>
      <div class="session-actions">
        <select
          v-if="sessionIds.length"
          :value="sessionId"
          :disabled="sessionSelectionDisabled"
          aria-label="选择回放会话"
          @change="emit('select-session', ($event.target as HTMLSelectElement).value)"
        >
          <option v-for="id in sessionIds" :key="id" :value="id">会话 {{ id.slice(0, 12) }}</option>
        </select>
        <span v-else :title="sessionId">未选择会话</span>
        <button
          type="button"
          :disabled="!sessionId || !events.length"
          @click="emit('export', sessionId)"
        >
          导出
        </button>
        <button
          type="button"
          class="danger"
          :disabled="!sessionId || deletionDisabled"
          @click="emit('delete-session', sessionId)"
        >
          删除会话
        </button>
      </div>
    </header>

    <p class="privacy-line">
      每个会话最多显示 200 条互动记录。点击记录可查看对应时间点，原始音频和视频不会保存。
    </p>

    <template v-if="events.length">
      <div class="playback-controls" aria-label="回放控制">
        <button type="button" title="回到开始" @click="restart">↺</button>
        <button
          type="button"
          :disabled="!canGoBack"
          title="上一事件"
          @click="selectEvent(activeIndex - 1)"
        >
          ←
        </button>
        <button
          type="button"
          class="play"
          :aria-label="playing ? '暂停回放' : '开始回放'"
          @click="togglePlayback"
        >
          {{ playing ? '暂停' : '回放' }}
        </button>
        <button
          type="button"
          :disabled="!canGoForward"
          title="下一事件"
          @click="selectEvent(activeIndex + 1)"
        >
          →
        </button>
        <span>{{ activeIndex + 1 }} / {{ events.length }}</span>
      </div>

      <div class="replay-layout">
        <ol class="timeline">
          <li
            v-for="(event, index) in events"
            :key="event.event_id"
            :class="[
              `is-${event.type}`,
              { active: index === activeIndex, visited: index < activeIndex },
            ]"
          >
            <button type="button" @click="selectEvent(index)">
              <span class="node" aria-hidden="true"></span>
              <time>{{ formatTime(event.occurred_at) }}</time>
              <span class="event-copy">
                <strong>{{ stageLabels[event.type] }}</strong>
                <small>{{ summary(event) }}</small>
              </span>
            </button>
          </li>
        </ol>

        <article v-if="activeEvent" class="active-event">
          <div class="active-meta">
            <span>{{ stageLabels[activeEvent.type] }}</span>
            <time>{{ formatTime(activeEvent.occurred_at) }}</time>
          </div>
          <p>{{ summary(activeEvent) }}</p>
          <dl v-if="activeEvidencePayload" class="evidence-measurements">
            <div v-for="(value, key) in activeEvidencePayload.measurements" :key="key">
              <dt>{{ key }}</dt>
              <dd>{{ formatMeasurement(value) }}</dd>
            </div>
          </dl>
          <dl>
            <div>
              <dt>Turn</dt>
              <dd>{{ activeEvent.turn_id }}</dd>
            </div>
            <div>
              <dt>Event</dt>
              <dd>{{ activeEvent.event_id }}</dd>
            </div>
            <div>
              <dt>Snapshot SHA-256</dt>
              <dd>{{ activeEvent.source_snapshot_sha256 }}</dd>
            </div>
          </dl>
        </article>
      </div>
    </template>

    <div v-else class="empty">
      <strong>当前会话还没有互动记录</strong>
      <span>开始对话后，重要的互动节点会依次显示在这里。</span>
    </div>
  </section>
</template>

<style scoped lang="less">
.event-replay {
  width: 100%;
  padding: 15px;
  color: #17231f;
  border: 1px solid #dfe7e3;
  border-radius: 14px;
  background: #ffffff;
  box-shadow: 0 10px 30px rgba(32, 58, 49, 0.05);
}

.replay-header,
.session-actions,
.playback-controls,
.active-meta {
  display: flex;
  align-items: center;
}

.replay-header {
  justify-content: space-between;
  gap: 14px;

  h2 {
    margin: 2px 0 0;
    font-size: 16px;
  }
}

.eyebrow {
  color: #148267;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.12em;
}

.session-actions {
  gap: 7px;
  flex-wrap: wrap;

  select {
    max-width: 190px;
    padding: 5px 24px 5px 8px;
    color: #3f514b;
    border: 1px solid #dfe7e3;
    border-radius: 6px;
    background: #ffffff;
    font:
      11px ui-monospace,
      monospace;

    &:disabled {
      opacity: 0.55;
    }
  }

  > span {
    max-width: 170px;
    overflow: hidden;
    color: #66756f;
    font:
      11px ui-monospace,
      monospace;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  button,
  .playback-controls button {
    padding: 5px 8px;
  }
}

button {
  min-height: 30px;
  color: #3f514b;
  border: 1px solid #dfe7e3;
  border-radius: 6px;
  background: #ffffff;
  font-size: 11px;
  cursor: pointer;

  &:hover:not(:disabled),
  &:focus-visible {
    color: #148267;
    border-color: rgba(20, 130, 103, 0.46);
    background: #f4faf8;
    outline: none;
  }

  &:disabled {
    cursor: not-allowed;
    opacity: 0.38;
  }

  &.danger:hover:not(:disabled) {
    color: #a72531;
    border-color: rgba(167, 37, 49, 0.45);
    background: #fff7f7;
  }
}

.privacy-line {
  margin: 11px 0;
  color: #66756f;
  font-size: 11px;
  line-height: 1.5;
}

.playback-controls {
  gap: 6px;
  padding: 7px;
  border: 1px solid #e4ebe8;
  border-radius: 8px;
  background: #f8faf9;

  button {
    min-width: 32px;
    height: 28px;
  }

  .play {
    min-width: 62px;
    color: #ffffff;
    border-color: #148267;
    background: #148267;
  }

  span {
    margin-left: auto;
    color: #5f706a;
    font:
      11px ui-monospace,
      monospace;
  }
}

.replay-layout {
  display: grid;
  grid-template-columns: minmax(260px, 0.85fr) minmax(280px, 1.15fr);
  gap: 10px;
  margin-top: 10px;
}

.timeline {
  max-height: 340px;
  margin: 0;
  padding: 2px 5px 2px 0;
  overflow: auto;
  list-style: none;

  li {
    position: relative;

    &::before {
      position: absolute;
      top: 24px;
      bottom: -8px;
      left: 15px;
      width: 1px;
      background: #d8e3df;
      content: '';
    }

    &:last-child::before {
      display: none;
    }

    > button {
      display: grid;
      grid-template-columns: 22px 66px minmax(0, 1fr);
      gap: 7px;
      width: 100%;
      padding: 8px 7px;
      text-align: left;
      border-color: transparent;
      background: transparent;
    }

    &.active > button {
      border-color: #b9dfd3;
      background: #edf8f4;
    }

    &.active .node,
    &.visited .node {
      border-color: #148267;
      background: #148267;
      box-shadow: 0 0 8px rgba(20, 130, 103, 0.34);
    }

    time {
      margin-top: 2px;
      color: #5f706a;
      font:
        10px ui-monospace,
        monospace;
    }
  }
}

.node {
  z-index: 1;
  box-sizing: border-box;
  width: 9px;
  height: 9px;
  margin: 4px auto 0;
  border: 2px solid #91a29b;
  border-radius: 50%;
  background: #ffffff;
}

.event-copy {
  min-width: 0;

  strong,
  small {
    display: block;
  }

  strong {
    color: #25342f;
    font-size: 12px;
  }

  small {
    margin-top: 3px;
    display: -webkit-box;
    overflow: hidden;
    color: #5f706a;
    font-size: 11px;
    line-height: 1.45;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
  }
}

.active-event {
  min-width: 0;
  padding: 15px;
  border: 1px solid #e1e9e5;
  border-radius: 10px;
  background: #fafcfb;

  > p {
    min-height: 66px;
    margin: 16px 0;
    color: #33443e;
    font-size: 12px;
    line-height: 1.6;
  }

  dl {
    margin: 0;

    div {
      padding: 7px 0;
      border-top: 1px solid #e7eeeb;
    }

    dt {
      color: #5f706a;
      font-size: 10px;
      text-transform: uppercase;
    }

    dd {
      margin: 3px 0 0;
      color: #53655f;
      font:
        11px/1.45 ui-monospace,
        monospace;
      overflow-wrap: anywhere;
    }
  }
}

.active-meta {
  justify-content: space-between;
  color: #148267;
  font-size: 12px;

  time {
    color: #5f706a;
    font:
      11px ui-monospace,
      monospace;
  }
}

.empty {
  display: grid;
  place-items: center;
  min-height: 130px;
  color: #5f706a;
  text-align: center;

  strong {
    color: #53655f;
  }

  span {
    max-width: 520px;
    font-size: 12px;
    line-height: 1.6;
  }
}

@media (max-width: 720px) {
  .event-replay {
    padding: 12px;
  }

  .replay-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .session-actions {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto auto;
    width: 100%;

    select,
    > span {
      max-width: none;
      min-width: 0;
    }
  }

  .replay-layout {
    grid-template-columns: 1fr;
  }

  .timeline {
    max-height: 260px;
  }

  .active-event {
    padding: 12px;
  }
}
</style>
