<template>
  <div ref="wrapRef" class="hiwm-board">
    <div v-if="hiwmError" class="hiwm-error" role="alert">HIWM 后端错误：{{ hiwmError }}</div>

    <main class="hiwm-grid">
      <aside class="hiwm-panel hiwm-beliefs">
        <div class="panel-heading">
          <div>
            <span class="panel-kicker">CURRENT BELIEFS</span>
            <h1>当前信念与证据</h1>
          </div>
          <span v-if="turnId" class="panel-tag">Turn {{ turnId }}</span>
        </div>

        <details class="profile-disclosure" :open="Boolean(profileDraft || profileSavedAt)">
          <summary>
            <span>会话背景</span>
            <small>{{ profileSavedAt ? '本机已保存' : '可选' }}</small>
          </summary>
          <section class="initial-profile-card">
            <textarea
              v-model="profileDraft"
              maxlength="4000"
              :disabled="streamState !== 'closed'"
              placeholder="填写用户主动确认的背景、偏好或任务约束；不要填写推测出的心理标签。"
            />
            <footer>
              <span>只作为可撤回的会话上下文。</span>
              <button type="button" :disabled="streamState !== 'closed'" @click="clearProfile">
                清除
              </button>
              <button type="button" :disabled="streamState !== 'closed'" @click="saveProfile">
                保存
              </button>
            </footer>
          </section>
        </details>

        <div v-if="objective" class="objective-card">
          <span>本轮目标</span>
          <p>{{ objective }}</p>
        </div>

        <section v-if="contentSignals.length" class="content-understanding">
          <div class="content-understanding__heading">
            <span>本轮内容理解</span>
            <small>仅来自已完成字幕</small>
          </div>
          <article v-for="signal in contentSignals" :key="signal.id">
            <span :class="`is-${signal.category}`">
              {{ contentCategoryLabel(signal.category) }}
            </span>
            <p>{{ signal.statement }}</p>
            <small>
              不确定性 {{ formatProbability(1 - signal.confidence) }} ·
              {{ beliefChangeLabel(signal.change) }}
            </small>
          </article>
        </section>

        <div v-if="beliefs.length" class="belief-list">
          <section v-for="group in beliefGroups" :key="group.status" class="belief-group">
            <h2>
              {{ group.label }}
              <small>{{ group.items.length }}</small>
            </h2>
            <article v-for="belief in group.items" :key="belief.id" class="belief-card">
              <div class="belief-card__topline">
                <span class="belief-status">{{ group.shortLabel }}</span>
                <span v-if="isProbability(belief.confidence)" class="belief-confidence">
                  不确定性 {{ formatProbability(1 - belief.confidence) }}
                </span>
              </div>
              <p class="belief-statement">{{ belief.statement }}</p>
              <p class="belief-uncertainty">本轮：{{ beliefChangeLabel(belief.change) }}</p>
              <div v-if="belief.evidence_refs?.length" class="evidence-list">
                <span v-for="evidence in belief.evidence_refs" :key="evidence">
                  {{ evidenceLabel(evidence) }}
                </span>
              </div>
            </article>
          </section>
        </div>
        <div v-else class="true-empty">等待真实输入</div>
      </aside>

      <section class="hiwm-center">
        <div class="camera-stage" :class="{ 'has-live-caption': showChatRecords }">
          <div
            ref="localVideoContainerRef"
            data-testid="camera-surface"
            class="local-video-container video-surface video-surface--camera is-primary"
            aria-label="真人摄像头主画面"
          >
            <video
              v-show="hasCamera && !cameraOff"
              ref="localVideoRef"
              class="local-video"
              autoplay
              muted
              playsinline
            />
            <FaceLandmarkOverlay
              :video="localVideoRef || null"
              :enabled="analysisAuthorized && hasCamera && !cameraOff"
              :mirror="true"
              fit="cover"
              :show-status="false"
            />
            <div v-if="!hasCamera || cameraOff" class="camera-empty">
              {{ cameraOff ? '真实摄像头已关闭' : '等待真实摄像头' }}
            </div>

            <div class="camera-hud camera-hud--top">
              <span v-if="face.tracked">
                本地面部点阵 · 68 点 · yaw {{ face.yaw.toFixed(1) }}° · pitch
                {{ face.pitch.toFixed(1) }}°
              </span>
              <span v-else>{{ cameraInferenceLabel }}</span>
            </div>

            <div class="surface-identity">
              <span>
                <i :class="{ on: hasCamera && !cameraOff }" />
                真人摄像头
              </span>
              <small>主画面</small>
            </div>
          </div>

          <div ref="remoteVideoContainerRef" class="remote-audio-host" aria-hidden="true">
            <video
              ref="remoteVideoRef"
              class="remote-audio-output"
              autoplay
              playsinline
              @loadedmetadata="ensureRemoteAudioPlayback"
              @canplay="ensureRemoteAudioPlayback"
            />
          </div>

          <div class="stage-topbar">
            <div class="stage-brand">
              <span class="hiwm-live-dot" :class="{ 'is-live': streamState === 'open' }" />
              <div>
                <strong>HIWM LIVE</strong>
                <small>真人主画面</small>
              </div>
            </div>

            <span v-if="replying" class="stage-response-status">
              <i :class="{ 'is-speaking': playbackActive }" />
              {{ playbackActive ? '正在语音回答' : '正在生成语音回答…' }}
            </span>

            <div class="stage-topbar__right">
              <span class="stage-connection" :class="{ 'is-online': streamState === 'open' }">
                <i />
                {{ connectionLabel }}
              </span>
              <details class="stage-menu">
                <summary aria-label="打开会话详情">会话详情</summary>
                <div class="stage-menu__panel">
                  <div class="stage-menu__heading">
                    <div>
                      <strong>会话状态</strong>
                      <span>访客 · {{ webRTCId ? webRTCId.slice(0, 8) : '未连接' }}</span>
                    </div>
                    <span class="status-pill">
                      <i :class="{ on: analysisAuthorized }" />
                      本地分析{{ analysisAuthorized ? '已授权' : '未授权' }}
                    </span>
                  </div>
                  <dl class="stage-menu__status">
                    <div>
                      <dt>摄像头</dt>
                      <dd>{{ hasCamera && !cameraOff ? '已开启' : '已关闭' }}</dd>
                    </div>
                    <div>
                      <dt>麦克风</dt>
                      <dd>{{ hasMic && !micMuted ? '已开启' : '已关闭' }}</dd>
                    </div>
                    <div>
                      <dt>语音播报</dt>
                      <dd>{{ volumeMuted ? '已静音' : playbackActive ? '正在播放' : '已开启' }}</dd>
                    </div>
                    <div>
                      <dt>预测锁定</dt>
                      <dd>{{ lockedPrediction ? '已完成' : '等待输入' }}</dd>
                    </div>
                  </dl>
                  <section class="stage-observation">
                    <span>最新后端观察</span>
                    <p>{{ observation?.current_asr.content || '等待真实输入' }}</p>
                  </section>
                  <button type="button" class="revoke-button" @click="revokeAnalysis">
                    撤回本地分析授权
                  </button>
                </div>
              </details>
            </div>
          </div>

          <div
            class="stage-insights"
            :class="{ 'has-caption': showChatRecords && latestTranscript }"
          >
            <div class="stage-prosody-shell">
              <div class="stage-prosody-title">
                <span>声学特征</span>
                <small>音调 · 声音轮廓 · 能量</small>
              </div>
              <ProsodyTrack
                class="stage-prosody"
                :stream="mediaState.localStream"
                :enabled="analysisAuthorized && hasMic && !micMuted"
                :tts-speaking="playbackActive"
                :speech-rate-wpm="estimatedSpeechRateWpm"
                @speech-start="handleSpeechStart"
                @speech-end="handleSpeechEnd"
              />
            </div>

            <div v-if="showChatRecords && latestTranscript" class="live-caption">
              <span>{{ latestTranscript.role === 'avatar' ? '机器人' : '用户' }}</span>
              <p>
                <template
                  v-for="(segment, index) in captionSegments"
                  :key="`${index}-${segment.text}`"
                >
                  <mark
                    v-if="segment.highlighted"
                    class="task-phrase"
                    :class="segment.category ? `is-${segment.category}` : undefined"
                    :title="`任务相关内容 · ${contentCategoryLabel(segment.category || 'unknown')}`"
                  >
                    {{ segment.text }}
                  </mark>
                  <span v-else>{{ segment.text }}</span>
                </template>
              </p>
            </div>
          </div>

          <div class="stage-controls">
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
                wave-color="#148267"
                @start-chat="onStartChat"
              />
            </div>
          </div>
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

        <div v-if="visibleActions.length" :key="turnId" class="action-list">
          <div class="belief-root">
            <span>ROOT BELIEF</span>
            <strong>{{ rootBelief }}</strong>
          </div>
          <article
            v-for="(action, index) in visibleActions"
            :key="action.action_id"
            class="action-card"
            :class="{
              'is-selected': action.action_id === selectedActionId,
              'is-unselected': Boolean(selectedActionId) && action.action_id !== selectedActionId,
            }"
            :aria-label="`候选行动 ${String.fromCharCode(65 + index)}${action.action_id === selectedActionId ? '，已自动选择' : ''}`"
          >
            <div class="action-card__heading">
              <span class="action-index">{{ String.fromCharCode(65 + index) }}</span>
              <strong>{{ action.strategy }}</strong>
              <span v-if="action.action_id === selectedActionId" class="selected-badge">
                AUTO SELECTED
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
              <b>模型预测 · 演示估计</b>
              <span v-if="isProbability(action.goal_probability)">
                目标 {{ formatProbability(action.goal_probability) }}
              </span>
              <span v-if="isProbability(action.risk_probability)">
                风险 {{ formatProbability(action.risk_probability) }}
              </span>
              <span v-if="isProbability(action.information_gain)">
                信息增益 {{ formatProbability(action.information_gain) }}
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
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { message } from 'ant-design-vue'

