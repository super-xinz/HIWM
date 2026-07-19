<script setup lang="ts">
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import {
  AudioOutlined,
  SafetyCertificateOutlined,
  VideoCameraOutlined,
} from '@ant-design/icons-vue'

import ApiConfigPanel from '@/components/ApiConfigPanel.vue'
import { useAppStore } from '@/store/app'
import { useMediaStore } from '@/store/media'
import type { AnalysisConsentRecord } from '@/store/perception'
import { isDashscopeRuntimeKeyReady } from '@/interface/apiConfig'

const props = withDefaults(
  defineProps<{
    visible?: boolean
    busy?: boolean
    error?: string | null
    consentVersion?: string
  }>(),
  {
    visible: true,
    busy: false,
    error: null,
    consentVersion: 'hiwm-demo-1.0',
  }
)

const emit = defineEmits<{
  start: [decision: AnalysisConsentRecord]
}>()

const appState = useAppStore()
const mediaState = useMediaStore()
const { apiConfig, apiConfigStatus } = storeToRefs(appState)
const { permissionError } = storeToRefs(mediaState)

const keyConfigured = computed(() => isDashscopeRuntimeKeyReady(apiConfig.value))
const videoRequired = computed(() => {
  const modalities = apiConfig.value?.hiwm?.input_modalities
  return modalities ? modalities.includes('image') : true
})
const displayedError = computed(() => props.error || permissionError.value)
const canStart = computed(
  () => !props.busy && apiConfigStatus.value === 'ready' && keyConfigured.value
)
const actionLabel = computed(() => {
  if (props.busy) return '正在准备，请稍候…'
  return '同意并开始体验'
})

