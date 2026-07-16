<template>
  <div ref="wrapRef" class="hiwm-board">
    <header class="hiwm-header">
      <div class="hiwm-brand">
        <span class="hiwm-live-dot" :class="{ 'is-live': streamState === 'open' }" />
        <div>
          <strong>HIWM LIVE</strong>
          <span>人际互动世界模型</span>
        </div>
      </div>
      <div class="hiwm-header-meta">
        <span>{{ connectionLabel }}</span>
        <span v-if="webRTCId" class="hiwm-session">Session {{ webRTCId }}</span>
        <span v-if="model">{{ model.model_name }} · {{ model.probability_kind }}</span>
      </div>
    </header>

    <div v-if="hiwmError" class="hiwm-error" role="alert">HIWM 后端错误：{{ hiwmError }}</div>

    <ApiConfigPanel class="hiwm-api-config" />

    <main class="hiwm-grid">
      <aside class="hiwm-panel hiwm-beliefs">
        <div class="panel-heading">
          <div>
            <span class="panel-kicker">CURRENT BELIEFS</span>
            <h1>当前信念与证据</h1>
          </div>
          <span v-if="turnId" class="panel-tag">Turn {{ turnId }}</span>
        </div>

        <div v-if="objective" class="objective-card">
          <span>本轮目标</span>
          <p>{{ objective }}</p>
        </div>

        <div v-if="beliefs.length" class="belief-list">
          <article v-for="belief in beliefs" :key="belief.id" class="belief-card">
            <div class="belief-card__topline">
              <span class="belief-status">{{ belief.status }}</span>
              <span v-if="isProbability(belief.confidence)" class="belief-confidence">
                {{ formatProbability(belief.confidence) }}
              </span>
            </div>
            <p class="belief-statement">{{ belief.statement }}</p>
            <p class="belief-uncertainty">变化：{{ belief.change }}</p>
            <div v-if="belief.evidence_refs?.length" class="evidence-list">
              <span v-for="evidence in belief.evidence_refs" :key="evidence">
                {{ evidenceLabel(evidence) }}
              </span>
            </div>
          </article>
        </div>
        <div v-else class="true-empty">等待真实输入</div>
      </aside>

      <section class="hiwm-center">
        <div class="camera-stage">
          <div ref="localVideoContainerRef" class="local-video-container">
            <video
              v-show="hasCamera && !cameraOff"
              ref="localVideoRef"
              class="local-video"
              autoplay
              muted
              playsinline
            />
            <div v-if="!hasCamera || cameraOff" class="camera-empty">
              {{ cameraOff ? '真实摄像头已关闭' : '等待真实摄像头' }}
            </div>
          </div>

          <div class="camera-hud camera-hud--top">
            <span>ROBOT VIEW</span>
            <span>{{ streamState === 'open' ? '实时会话' : '本地预览' }}</span>
          </div>

          <div v-if="showChatRecords" class="live-caption">
            <span>
              {{
                latestTranscript ? (latestTranscript.role === 'avatar' ? '机器人' : '用户') : '字幕'
              }}
            </span>
            <p>{{ latestTranscript?.message || '等待真实输入' }}</p>
          </div>
        </div>

        <div class="observation-panel">
          <div class="observation-panel__heading">
            <span>BACKEND OBSERVATION</span>
            <time v-if="observation">
              {{ formatTimestamp(observation.current_asr.observed_at) }}
            </time>
          </div>
          <p v-if="observation?.current_asr.content">{{ observation.current_asr.content }}</p>
          <p v-else class="is-empty">等待真实输入</p>
          <span v-if="observation?.current_asr.source" class="observation-source">
            来源：{{ observation.current_asr.source }}
          </span>
        </div>

        <div class="hiwm-controls">
          <div v-if="toolsVisible" class="hiwm-actions">
            <ActionGroup />
          </div>
          <div class="hiwm-primary-control">
            <span
              v-if="(!hasMic || micMuted) && streamState === 'open' && inputVisible"
              class="real-input-required"
            >
              请开启真实麦克风继续
            </span>
            <ChatBtn
              v-else-if="webcamAccessed && inputVisible"
              :audio-source-callback="audioSourceCallback"
              :stream-state="streamState"
              wave-color="#70e1c1"
              @start-chat="onStartChat"
            />
          </div>
        </div>

        <div ref="remoteVideoContainerRef" class="remote-output" aria-hidden="true">
          <video
            v-if="!avatarType"
            ref="remoteVideoRef"
            autoplay
            playsinline
            :muted="volumeMuted"
          />
        </div>
      </section>

      <aside class="hiwm-panel hiwm-predictions">
        <div class="panel-heading">
          <div>
            <span class="panel-kicker">ACTION FORECAST</span>
            <h1>真实行动分支</h1>
          </div>
          <span v-if="actions.length" class="panel-tag">{{ visibleActions.length }} 条</span>
        </div>

        <div v-if="visibleActions.length" class="action-list">
          <article
            v-for="(action, index) in visibleActions"
            :key="action.action_id"
            class="action-card"
            :class="{ 'is-selected': action.action_id === selectedActionId }"
          >
            <div class="action-card__heading">
              <span class="action-index">{{ String.fromCharCode(65 + index) }}</span>
              <strong>{{ action.strategy }}</strong>
              <span v-if="action.action_id === selectedActionId" class="selected-badge">
                已由后端选择
              </span>
            </div>
            <p v-if="action.utterance" class="action-utterance">“{{ action.utterance }}”</p>
            <dl>
              <div>
                <dt>预测回应</dt>
                <dd>{{ action.predicted_observation }}</dd>
              </div>
              <div>
                <dt>状态变化</dt>
                <dd>{{ stateDeltaLabel(action.predicted_state_delta) }}</dd>
              </div>
            </dl>
            <div class="action-metrics">
              <span v-if="isProbability(action.goal_probability)">
                目标 {{ formatProbability(action.goal_probability) }}
              </span>
              <span v-if="isProbability(action.risk_probability)">
                风险 {{ formatProbability(action.risk_probability) }}
              </span>
            </div>
            <p v-if="action.risk" class="action-risk">风险：{{ action.risk }}</p>
            <p v-if="isProbability(action.uncertainty)" class="action-uncertainty">
              不确定性：{{ formatProbability(action.uncertainty) }}
            </p>
          </article>
        </div>
        <div v-else class="true-empty">等待真实输入</div>
      </aside>
    </main>

    <footer class="hiwm-loop">
      <div class="loop-heading">
        <span class="panel-kicker">PREDICTION → FEEDBACK → UPDATE</span>
        <strong>可审计反馈闭环</strong>
      </div>
      <div class="loop-steps">
        <article :class="{ 'is-complete': lockedPrediction }">
          <span>01</span>
          <div>
            <strong>预测锁定</strong>
            <p v-if="lockedPrediction">
              {{ lockedPrediction.prediction_id }} ·
              {{ formatTimestamp(lockedPrediction.locked_at) }}
            </p>
            <p v-else>等待真实输入</p>
          </div>
        </article>
        <i aria-hidden="true">→</i>
        <article :class="{ 'is-complete': feedback }">
          <span>02</span>
          <div>
            <strong>实际反馈</strong>
            <p v-if="feedback">{{ feedback.actual_observation }}</p>
            <p v-else>等待真实输入</p>
          </div>
        </article>
        <i aria-hidden="true">→</i>
        <article :class="{ 'is-complete': changedBeliefs.length }">
          <span>03</span>
          <div>
            <strong>信念更新</strong>
            <p v-if="changedBeliefs.length">
              {{ changedBeliefs.join('；') }}
            </p>
            <p v-else>等待真实输入</p>
          </div>
        </article>
      </div>
      <div v-if="feedback" class="feedback-verdict">
        <strong>{{ feedback.comparison }}</strong>
        <span>{{ feedback.explanation }}</span>
      </div>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'

