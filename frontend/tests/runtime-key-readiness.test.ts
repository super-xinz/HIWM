import assert from 'node:assert/strict'
import test from 'node:test'

import {
  isDashscopeRuntimeKeyReady,
  isDashscopeRuntimeKeyRequired,
  type PublicApiConfig,
  type PublicApiServiceConfig,
} from '../src/renderer/src/interface/apiConfig.ts'

const service = (provider: string | null, configured: boolean | null): PublicApiServiceConfig => ({
  provider,
  configured,
  model: null,
  endpoint: null,
  key_env: provider === 'dashscope' ? 'DASHSCOPE_API_KEY' : null,
})

const config = (
  asr: PublicApiServiceConfig | null,
  hiwm: PublicApiServiceConfig | null,
  tts: PublicApiServiceConfig | null
): PublicApiConfig => ({ schema_version: '1.1', asr, hiwm, tts })

test('a classic profile with Bailian TTS can complete runtime key setup without HIWM', () => {
  const before = config(service(null, false), service(null, false), service('dashscope', false))
  const after = config(service(null, false), service(null, false), service('dashscope', true))

  assert.equal(isDashscopeRuntimeKeyRequired(before), true)
  assert.equal(isDashscopeRuntimeKeyReady(before), false)
  assert.equal(isDashscopeRuntimeKeyReady(after), true)
})

test('a profile with no DashScope services does not block the setup gate', () => {
  const localOnly = config(service('local', true), null, service('local', true))

  assert.equal(isDashscopeRuntimeKeyRequired(localOnly), false)
  assert.equal(isDashscopeRuntimeKeyReady(localOnly), true)
})
