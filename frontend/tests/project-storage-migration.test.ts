import assert from 'node:assert/strict'
import { test } from 'node:test'

import {
  HIWM_AUTH_STORAGE_KEY,
  HIWM_PROFILE_STORAGE_KEY,
  LEGACY_AUTH_STORAGE_KEYS,
  LEGACY_PROFILE_STORAGE_KEYS,
  readMigratedStorage,
  readRuntimeControlToken,
  writeRuntimeControlToken,
} from '../src/renderer/src/utils/projectStorage.ts'

test('legacy browser keys migrate once into the HIWM namespace', () => {
  const values = new Map<string, string>([
    [LEGACY_AUTH_STORAGE_KEYS[0], 'legacy-access-token'],
    [LEGACY_PROFILE_STORAGE_KEYS[0], '{"schema_version":"1.0"}'],
  ])
  const localStorage = {
    getItem: (key: string): string | null => values.get(key) ?? null,
    setItem: (key: string, value: string): void => {
      values.set(key, value)
    },
    removeItem: (key: string): void => {
      values.delete(key)
    },
  }
  const originalWindow = Object.getOwnPropertyDescriptor(globalThis, 'window')
  Object.defineProperty(globalThis, 'window', {
    configurable: true,
    value: { localStorage },
  })

  try {
    assert.equal(readRuntimeControlToken(), 'legacy-access-token')
    assert.equal(values.get(HIWM_AUTH_STORAGE_KEY), 'legacy-access-token')
    assert.equal(values.has(LEGACY_AUTH_STORAGE_KEYS[0]), false)

    assert.equal(
      readMigratedStorage(HIWM_PROFILE_STORAGE_KEY, LEGACY_PROFILE_STORAGE_KEYS),
      '{"schema_version":"1.0"}'
    )
    assert.equal(values.has(LEGACY_PROFILE_STORAGE_KEYS[0]), false)

    writeRuntimeControlToken('  new-access-token  ')
    assert.equal(values.get(HIWM_AUTH_STORAGE_KEY), 'new-access-token')
    writeRuntimeControlToken('')
    assert.equal(values.has(HIWM_AUTH_STORAGE_KEY), false)
  } finally {
    if (originalWindow) {
      Object.defineProperty(globalThis, 'window', originalWindow)
    } else {
      delete (globalThis as { window?: unknown }).window
    }
  }
})
