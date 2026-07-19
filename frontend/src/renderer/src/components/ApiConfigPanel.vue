<script setup lang="ts">
import { computed } from 'vue'
import { storeToRefs } from 'pinia'

import type {
  PublicApiServiceConfig,
  PublicAsrConfig,
  PublicHiwmConfig,
  PublicTtsConfig,
} from '@/interface/apiConfig'
import { useAppStore } from '@/store/app'

withDefaults(
  defineProps<{
    permissionMode?: boolean
  }>(),
  {
    permissionMode: false,
  }
)

interface ConfigField {
  label: string
  value: string
}

interface ServiceView {
  id: 'asr' | 'hiwm' | 'tts'
  name: string
  description: string
  config: PublicApiServiceConfig | null
  fields: ConfigField[]
}

const appState = useAppStore()
const { apiConfig, apiConfigStatus, apiConfigError } = storeToRefs(appState)

const missingValue = (value: string | null, label = '暂不可用'): string => value || label
const formatNumber = (value: number | null, unit: string): string =>
  value === null ? '暂不可用' : `${value} ${unit}`
const formatModalities = (value: string[] | null): string => {
  if (!value) return '暂不可用'
  return value.map((modality) => ({ text: '文本', image: '图像' })[modality] || modality).join('、')
}

const commonFields = (config: PublicApiServiceConfig): ConfigField[] => [
  { label: '服务商', value: missingValue(config.provider) },
  { label: '模型', value: missingValue(config.model) },
]

const asrFields = (config: PublicAsrConfig): ConfigField[] => [
  ...commonFields(config),
  { label: '音频标准', value: formatNumber(config.sample_rate, 'Hz') },
]

const hiwmFields = (config: PublicHiwmConfig): ConfigField[] => [
  ...commonFields(config),
  { label: '支持内容', value: formatModalities(config.input_modalities) },
]

const ttsFields = (config: PublicTtsConfig): ConfigField[] => [
  ...commonFields(config),
  { label: '声音', value: missingValue(config.voice) },
]

const services = computed<ServiceView[]>(() => {
  const asr = apiConfig.value?.asr || null
  const hiwm = apiConfig.value?.hiwm || null
  const tts = apiConfig.value?.tts || null
  return [
    {
      id: 'asr',
      name: '语音识别',
      description: '将语音转成文字',
      config: asr,
      fields: asr ? asrFields(asr) : [],
    },
    {
      id: 'hiwm',
      name: '智能分析',
      description: '理解对话与画面信息',
      config: hiwm,
      fields: hiwm ? hiwmFields(hiwm) : [],
    },
    {
      id: 'tts',
      name: '语音回复',
      description: '生成自然语音回应',
      config: tts,
      fields: tts ? ttsFields(tts) : [],
    },
  ]
})

const panelStatusLabel = computed(() => {
  if (apiConfigStatus.value === 'loading') return '正在连接服务'
  if (apiConfigStatus.value === 'missing') return '服务暂不可用'
  if (apiConfigStatus.value === 'error') return '服务连接失败'
  const missingCount = services.value.filter((service) => !service.config).length
  return missingCount ? '部分服务暂不可用' : '服务已就绪'
})

const sectionStatus = computed(() => {
  if (apiConfigStatus.value === 'loading') return '正在连接'
  if (apiConfigStatus.value === 'error') return '连接失败，请稍后重试'
  return '暂不可用'
})

const configuredLabel = (config: PublicApiServiceConfig | null): string => {
  if (!config) return '暂不可用'
  if (config.configured === null) return '正在检查'
  return config.configured ? '已连接' : '正在准备'
}

const configuredClass = (config: PublicApiServiceConfig | null): string => {
  if (!config || config.configured === null) return 'is-unknown'
  return config.configured ? 'is-configured' : 'is-unconfigured'
}
</script>

<template>
  <section
    class="api-config-panel"
    :class="{ 'is-permission-mode': permissionMode }"
    aria-label="AI 服务状态"
  >
    <header class="api-config-header">
      <div>
        <span class="api-config-kicker">AI SERVICES</span>
        <h2>AI 服务状态</h2>
      </div>
      <div class="api-config-meta">
        <span>{{ services.length }} 项服务</span>
        <strong :class="`is-${apiConfigStatus}`" aria-live="polite">
          {{ panelStatusLabel }}
        </strong>
      </div>
    </header>

    <p v-if="apiConfigError" class="api-config-error" role="alert">{{ apiConfigError }}</p>

    <div class="api-config-services">
      <article v-for="service in services" :key="service.id" class="api-service-card">
        <header>
          <div>
            <strong>{{ service.name }}</strong>
            <span>{{ service.description }}</span>
          </div>
          <span class="api-service-status" :class="configuredClass(service.config)">
            {{ configuredLabel(service.config) }}
          </span>
        </header>

        <dl v-if="service.config">
          <div v-for="field in service.fields" :key="field.label">
            <dt>{{ field.label }}</dt>
            <dd :title="field.value">{{ field.value }}</dd>
          </div>
        </dl>
        <p v-else class="api-service-missing">{{ sectionStatus }}</p>
      </article>
    </div>

    <footer v-if="permissionMode">
      <span aria-hidden="true">●</span>
      AI 服务已由系统统一连接，可直接开始使用
    </footer>
    <footer v-else>
      <span aria-hidden="true">●</span>
      页面仅显示服务状态，不会展示任何访问凭证
    </footer>
  </section>