import ActionGroup from '@/components/ActionGroup.vue'
import ChatBtn from '@/components/ChatBtn.vue'
import FaceLandmarkOverlay from '@/components/FaceLandmarkOverlay.vue'
import ProsodyTrack from '@/components/ProsodyTrack.vue'
import { useAppStore } from '@/store/app'
import { useChatStore } from '@/store/chat'
import { useHiwmStore } from '@/store/hiwm'
import { useMediaStore } from '@/store/media'
import { usePerceptionStore } from '@/store/perception'
import { useProfileStore } from '@/store/profile'
import { useVideoChatStore } from '@/store/webrtc'
import { useVisionStore } from '@/store/vision'
import {
  releaseRemoteAudioOutput,
  setRemoteAudioMuted,
  unlockRemoteAudioOutput,
} from '@/utils/remoteAudio'
import { segmentTaskRelevantTranscript } from '@/utils/transcriptHighlightUtils'

const visionState = useVisionStore()
const videoChatState = useVideoChatStore()
const chatState = useChatStore()
const hiwmState = useHiwmStore()
const appState = useAppStore()
const mediaState = useMediaStore()
const perceptionState = usePerceptionStore()
const profileState = useProfileStore()

const wrapRef = ref<HTMLDivElement>()
const localVideoContainerRef = ref<HTMLDivElement>()
const remoteVideoContainerRef = ref<HTMLDivElement>()
const localVideoRef = ref<HTMLVideoElement>()
const remoteVideoRef = ref<HTMLVideoElement>()
const speechStartedAt = ref<number | null>(null)
const lastSpeechDurationMs = ref<number | null>(null)
const profileDraft = ref(profileState.initialInformation)
let perceptionTimer: ReturnType<typeof setInterval> | null = null

