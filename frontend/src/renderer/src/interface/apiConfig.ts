export type ApiConfigLoadState = 'loading' | 'ready' | 'missing' | 'error'

export interface PublicApiServiceConfig {
  provider: string | null
  model: string | null
  endpoint: string | null
  key_env: string | null
  configured: boolean | null
}

export interface PublicAsrConfig extends PublicApiServiceConfig {
  sample_rate: number | null
  format: string | null
}

export interface PublicHiwmConfig extends PublicApiServiceConfig {
  timeout_seconds: number | null
  temperature: number | null
  streaming: boolean | null
  response_format: string | null
  input_modalities: string[] | null
  structured_output: boolean | null
  thinking_enabled: boolean | null
}

export interface PublicTtsConfig extends PublicApiServiceConfig {
  voice: string | null
  sample_rate: number | null
}

export interface PublicApiConfig {
  schema_version: string | null
  asr: PublicAsrConfig | null
  hiwm: PublicHiwmConfig | null
  tts: PublicTtsConfig | null
}

const DASHSCOPE_KEY_ENV = 'DASHSCOPE_API_KEY'

export const dashscopeRuntimeServices = (
  config: PublicApiConfig | null
): PublicApiServiceConfig[] => {
  if (!config) return []
  const services: Array<PublicApiServiceConfig | null> = [config.asr, config.hiwm, config.tts]
  return services.filter(
    (service): service is PublicApiServiceConfig =>
      service?.provider === 'dashscope' && service.key_env === DASHSCOPE_KEY_ENV
  )
}

export const isDashscopeRuntimeKeyRequired = (config: PublicApiConfig | null): boolean =>
  config === null || dashscopeRuntimeServices(config).length > 0

export const isDashscopeRuntimeKeyReady = (config: PublicApiConfig | null): boolean => {
  if (!config) return false
  const services = dashscopeRuntimeServices(config)
  return services.length === 0 || services.every((service) => service.configured === true)
}

export type PublicApiConfigParseResult =
  | { ok: true; config: PublicApiConfig }
  | { ok: false; reason: string }

const forbiddenSecretFieldNames = new Set([
  'apikey',
  'key',
  'token',
  'secret',
  'password',
  'accesskey',
  'accesstoken',
  'authorization',
])

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)

const readString = (value: unknown): string | null =>
  typeof value === 'string' && value.trim() ? value.trim() : null

const readEnvironmentName = (value: unknown): string | null => {
  const name = readString(value)
  return name && /^[A-Z_][A-Z0-9_]{0,127}$/.test(name) ? name : null
}

const readNumber = (value: unknown): number | null =>
  typeof value === 'number' && Number.isFinite(value) ? value : null

const readConfigured = (value: unknown): boolean | null =>
  typeof value === 'boolean' ? value : null

const readStringArray = (value: unknown): string[] | null => {
  if (!Array.isArray(value)) return null
  const strings = value.map(readString)
  return strings.every((item): item is string => item !== null) ? strings : null
}

const containsForbiddenSecretField = (value: unknown): boolean => {
  if (Array.isArray(value)) return value.some(containsForbiddenSecretField)
  if (!isRecord(value)) return false

  return Object.entries(value).some(([key, nestedValue]) => {
    const normalizedKey = key.replace(/[-_]/g, '').toLowerCase()
    return forbiddenSecretFieldNames.has(normalizedKey) || containsForbiddenSecretField(nestedValue)
  })
}

const parseBaseConfig = (value: Record<string, unknown>): PublicApiServiceConfig => ({
  provider: readString(value.provider),
  model: readString(value.model),
  endpoint: readString(value.endpoint),
  key_env: readEnvironmentName(value.key_env),
  configured: readConfigured(value.configured),
})

const parseAsrConfig = (value: unknown): PublicAsrConfig | null => {
  if (!isRecord(value)) return null
  return {
    ...parseBaseConfig(value),
    sample_rate: readNumber(value.sample_rate),
    format: readString(value.format),
  }
}

const parseHiwmConfig = (value: unknown): PublicHiwmConfig | null => {
  if (!isRecord(value)) return null
  return {
    ...parseBaseConfig(value),
    timeout_seconds: readNumber(value.timeout_seconds),
    temperature: readNumber(value.temperature),
    streaming: readConfigured(value.streaming),
    response_format: readString(value.response_format),
    input_modalities: readStringArray(value.input_modalities),
    structured_output: readConfigured(value.structured_output),
    thinking_enabled: readConfigured(value.thinking_enabled),
  }
}

const parseTtsConfig = (value: unknown): PublicTtsConfig | null => {
  if (!isRecord(value)) return null
  return {
    ...parseBaseConfig(value),
    voice: readString(value.voice),
    sample_rate: readNumber(value.sample_rate),
  }
}

export const parsePublicApiConfig = (value: unknown): PublicApiConfigParseResult => {
  if (!isRecord(value)) {
    return { ok: false, reason: '服务配置暂时无法识别' }
  }
  if (containsForbiddenSecretField(value)) {
    return { ok: false, reason: '服务配置校验失败，请稍后重试' }
  }

  return {
    ok: true,
    config: {
      schema_version: readString(value.schema_version),
      asr: parseAsrConfig(value.asr),
      hiwm: parseHiwmConfig(value.hiwm),
      tts: parseTtsConfig(value.tts),
    },
  }
}
