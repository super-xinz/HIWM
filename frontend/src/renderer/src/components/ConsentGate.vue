<script setup lang="ts">
import { ref, watch } from 'vue'
import type { AnalysisConsentRecord } from '@/store/perception'

const props = withDefaults(
  defineProps<{
    visible?: boolean
    busy?: boolean
    consentVersion?: string
    derivedRetentionLabel?: string
    allowCancel?: boolean
  }>(),
  {
    visible: true,
    busy: false,
    consentVersion: '1.0',
    derivedRetentionLabel: '仅保留当前会话所需的转录、特征摘要与派生事件',
    allowCancel: true,
  }
)

const emit = defineEmits<{
  authorize: [decision: AnalysisConsentRecord]
  cancel: []
}>()

const acknowledged = ref(false)

watch(
  () => props.visible,
  () => {
    acknowledged.value = false
  }
)

const createConsentId = (): string => {
  if (typeof window !== 'undefined' && typeof window.crypto?.randomUUID === 'function') {
    return window.crypto.randomUUID()
  }
  return `consent-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

const authorize = (): void => {
  if (!acknowledged.value || props.busy) return
  emit(
    'authorize',
    Object.freeze({
      consentId: createConsentId(),
      version: props.consentVersion,
      grantedAt: Date.now() / 1000,
      scopes: Object.freeze({
        aiInteraction: true,
        camera: true,
        microphone: true,
        localFaceSignals: true,
        localProsodySignals: true,
        derivedDataToBackend: true,
        recentCameraFrameToCloud: true,
      }),
      rawMediaStored: false,
    })
  )
}
</script>

<template>
  <div
    v-if="visible"
    class="consent-gate"
    role="dialog"
    aria-modal="true"
    aria-labelledby="consent-title"
  >
    <section class="consent-card">
      <header>
        <span class="eyebrow">PRIVACY &amp; CONSENT</span>
        <h2 id="consent-title">启动 AI 交互分析前，请先明确授权</h2>
        <p>
          只有点击“同意并继续”后，上层页面才可以申请设备权限。本组件自身不会打开摄像头或麦克风。
        </p>
      </header>

      <div class="consent-items">
        <article>
          <span aria-hidden="true">01</span>
          <div>
            <h3>AI 交互</h3>
            <p>对话由 AI 虚拟人参与，并会用于当前会话的交互预测与响应生成。</p>
          </div>
        </article>
        <article>
          <span aria-hidden="true">02</span>
          <div>
            <h3>摄像头与麦克风</h3>
            <p>授权后，应用可在对话期间读取视频与声音；你可以随时结束会话或关闭设备。</p>
          </div>
        </article>
        <article>
          <span aria-hidden="true">03</span>
          <div>
            <h3>本地派生特征</h3>
            <p>
              面部点位、头部姿态和语音韵律信号优先在本地计算，它们只表示可观察的交互线索。你主动填写的初始信息会保存在本机，直到主动清除。
            </p>
          </div>
        </article>
        <article>
          <span aria-hidden="true">04</span>
          <div>
            <h3>发送到后端的内容</h3>
            <p>
              语音转录、你主动填写的初始信息、受限的派生特征摘要和最近一帧摄像头画面会发送到百炼云端模型，用于当前会话的预测、评估和回应。
            </p>
          </div>
        </article>
      </div>

      <div class="privacy-note">
        <strong>默认不保存原始音视频</strong>
        <p>
          {{ derivedRetentionLabel }}。派生事件会保存在本机浏览器中（每个会话最多 200
          条），直到你点击“删除会话”或清理浏览器数据；服务端的预测锁记录会同步执行删除。不将视觉或语音线索宣称为对内心状态的事实判定。
        </p>
      </div>

      <label class="acknowledge">
        <input v-model="acknowledged" type="checkbox" :disabled="busy" />
        <span>我已了解上述用途，并同意在本次会话中启用这些功能。</span>
      </label>

      <footer>
        <button
          v-if="allowCancel"
          type="button"
          class="secondary"
          :disabled="busy"
          @click="emit('cancel')"
        >
          取消
        </button>
        <button type="button" class="primary" :disabled="!acknowledged || busy" @click="authorize">
          {{ busy ? '正在处理…' : '同意并继续' }}
        </button>
      </footer>
    </section>
  </div>
</template>

<style scoped lang="less">
.consent-gate {
  position: fixed;
  z-index: 1200;
  inset: 0;
  display: grid;
  place-items: center;
  padding: 24px;
  overflow: hidden;
  color: #17231f;
  background: rgba(245, 247, 246, 0.94);
  backdrop-filter: blur(14px);
}

.consent-card {
  width: min(760px, 100%);
  max-height: calc(100vh - 48px);
  max-height: calc(100dvh - 48px);
  box-sizing: border-box;
  padding: 26px;
  overflow-y: auto;
  overscroll-behavior: contain;
  border: 1px solid #dfe7e3;
  border-radius: 18px;
  background: #ffffff;
  box-shadow: 0 24px 72px rgba(32, 58, 49, 0.14);

  header h2 {
    margin: 6px 0 8px;
    font-size: clamp(20px, 3vw, 28px);
    line-height: 1.3;
  }

  header p,
  article p,
  .privacy-note p {
    margin: 0;
    color: #596a64;
    font-size: 14px;
    line-height: 1.65;
  }
}

.eyebrow {
  color: #148267;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.14em;
}

.consent-items {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin: 22px 0 14px;

  article {
    display: flex;
    gap: 12px;
    padding: 14px;
    border: 1px solid #dfe7e3;
    border-radius: 12px;
    background: #f8faf9;

    > span {
      color: #148267;
      font:
        700 12px/1.5 ui-monospace,
        monospace;
    }

    h3 {
      margin: 0 0 5px;
      font-size: 14px;
    }
  }
}

.privacy-note {
  padding: 14px 16px;
  border-left: 3px solid #148267;
  border-radius: 0 10px 10px 0;
  background: #edf8f4;

  strong {
    display: block;
    margin-bottom: 4px;
    color: #126d57;
  }
}

.acknowledge {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  margin: 18px 0;
  color: #273a33;
  font-size: 14px;
  line-height: 1.5;
  cursor: pointer;

  input {
    flex: 0 0 auto;
    width: 18px;
    height: 18px;
    margin-top: 2px;
    accent-color: #148267;
  }
}

footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;

  button {
    min-width: 112px;
    min-height: 44px;
    padding: 10px 16px;
    color: #33443e;
    border: 1px solid #d6e0dc;
    border-radius: 9px;
    background: transparent;
    font-size: 14px;
    font-weight: 600;
    line-height: 1.35;
    cursor: pointer;

    &.primary {
      color: #ffffff;
      border-color: #148267;
      background: #148267;
      font-weight: 700;
    }

    &:disabled {
      cursor: not-allowed;
      opacity: 0.55;
    }

    &:focus-visible {
      outline: 3px solid rgba(20, 130, 103, 0.22);
      outline-offset: 2px;
    }
  }
}

@media (max-width: 640px) {
  .consent-gate {
    place-items: start center;
    padding: 10px;
  }

  .consent-card {
    max-height: calc(100vh - 20px);
    max-height: calc(100dvh - 20px);
    padding: 18px 16px;
  }

  .consent-items {
    grid-template-columns: 1fr;
    margin-top: 16px;
  }

  footer {
    button {
      flex: 1 1 0;
      min-width: 0;
    }
  }
}

@media (max-height: 760px) and (min-width: 641px) {
  .consent-gate {
    padding: 12px;
  }

  .consent-card {
    padding: 18px 22px;

    header h2 {
      margin: 3px 0 5px;
    }
  }

  .consent-items {
    margin: 12px 0 10px;

    article {
      padding: 10px 12px;
    }
  }

  .privacy-note {
    padding: 10px 14px;
  }

  .acknowledge {
    margin: 10px 0;
  }
}
</style>
