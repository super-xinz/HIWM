import assert from 'node:assert/strict'
import { test } from 'node:test'

import { createPinia, setActivePinia } from 'pinia'

import { type HiwmTimelineEvent, useHiwmStore } from '../src/renderer/src/store/hiwm.ts'

function createStore(): ReturnType<typeof useHiwmStore> {
  setActivePinia(createPinia())
  return useHiwmStore()
}

function createTimelineEvent(sessionId: string, index: number): HiwmTimelineEvent {
  return {
    event_id: `${sessionId}:event-${index}`,
    session_id: sessionId,
    turn_id: `turn-${index}`,
    type: 'robot_response',
    occurred_at: index,
    recorded_at: index,
    source_snapshot_sha256: 'a'.repeat(64),
    payload: {
      action_id: `action-${index}`,
      strategy: 'test strategy',
      utterance: 'test utterance',
    },
  }
}

test('deleting the active session selects the newest remaining session and clears the turn', () => {
  const store = createStore()
  store.beginSession('session-a')
  store.beginSession('session-b')
  store.switchSession('session-a')
  store.turnId = 'turn-a'
  store.objective = 'active turn snapshot'

  assert.equal(store.deleteSession('session-a'), true)
  assert.deepEqual(store.timelineSessionIds, ['session-b'])
  assert.equal(store.activeSessionId, 'session-b')
  assert.equal(store.turnId, '')
  assert.equal(store.objective, '')
})

test('deleting the last session leaves no active session and clears the turn', () => {
  const store = createStore()
  store.beginSession('session-a')
  store.turnId = 'turn-a'
  store.objective = 'active turn snapshot'

  assert.equal(store.deleteSession('session-a'), true)
  assert.deepEqual(store.timelineSessionIds, [])
  assert.equal(store.activeSessionId, '')
  assert.equal(store.turnId, '')
  assert.equal(store.objective, '')
})

test('deleting a non-active session preserves the active session and turn', () => {
  const store = createStore()
  store.beginSession('session-a')
  store.beginSession('session-b')
  store.switchSession('session-a')
  store.turnId = 'turn-a'
  store.objective = 'active turn snapshot'

  assert.equal(store.deleteSession('session-b'), true)
  assert.deepEqual(store.timelineSessionIds, ['session-a'])
  assert.equal(store.activeSessionId, 'session-a')
  assert.equal(store.turnId, 'turn-a')
  assert.equal(store.objective, 'active turn snapshot')
})

test('timeline keeps only the newest 200 valid events', () => {
  const store = createStore()
  store.beginSession('session-a')

  store.appendTimelineEvents(
    'session-a',
    Array.from({ length: 201 }, (_, index) => createTimelineEvent('session-a', index))
  )

  assert.equal(store.timeline.length, 200)
  assert.equal(store.timeline[0]?.event_id, 'session-a:event-1')
  assert.equal(store.timeline[199]?.event_id, 'session-a:event-200')
})

test('timeline ignores a repeated snapshot event id', () => {
  const store = createStore()
  store.beginSession('session-a')
  const firstEvent = createTimelineEvent('session-a', 1)

  store.appendTimelineEvents('session-a', [firstEvent])
  store.appendTimelineEvents('session-a', [firstEvent, createTimelineEvent('session-a', 2)])

  assert.deepEqual(
    store.timeline.map((event) => event.event_id),
    ['session-a:event-1', 'session-a:event-2']
  )
})

test('session export is bounded to derived events and declares that raw media is absent', () => {
  const store = createStore()
  store.beginSession('session-export')
  store.appendTimelineEvents('session-export', [createTimelineEvent('session-export', 1)])

  const serialized = store.exportSession()

  assert.notEqual(serialized, null)
  const exported = JSON.parse(serialized!) as {
    schema_version: string
    session_id: string
    raw_media_included: boolean
    events: HiwmTimelineEvent[]
  }
  assert.equal(exported.schema_version, '1.0')
  assert.equal(exported.session_id, 'session-export')
  assert.equal(exported.raw_media_included, false)
  assert.deepEqual(exported.events, [createTimelineEvent('session-export', 1)])
})

test('a new store restores the active session and frozen timeline from local storage', () => {
  const values = new Map<string, string>()
  const localStorage = {
    getItem: (key: string): string | null => values.get(key) ?? null,
    setItem: (key: string, value: string): void => {
      values.set(key, value)
    },
  }
  const originalWindow = Object.getOwnPropertyDescriptor(globalThis, 'window')
  Object.defineProperty(globalThis, 'window', {
    configurable: true,
    value: { localStorage },
  })

  try {
    const firstStore = createStore()
    firstStore.beginSession('session-persisted')
    firstStore.appendTimelineEvents('session-persisted', [
      createTimelineEvent('session-persisted', 7),
    ])

    const restoredStore = createStore()

    assert.equal(restoredStore.activeSessionId, 'session-persisted')
    assert.deepEqual(restoredStore.timeline, [createTimelineEvent('session-persisted', 7)])
    assert.equal(Object.isFrozen(restoredStore.timeline[0]), true)
    assert.equal(Object.isFrozen(restoredStore.timeline[0]?.payload), true)
  } finally {
    if (originalWindow) {
      Object.defineProperty(globalThis, 'window', originalWindow)
    } else {
      delete (globalThis as { window?: unknown }).window
    }
  }
})
