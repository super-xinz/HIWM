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
const formatModalities = (value: string[] | null): string => {
  if (!value) return '能力信息缺失'
  return value.map((modality) => ({ text: '文本', image: '图像' })[modality] || modality).join('、')
}
const formatSupport = (value: boolean | null): string => {
  if (value === null) return '能力信息缺失'
  return value ? '支持' : '不支持'
}

const commonFields = (config: PublicApiServiceConfig): ConfigField[] => [
  { label: 'Provider', value: missingValue(config.provider) },
  { label: 'Model', value: missingValue(config.model) },
  { label: 'Endpoint', value: formatEndpoint(config.endpoint) },
  { label: 'Key 配置槽', value: missingValue(config.key_env, '配置槽名称缺失') },
  {
    label: 'Key 状态',
    value:
      config.configured === null ? '状态缺失' : config.configured ? '已加载（未验证）' : '未配置',
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
  {
    label: 'Temperature',
    value: config.temperature === null ? '配置缺失' : String(config.temperature),
  },
  {
    label: '流式响应',
    value: config.streaming === null ? '配置缺失' : config.streaming ? '已启用' : '已关闭',
  },
  { label: '输入模态', value: formatModalities(config.input_modalities) },
  { label: 'Structured Output', value: formatSupport(config.structured_output) },
  {
    label: '思考模式',
    value:
      config.thinking_enabled === null ? '配置缺失' : config.thinking_enabled ? '已启用' : '已关闭',
  },
  {
    label: '响应格式参数',
    value: config.response_format || '未启用',
  },
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
  return config.configured ? 'Key 已加载' : '未配置'
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

    <footer v-if="permissionMode">
      <span aria-hidden="true">●</span>
      配置详情始终脱敏；你在本页提交的 Key 只进入本机服务内存，不写入 .env 或浏览器存储
    </footer>
    <footer v-else>
      <span aria-hidden="true">●</span>
      只读脱敏配置：Key
      已加载仅代表环境变量存在，不代表余额与模型权限已通过验证；前端不接收、保存或显示 Key 值
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