const { streamState, webRTCId, chatChannelState } = storeToRefs(videoChatState)
const { volumeMuted, showChatRecords, replying, playbackActive } = storeToRefs(chatState)
const { chatRecords, inputVisible, toolsVisible, apiConfig } = storeToRefs(appState)
const { hasCamera, hasMic, micMuted, cameraOff, webcamAccessed } = storeToRefs(mediaState)
const { analysisAuthorized, face } = storeToRefs(perceptionState)
const { savedAt: profileSavedAt } = storeToRefs(profileState)
const {
  turnId,
  objective,
  observation,
  contentSignals,
  beliefs,
  actions,
  selectedActionId,
  lockedPrediction,
  error: hiwmError,
} = storeToRefs(hiwmState)

const visibleActions = computed(() => actions.value.slice(0, 3))
const beliefGroups = computed(() => [
  {
    status: 'known',
    label: '已知信息（已确认 / 已授权）',
    shortLabel: '已知',
    items: beliefs.value.filter((belief) => belief.status === 'known'),
  },
  {
    status: 'working_hypothesis',
    label: '当前关键判断（工作假设）',
    shortLabel: '假设',
    items: beliefs.value.filter((belief) => belief.status === 'working_hypothesis'),
  },
  {
    status: 'unknown',
    label: '仍然未知',
    shortLabel: '未知',
    items: beliefs.value.filter((belief) => belief.status === 'unknown'),
  },
])
const rootBelief = computed(
  () =>
    beliefs.value.find((belief) => belief.status === 'working_hypothesis')?.statement ||
    beliefs.value.find((belief) => belief.status === 'known')?.statement ||
    '等待可验证的当前判断'
)
const cameraInferenceLabel = computed(() => {
  const modalities = apiConfig.value?.hiwm?.input_modalities
  if (!modalities) return 'HIWM 输入能力信息未提供'
  return modalities.includes('image') ? '参与模型视觉推理' : '文本模型 · 摄像头不参与推理'
})
const evidenceById = computed(() => {
  if (!observation.value) return new Map()
  const evidence = [
    observation.value.current_asr,
    ...(observation.value.camera ? [observation.value.camera] : []),
    ...(observation.value.history || []),
  ]
  return new Map(evidence.map((item) => [item.evidence_id, item]))
})
const latestTranscript = computed(() => {
  const records = chatRecords.value.filter(
    (record) => record.message && !record.invalid && !record.cancelled
  )
  return records.at(-1) || null
})
const captionSegments = computed(() => {
  const transcript = latestTranscript.value
  const text = transcript?.message || '等待真实输入'
  if (!transcript || transcript.role !== 'human') {
    return segmentTaskRelevantTranscript(text, [])
  }

  const observationStreamKey = observation.value?.current_asr.stream_key
  const belongsToCurrentTurn =
    !observationStreamKey ||
    !transcript.stream_key ||
    observationStreamKey === transcript.stream_key
  return segmentTaskRelevantTranscript(text, belongsToCurrentTurn ? contentSignals.value : [])
})
const latestHumanTranscript = computed(() =>
  chatRecords.value
    .filter(
      (record) => record.role === 'human' && record.message && !record.invalid && !record.cancelled
    )
    .at(-1)
)
const estimatedSpeechRateWpm = computed(() => {
  const text = latestHumanTranscript.value?.message?.trim()
  const duration = lastSpeechDurationMs.value
  if (!text || !duration || duration < 300) return null
  const latinWords = text.match(/[A-Za-z0-9]+(?:['-][A-Za-z0-9]+)*/g)?.length ?? 0
  const cjkUnits =
    text.match(/[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}]/gu)?.length ?? 0
  const units = latinWords + cjkUnits
  return Math.min(500, Math.round((units * 60_000) / duration))
})
const connectionLabel = computed(() => {
  if (streamState.value === 'open' && chatChannelState.value === 'open') {
    return '真实会话与字幕通道在线'
  }
  if (streamState.value === 'waiting' || chatChannelState.value === 'connecting') {
    return '正在连接媒体与字幕通道'
  }
  if (chatChannelState.value === 'error') return '连接中断，可重新开始'
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
  if (remoteVideoRef.value) setRemoteAudioMuted(remoteVideoRef.value, volumeMuted.value)
  perceptionTimer = setInterval(() => {
    if (streamState.value !== 'open' || !analysisAuthorized.value) return
    videoChatState.sendClientObservation(perceptionState.toClientObservation())
  }, 500)
})

onBeforeUnmount(() => {
  if (perceptionTimer) clearInterval(perceptionTimer)
  perceptionTimer = null
  if (remoteVideoRef.value) releaseRemoteAudioOutput(remoteVideoRef.value)
  videoChatState.sendClientObservation({ consent: false })
})

watch(playbackActive, (speaking) => perceptionState.setTtsSpeaking(speaking))
watch(volumeMuted, (muted) => {
  if (remoteVideoRef.value) setRemoteAudioMuted(remoteVideoRef.value, muted)
  if (!muted) void nextTick(ensureRemoteAudioPlayback)
})

const audioSourceCallback = (): MediaStream | null => mediaState.localStream

async function ensureRemoteAudioPlayback(): Promise<void> {
  const node = remoteVideoRef.value
  if (!node?.srcObject || volumeMuted.value) return
  setRemoteAudioMuted(node, false)
  await unlockRemoteAudioOutput(node)
  try {
    await node.play()
  } catch (error) {
    console.debug('Remote voice playback is waiting for browser permission', {
      errorName: error instanceof Error ? error.name : 'UnknownError',
    })
  }
}

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

const beliefChangeLabel = (change: string): string =>
  ({
    new: '新增',
    updated: '已更新',
    unchanged: '未变',
    retracted: '已撤回 / 已反驳',
  })[change] || change

const contentCategoryLabel = (category: string): string =>
  ({
    need: '需求',
    concern: '顾虑',
    commitment: '承诺',
    question: '问题',
    unknown: '未知信息',
  })[category] || category

function handleSpeechStart(observedAt: number): void {
  speechStartedAt.value = observedAt
}

function handleSpeechEnd(observedAt: number): void {
  if (speechStartedAt.value !== null) {
    lastSpeechDurationMs.value = Math.max(1, observedAt - speechStartedAt.value)
  }
  speechStartedAt.value = null
}

async function revokeAnalysis(): Promise<void> {
  videoChatState.sendClientObservation({ consent: false })
  videoChatState.sendSessionProfile({ consent: false })
  await videoChatState.stopWebRTC(false)
  mediaState.releaseDevices()
  perceptionState.setAnalysisAuthorized(false)
}

function saveProfile(): void {
  if (profileState.save(profileDraft.value)) {
    profileDraft.value = profileState.initialInformation
    message.success('初始信息已保存在本机浏览器，将在下一次会话中发送')
    return
  }
  message.warning('请先填写至少一条用户已确认的信息')
}

function clearProfile(): void {
  profileState.clear()
  profileDraft.value = ''
  message.success('本机初始信息已清除')
}

function onStartChat(): void {
  if (streamState.value === 'closed' && remoteVideoRef.value) {
    setRemoteAudioMuted(remoteVideoRef.value, volumeMuted.value)
    void unlockRemoteAudioOutput(remoteVideoRef.value)
  }
  void videoChatState.startWebRTC()
}
</script>

<style lang="less" scoped>
@import './index.less';
</style>