import ActionGroup from '@/components/ActionGroup.vue'
import ApiConfigPanel from '@/components/ApiConfigPanel.vue'
import ChatBtn from '@/components/ChatBtn.vue'
import { useAppStore } from '@/store/app'
import { useChatStore } from '@/store/chat'
import { useHiwmStore } from '@/store/hiwm'
import { useMediaStore } from '@/store/media'
import { useVideoChatStore } from '@/store/webrtc'
import { useVisionStore } from '@/store/vision'

const visionState = useVisionStore()
const videoChatState = useVideoChatStore()
const chatState = useChatStore()
const hiwmState = useHiwmStore()
const appState = useAppStore()
const mediaState = useMediaStore()

const wrapRef = ref<HTMLDivElement>()
const localVideoContainerRef = ref<HTMLDivElement>()
const remoteVideoContainerRef = ref<HTMLDivElement>()
const localVideoRef = ref<HTMLVideoElement>()
const remoteVideoRef = ref<HTMLVideoElement>()

const { streamState, webRTCId } = storeToRefs(videoChatState)
const { volumeMuted, showChatRecords } = storeToRefs(chatState)
const { avatarType, chatRecords, inputVisible, toolsVisible } = storeToRefs(appState)
const { hasCamera, hasMic, micMuted, cameraOff, webcamAccessed } = storeToRefs(mediaState)
const {
  turnId,
  objective,
  observation,
  beliefs,
  actions,
  selectedActionId,
  lockedPrediction,
  feedback,
  model,
  error: hiwmError,
} = storeToRefs(hiwmState)

