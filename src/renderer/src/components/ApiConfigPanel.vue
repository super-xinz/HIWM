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

const missingValue = (value: string | null, label = '配置缺失'): string => value || label
const formatEndpoint = (value: string | null): string => value || '未显式配置'
const formatNumber = (value: number | null, unit: string): string =>
  value === null ? '配置缺失' : `${value} ${unit}`

const commonFields = (config: PublicApiServiceConfig): ConfigField[] => [
  { label: 'Provider', value: missingValue(config.provider) },
  { label: 'Model', value: missingValue(config.model) },
  { label: 'Endpoint', value: formatEndpoint(config.endpoint) },
  { label: 'Key 环境变量', value: missingValue(config.key_env, '环境变量名缺失') },
  {
    label: 'Key 状态',
    value: config.configured === null ? '状态缺失' : config.configured ? '已配置' : '未配置',
  },
]

const asrFields = (config: PublicAsrConfig): ConfigField[] => [
  ...commonFields(config),
  { label: '采样率', value: formatNumber(config.sample_rate, 'Hz') },
  { label: '音频格式', value: missingValue(config.format) },
]

const hiwmFields = (config: PublicHiwmConfig): ConfigField[] => [
  ...commonFields(config),
  { label: '请求超时', value: formatNumber(config.timeout_seconds, 's') },
  { label: '响应格式', value: missingValue(config.response_format) },
]

const ttsFields = (config: PublicTtsConfig): ConfigField[] => [
  ...commonFields(config),
  { label: 'Voice', value: missingValue(config.voice) },
  { label: '采样率', value: formatNumber(config.sample_rate, 'Hz') },
]

const services = computed<ServiceView[]>(() => {
  const asr = apiConfig.value?.asr || null
  const hiwm = apiConfig.value?.hiwm || null
  const tts = apiConfig.value?.tts || null
  return [
    {
      id: 'asr',
      name: 'ASR',
      description: '实时语音识别',
      config: asr,
      fields: asr ? asrFields(asr) : [],
    },
    {
      id: 'hiwm',
      name: 'HIWM',
      description: '世界模型推理',
      config: hiwm,
      fields: hiwm ? hiwmFields(hiwm) : [],
    },
    {
      id: 'tts',
      name: 'TTS',
      description: '实时语音合成',
      config: tts,
      fields: tts ? ttsFields(tts) : [],
    },
  ]
})

const panelStatusLabel = computed(() => {
  if (apiConfigStatus.value === 'loading') return '正在读取真实配置'
  if (apiConfigStatus.value === 'missing') return 'API 配置未提供'
  if (apiConfigStatus.value === 'error') return 'API 配置读取失败'
  const missingCount = services.value.filter((service) => !service.config).length
  return missingCount ? `${missingCount} 个配置段缺失` : '配置已同步'
})

const sectionStatus = computed(() => {
  if (apiConfigStatus.value === 'loading') return '正在从后端读取'
  if (apiConfigStatus.value === 'missing') return '后端未提供 api_config'
  if (apiConfigStatus.value === 'error') return '无法读取该配置'
  return '后端未提供该配置段'
})

const configuredLabel = (config: PublicApiServiceConfig | null): string => {
  if (!config) return '配置缺失'
  if (config.configured === null) return '状态缺失'
  return config.configured ? '已配置' : '未配置'
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
    aria-label="真实 API 配置"
  >
    <header class="api-config-header">
      <div>
        <span class="api-config-kicker">API RUNTIME CONFIG</span>
        <h2>真实 API 配置</h2>
      </div>
      <div class="api-config-meta">
        <span v-if="apiConfig?.schema_version">Schema {{ apiConfig.schema_version }}</span>
        <span v-else>Schema 未提供</span>
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

    <footer>
      <span aria-hidden="true">●</span>
      只读脱敏配置：前端仅接收 Key 环境变量名与配置状态，不接收、保存或显示 Key 值
    </footer>
  </section>
</template>

<style lang="less" scoped>
.api-config-panel {
  --api-line: rgba(149, 220, 199, 0.2);
  --api-accent: #70e1c1;
  width: 100%;
  padding: 12px 14px;
  color: #effbf7;
  border: 1px solid var(--api-line);
  border-radius: 14px;
  background: rgba(10, 25, 23, 0.94);
  box-shadow: 0 16px 42px rgba(0, 0, 0, 0.2);

  &.is-permission-mode {
    max-width: 1180px;
    background: rgba(9, 24, 22, 0.98);
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
  font-size: 9px;
  letter-spacing: 0.15em;
}

.api-config-meta {
  justify-content: flex-end;
  gap: 7px;
  flex-wrap: wrap;

  span,
  strong {
    padding: 4px 7px;
    border: 1px solid var(--api-line);
    border-radius: 999px;
    font-size: 9px;
    font-weight: 500;
  }

  span {
    color: #91aaa3;
  }

  strong {
    color: #d7ebe6;

    &.is-ready {
      color: #a7efdb;
      border-color: rgba(112, 225, 193, 0.36);
      background: rgba(112, 225, 193, 0.08);
    }

    &.is-missing,
    &.is-error {
      color: #ffd0c7;
      border-color: rgba(255, 118, 97, 0.36);
      background: rgba(105, 31, 21, 0.22);
    }
  }
}

.api-config-error {
  margin: 0 0 9px;
  padding: 7px 9px;
  color: #ffd8d1;
  border: 1px solid rgba(255, 118, 97, 0.34);
  border-radius: 8px;
  background: rgba(105, 31, 21, 0.24);
  font-size: 10px;
}

.api-config-services {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 9px;
}

.api-service-card {
  min-width: 0;
  padding: 10px;
  border: 1px solid rgba(149, 220, 199, 0.14);
  border-radius: 10px;
  background: rgba(20, 42, 38, 0.58);

  > header {
    justify-content: space-between;
    gap: 9px;
    margin-bottom: 8px;

    > div {
      min-width: 0;
      display: flex;
      align-items: baseline;
      gap: 7px;
    }

    strong {
      color: #f1fcf8;
      font-size: 12px;
      letter-spacing: 0.08em;
    }

    div > span {
      color: #809b93;
      font-size: 9px;
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
      color: #78928a;
      font-size: 8px;
    }

    dd {
      margin: 2px 0 0;
      color: #cce1db;
      font-family: 'SFMono-Regular', Consolas, monospace;
      font-size: 9px;
      line-height: 1.35;
      overflow-wrap: anywhere;
    }
  }
}

.api-service-status {
  flex: 0 0 auto;
  padding: 3px 6px;
  border: 1px solid;
  border-radius: 999px;
  font-size: 8px;

  &.is-configured {
    color: #9debd4;
    border-color: rgba(112, 225, 193, 0.34);
    background: rgba(112, 225, 193, 0.08);
  }

  &.is-unconfigured,
  &.is-unknown {
    color: #ffc9be;
    border-color: rgba(255, 118, 97, 0.32);
    background: rgba(105, 31, 21, 0.2);
  }
}

.api-service-missing {
  min-height: 52px;
  display: grid;
  place-items: center;
  margin: 0;
  color: #af847c;
  border: 1px dashed rgba(255, 118, 97, 0.22);
  border-radius: 7px;
  font-size: 9px;
}

.api-config-panel > footer {
  margin-top: 8px;
  color: #758f87;
  font-size: 8px;

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
</style>