</template>

<style lang="less" scoped>
.api-config-panel {
  --api-line: #dfe7e3;
  --api-accent: #148267;
  width: 100%;
  box-sizing: border-box;
  padding: 12px 14px;
  color: #17231f;
  border: 1px solid var(--api-line);
  border-radius: 14px;
  background: #ffffff;
  box-shadow: 0 10px 30px rgba(32, 58, 49, 0.06);

  &.is-permission-mode {
    max-width: 1180px;
    background: #ffffff;
  }
}

.api-config-header,
.api-config-meta,
.api-service-card > header {
  display: flex;
  align-items: center;
}

.api-config-header {
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 10px;

  h2 {
    margin: 2px 0 0;
    font-size: 15px;
    font-weight: 620;
  }
}

.api-config-kicker {
  color: var(--api-accent);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.15em;
}

.api-config-meta {
  justify-content: flex-end;
  gap: 7px;
  flex-wrap: wrap;

  span,
  strong {
    padding: 4px 8px;
    border: 1px solid var(--api-line);
    border-radius: 999px;
    font-size: 10px;
    font-weight: 600;
    line-height: 1.35;
  }

  span {
    color: #66756f;
  }

  strong {
    color: #3f514b;

    &.is-ready {
      color: #126d57;
      border-color: #b9dfd3;
      background: #edf8f4;
    }

    &.is-missing,
    &.is-error {
      color: #a63d32;
      border-color: #efc4be;
      background: #fff5f3;
    }
  }
}

.api-config-error {
  margin: 0 0 9px;
  padding: 7px 9px;
  color: #a63d32;
  border: 1px solid #efc4be;
  border-radius: 8px;
  background: #fff5f3;
  font-size: 11px;
  line-height: 1.55;
  overflow-wrap: anywhere;
}

.api-config-services {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 9px;
}

.api-service-card {
  min-width: 0;
  padding: 10px;
  border: 1px solid var(--api-line);
  border-radius: 10px;
  background: #f8faf9;

  > header {
    align-items: flex-start;
    justify-content: space-between;
    gap: 9px;
    margin-bottom: 8px;

    > div {
      min-width: 0;
      display: flex;
      align-items: baseline;
      gap: 7px;
      flex-wrap: wrap;
    }

    strong {
      color: #17231f;
      font-size: 12px;
      letter-spacing: 0.08em;
    }

    div > span {
      color: #5f6f69;
      font-size: 10px;
      line-height: 1.4;
    }
  }

  dl {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 5px 10px;
    margin: 0;

    div {
      min-width: 0;
    }

    dt {
      color: #66756f;
      font-size: 10px;
      font-weight: 600;
      line-height: 1.35;
    }

    dd {
      margin: 2px 0 0;
      color: #3f514b;
      font-family: 'SFMono-Regular', Consolas, monospace;
      font-size: 10px;
      line-height: 1.5;
      overflow-wrap: anywhere;
    }
  }
}

.api-service-status {
  flex: 0 0 auto;
  padding: 3px 6px;
  border: 1px solid;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 650;
  line-height: 1.35;

  &.is-configured {
    color: #126d57;
    border-color: #b9dfd3;
    background: #edf8f4;
  }

  &.is-unconfigured,
  &.is-unknown {
    color: #a63d32;
    border-color: #efc4be;
    background: #fff5f3;
  }
}

.api-service-missing {
  min-height: 52px;
  display: grid;
  place-items: center;
  margin: 0;
  color: #91443e;
  border: 1px dashed #e5bdb8;
  border-radius: 7px;
  background: #fff8f7;
  font-size: 11px;
  line-height: 1.5;
}

.api-config-panel > footer {
  margin-top: 8px;
  color: #5f6f69;
  font-size: 10px;
  line-height: 1.5;

  span {
    margin-right: 5px;
    color: var(--api-accent);
  }
}

@media (max-width: 760px) {
  .api-config-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .api-config-meta {
    justify-content: flex-start;
  }

  .api-config-services {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 420px) {
  .api-config-panel {
    padding: 11px;
  }

  .api-config-meta {
    gap: 5px;
  }

  .api-service-card {
    > header {
      flex-wrap: wrap;
    }

    dl {
      grid-template-columns: 1fr;
      gap: 7px;
    }
  }
}
</style>