const visibleActions = computed(() => actions.value.slice(0, 3))
const evidenceById = computed(() => {
  if (!observation.value) return new Map()
  const evidence = [
    observation.value.current_asr,
    ...(observation.value.camera ? [observation.value.camera] : []),
    ...(observation.value.history || []),
  ]
  return new Map(evidence.map((item) => [item.evidence_id, item]))
})
const changedBeliefs = computed(() =>
  beliefs.value
    .filter((belief) => belief.change !== 'unchanged')
    .map((belief) => `${belief.change}: ${belief.statement}`)
)
const latestTranscript = computed(() => {
  const records = chatRecords.value.filter(
    (record) => record.message && !record.invalid && !record.cancelled
  )
  return records.at(-1) || null
})
const connectionLabel = computed(() => {
  if (streamState.value === 'open') return '真实会话在线'
  if (streamState.value === 'waiting') return '正在连接真实后端'
  return '未连接'
})

onMounted(() => {
  chatState.showChatRecords = true
  const wrapper = wrapRef.value
  if (wrapper) {
    visionState.wrapperRef = wrapper
    visionState.wrapperRect.width = wrapper.clientWidth
    visionState.wrapperRect.height = wrapper.clientHeight
    visionState.isLandscape = wrapper.clientWidth > wrapper.clientHeight
  }
  visionState.remoteVideoContainerRef = remoteVideoContainerRef.value
  visionState.localVideoContainerRef = localVideoContainerRef.value
  visionState.localVideoRef = localVideoRef.value
  visionState.remoteVideoRef = remoteVideoRef.value
})

const audioSourceCallback = (): MediaStream | null => mediaState.localStream

const isProbability = (value: unknown): value is number =>
  typeof value === 'number' && Number.isFinite(value)

const formatProbability = (value: number): string =>
  new Intl.NumberFormat('zh-CN', {
    style: 'percent',
    maximumFractionDigits: 1,
  }).format(value)

const evidenceLabel = (evidenceId: string): string => {
  const evidence = evidenceById.value.get(evidenceId)
  return evidence?.content || `${evidence?.source || 'evidence'} · ${evidenceId}`
}

const stateDeltaLabel = (deltas: Array<{ target: string; predicted_change: string }>): string =>
  deltas.map((delta) => `${delta.target}: ${delta.predicted_change}`).join('；')

const formatTimestamp = (value: number | string): string => {
  if (value === '' || value === null || value === undefined) return ''
  const numericValue = typeof value === 'number' && value < 1_000_000_000_000 ? value * 1000 : value
  const date = new Date(numericValue)
  if (Number.isNaN(date.getTime())) return String(value)
  return date.toLocaleTimeString('zh-CN', { hour12: false })
}

function onStartChat(): void {
  void videoChatState.startWebRTC()
}
</script>

<style lang="less" scoped>
@import './index.less';
</style>