const createConsentId = (): string => {
  if (typeof window !== 'undefined' && typeof window.crypto?.randomUUID === 'function') {
    return window.crypto.randomUUID()
  }
  return `consent-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

const createDecision = (): AnalysisConsentRecord =>
  Object.freeze({
    consentId: createConsentId(),
    version: props.consentVersion,
    grantedAt: Date.now() / 1000,
    scopes: Object.freeze({
      aiInteraction: true,
      camera: videoRequired.value,
      microphone: true,
      localFaceSignals: videoRequired.value,
      localProsodySignals: true,
      derivedDataToBackend: true,
      recentCameraFrameToCloud: videoRequired.value,
    }),
    rawMediaStored: false,
  })

const start = (): void => {
  if (!canStart.value) return
  emit('start', createDecision())
}
</script>

<template>
  <div
    v-if="visible"
    class="setup-gate"
    role="dialog"
    aria-modal="true"
    aria-labelledby="setup-title"
  >
    <section class="setup-card">
      <div class="setup-content">
        <header class="setup-header">
          <div>
            <span class="eyebrow">GET STARTED</span>
            <h1 id="setup-title">开始使用 HIWM</h1>
            <p>
              确认所需权限，即可开始实时互动。首次使用时，浏览器会申请{{
                videoRequired ? '摄像头与麦克风' : '麦克风'
              }}权限。
            </p>
          </div>
          <span class="step-badge">快速开始</span>
        </header>

        <ApiConfigPanel permission-mode />

        <div class="setup-details">
          <section class="key-card" aria-labelledby="api-key-title">
            <div class="section-heading">
              <span class="section-index">01</span>
              <div>
                <h2 id="api-key-title">AI 服务连接</h2>
                <p>语音识别、智能分析与语音回复均已由系统统一配置。</p>
              </div>
              <span class="key-status" :class="{ configured: keyConfigured }">
                {{ keyConfigured ? '已准备就绪' : '正在连接' }}
              </span>
            </div>

            <p class="memory-note">
              <SafetyCertificateOutlined />
              AI 服务已安全连接，无需额外填写任何凭证。
            </p>
          </section>

          <section class="consent-card" aria-labelledby="consent-title">
            <div class="section-heading">
              <span class="section-index">02</span>
              <div>
                <h2 id="consent-title">权限与隐私</h2>
                <p>开始前，请确认本次体验所需的设备权限。</p>
              </div>
            </div>

            <div class="consent-grid">
              <article>
                <VideoCameraOutlined v-if="videoRequired" />
                <AudioOutlined v-else />
                <div>
                  <strong>{{ videoRequired ? '摄像头与麦克风' : '麦克风' }}</strong>
                  <span>用于实时语音和画面互动，可随时关闭。</span>
                </div>
              </article>
              <article>
                <span class="signal-icon">⌁</span>
                <div>
                  <strong>互动感知</strong>
                  <span>帮助理解面部动作、姿态和语音节奏。</span>
                </div>
              </article>
              <article>
                <span class="signal-icon">↗</span>
                <div>
                  <strong>智能分析</strong>
                  <span>
                    {{
                      videoRequired
                        ? '结合对话内容和必要的画面信息，生成实时回应与建议。'
                        : '结合对话内容生成实时回应与建议。'
                    }}
                  </span>
                </div>
              </article>
              <article>
                <span class="signal-icon">∅</span>
                <div>
                  <strong>隐私保护</strong>
                  <span>不会保存原始音频或视频，互动记录可随时清除。</span>
                </div>
              </article>
            </div>
          </section>
        </div>

        <div v-if="displayedError" class="setup-error" role="alert">
          <strong>暂时无法开始</strong>
          <span>{{ displayedError }}</span>
        </div>
      </div>

      <footer class="setup-footer">
        <p>点击后将申请设备权限，授权成功后自动进入互动页面。</p>
        <button type="button" class="start-button" :disabled="!canStart" @click="start">
          <span>{{ actionLabel }}</span>
          <span aria-hidden="true">→</span>
        </button>
      </footer>
    </section>
  </div>
</template>

<style scoped lang="less">
.setup-gate {
  position: fixed;
  z-index: 1200;
  inset: 0;
  display: grid;
  place-items: center;
  box-sizing: border-box;
  padding: 22px;
  overflow: auto;
  color: #17231f;
  background:
    radial-gradient(circle at 12% 8%, rgba(20, 130, 103, 0.08), transparent 28%),
    rgba(245, 247, 246, 0.97);
  backdrop-filter: blur(14px);
}

.setup-card {
  width: min(1180px, 100%);
  max-height: calc(100vh - 44px);
  max-height: calc(100dvh - 44px);
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  padding: 22px;
  overflow: hidden;
  border: 1px solid #dce6e1;
  border-radius: 20px;
  background: #fff;
  box-shadow: 0 28px 90px rgba(32, 58, 49, 0.16);
}

.setup-content {
  min-height: 0;
  padding-right: 4px;
  overflow-y: auto;
  overscroll-behavior: contain;
}

.setup-header,
.setup-footer,
.section-heading {
  display: flex;
  align-items: center;
}

.setup-header {
  justify-content: space-between;
  gap: 24px;
  margin-bottom: 16px;

  h1 {
    margin: 4px 0 4px;
    font-size: clamp(23px, 2.5vw, 31px);
    line-height: 1.25;
  }

  p {
    margin: 0;
    color: #596a64;
    font-size: 13px;
    line-height: 1.55;
  }
}

.eyebrow {
  color: #148267;
  font-size: 10px;
  font-weight: 750;
  letter-spacing: 0.17em;
}

.step-badge,
.key-status {
  flex: 0 0 auto;
  padding: 5px 10px;
  border: 1px solid #b9dfd3;
  border-radius: 999px;
  color: #126d57;
  background: #edf8f4;
  font-size: 11px;
  font-weight: 700;
}

.setup-details {
  display: grid;
  grid-template-columns: minmax(0, 0.95fr) minmax(0, 1.05fr);
  gap: 12px;
  margin-top: 12px;
}

.key-card,
.consent-card {
  min-width: 0;
  padding: 15px;
  border: 1px solid #dfe7e3;
  border-radius: 14px;
  background: #f8faf9;
}

.section-heading {
  align-items: flex-start;
  gap: 10px;

  > div {
    min-width: 0;
    flex: 1;
  }

  h2 {
    margin: 0;
    font-size: 14px;
    line-height: 1.45;
  }

  p {
    margin: 3px 0 0;
    color: #65756f;
    font-size: 11px;
    line-height: 1.45;
  }
}

.section-index {
  flex: 0 0 auto;
  color: #148267;
  font:
    700 11px/1.5 'SFMono-Regular',
    Consolas,
    monospace;
}

.key-status {
  color: #7a5d14;
  border-color: #ead9a5;
  background: #fff9e8;

  &.configured {
    color: #126d57;
    border-color: #b9dfd3;
    background: #edf8f4;
  }
}

.key-input-wrap {
  position: relative;
  display: block;
  margin-top: 13px;

  input {
    width: 100%;
    height: 46px;
    box-sizing: border-box;
    padding: 0 46px 0 13px;
    color: #24352f;
    border: 1px solid #cfdcd6;
    border-radius: 10px;
    background: #fff;
    font-family: 'SFMono-Regular', Consolas, monospace;
    font-size: 13px;
    outline: none;

    &:focus {
      border-color: #148267;
      box-shadow: 0 0 0 3px rgba(20, 130, 103, 0.14);
    }

    &::placeholder {
      color: #96a39e;
    }
  }
}

.reveal-button {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 38px;
  height: 38px;
  padding: 0;
  color: #65756f;
  border: 0;
  border-radius: 8px;
  background: transparent;
  cursor: pointer;

  &:hover,
  &:focus-visible {
    color: #148267;
    background: #edf8f4;
    outline: none;
  }
}

.access-token-field {
  display: grid;
  gap: 6px;
  margin-top: 11px;

  label {
    color: #344a42;
    font-size: 11px;
    font-weight: 700;
  }

  input {
    width: 100%;
    height: 42px;
    box-sizing: border-box;
    padding: 0 13px;
    color: #24352f;
    border: 1px solid #cfdcd6;
    border-radius: 10px;
    background: #fff;
    font-family: 'SFMono-Regular', Consolas, monospace;
    font-size: 12px;
    outline: none;

    &:focus {
      border-color: #148267;
      box-shadow: 0 0 0 3px rgba(20, 130, 103, 0.14);
    }
  }

  small {
    color: #65756f;
    font-size: 10px;
    line-height: 1.45;
  }
}

.memory-note {
  display: flex;
  gap: 7px;
  align-items: flex-start;
  margin: 10px 0 0;
  color: #527067;
  font-size: 11px;
  line-height: 1.5;

  :deep(svg) {
    margin-top: 2px;
    color: #148267;
  }
}

.consent-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin-top: 12px;

  article {
    min-width: 0;
    display: flex;
    gap: 9px;
    align-items: flex-start;
    padding: 9px;
    border: 1px solid #e3e9e6;
    border-radius: 9px;
    background: #fff;

    > :deep(svg),
    .signal-icon {
      flex: 0 0 auto;
      width: 17px;
      color: #148267;
      font-size: 15px;
      line-height: 1.25;
      text-align: center;
    }

    div {
      min-width: 0;
      display: grid;
      gap: 2px;
    }

    strong {
      font-size: 11px;
      line-height: 1.4;
    }

    span:not(.signal-icon) {
      color: #65756f;
      font-size: 10px;
      line-height: 1.45;
    }
  }
}

.setup-error {
  display: grid;
  gap: 3px;
  margin-top: 12px;
  padding: 10px 12px;
  color: #8a302b;
  border: 1px solid #edc9c6;
  border-radius: 10px;
  background: #fff1ef;

  strong {
    font-size: 12px;
  }

  span {
    font-size: 11px;
    line-height: 1.5;
  }
}

.setup-footer {
  flex: 0 0 auto;
  justify-content: space-between;
  gap: 18px;
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid #e4ebe8;
  background: #fff;

  p {
    max-width: 650px;
    margin: 0;
    color: #65756f;
    font-size: 11px;
    line-height: 1.55;
  }
}

.start-button {
  min-width: 260px;
  min-height: 46px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 11px 18px;
  color: #fff;
  border: 1px solid #148267;
  border-radius: 10px;
  background: #148267;
  font-size: 13px;
  font-weight: 750;
  line-height: 1.35;
  cursor: pointer;
  box-shadow: 0 10px 24px rgba(20, 130, 103, 0.2);

  &:hover:not(:disabled),
  &:focus-visible:not(:disabled) {
    border-color: #0f6f58;
    background: #0f765e;
    outline: none;
  }

  &:focus-visible:not(:disabled) {
    box-shadow:
      0 10px 24px rgba(20, 130, 103, 0.2),
      0 0 0 3px rgba(20, 130, 103, 0.2);
  }

  &:disabled {
    cursor: not-allowed;
    opacity: 0.52;
    box-shadow: none;
  }
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

@media (max-width: 900px) {
  .setup-details {
    grid-template-columns: 1fr;
  }

  .setup-footer {
    align-items: stretch;
    flex-direction: column;
  }

  .start-button {
    width: 100%;
  }
}

@media (max-width: 640px) {
  .setup-gate {
    place-items: start center;
    padding: 8px;
  }

  .setup-card {
    max-height: calc(100vh - 16px);
    max-height: calc(100dvh - 16px);
    padding: 14px;
    border-radius: 14px;
  }

  .setup-header {
    align-items: flex-start;
  }

  .step-badge {
    display: none;
  }

  .section-heading {
    flex-wrap: wrap;
  }

  .key-status {
    margin-left: 27px;
  }

  .consent-grid {
    grid-template-columns: 1fr;
  }

  .start-button {
    min-width: 0;
  }
}
</style>
