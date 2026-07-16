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
  response_format: string | null
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
    response_format: readString(value.response_format),
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
    return { ok: false, reason: '后端 api_config 不是有效对象' }
  }
  if (containsForbiddenSecretField(value)) {
    return { ok: false, reason: '后端 api_config 含禁止的敏感字段，前端已拒绝载入' }
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
