import assert from 'node:assert/strict'
import { test } from 'node:test'

import { createPinia, setActivePinia } from 'pinia'

import { useProfileStore } from '../src/renderer/src/store/profile.ts'

function createStore(): ReturnType<typeof useProfileStore> {
  setActivePinia(createPinia())
  return useProfileStore()
}

test('initial profile saves, restores after a new store, and clears without residue', () => {
  const values = new Map<string, string>()
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
    value: {
      localStorage,
      crypto: { randomUUID: () => 'profile-test-id' },
    },
  })

  try {
    const firstStore = createStore()
    assert.equal(firstStore.hasProfile, false)
    assert.equal(firstStore.save('  已确认预算需要审批。  '), true)
    assert.equal(firstStore.initialInformation, '已确认预算需要审批。')
    assert.deepEqual(firstStore.toClientPayload(), {
      consent: true,
      profile_id: 'profile-test-id',
      initial_information: '已确认预算需要审批。',
    })

    const restoredStore = createStore()
    assert.equal(restoredStore.hasProfile, true)
    assert.equal(restoredStore.initialInformation, '已确认预算需要审批。')
    assert.equal(restoredStore.profileId, 'profile-test-id')

    restoredStore.clear()
    assert.equal(values.size, 0)
    assert.deepEqual(restoredStore.toClientPayload(), { consent: false })

    const afterClearStore = createStore()
    assert.equal(afterClearStore.hasProfile, false)
    assert.equal(afterClearStore.initialInformation, '')
  } finally {
    if (originalWindow) {
      Object.defineProperty(globalThis, 'window', originalWindow)
    } else {
      delete (globalThis as { window?: unknown }).window
    }
  }
})
