import assert from 'node:assert/strict'
import test from 'node:test'

import {
  COMPANION_SESSION_KEY,
  loadOrCreateCompanionSession,
} from '../src/renderer/src/utils/companionSession.ts'
import { extractSseFrames } from '../src/renderer/src/utils/sse.ts'

test('split SSE chunks emit each delta exactly once', () => {
  let buffer = 'data: {"type":"delta","content":"你'
  let parsed = extractSseFrames(buffer)
  assert.deepEqual(parsed.events, [])

  buffer = parsed.rest + '好"}\n\ndata: {"type":"delta","content":"！"}\n\n'
  parsed = extractSseFrames(buffer)
  assert.deepEqual(parsed.events, [
    { type: 'delta', content: '你好' },
    { type: 'delta', content: '！' },
  ])
  assert.equal(parsed.rest, '')
})

test('invalid SSE JSON becomes a visible safe error event', () => {
  const parsed = extractSseFrames('data: not-json\n\n')
  assert.equal(parsed.events[0]?.type, 'error')
  assert.equal(parsed.events[0]?.code, 'invalid_stream_event')
})

test('the first companion session is persisted and restored', () => {
  const values = new Map<string, string>()
  const storage = {
    getItem: (key: string): string | null => values.get(key) || null,
    setItem: (key: string, value: string): void => {
      values.set(key, value)
    },
  }
  assert.equal(
    loadOrCreateCompanionSession(storage, () => 'session-first'),
    'session-first'
  )
  assert.equal(values.get(COMPANION_SESSION_KEY), 'session-first')
  assert.equal(
    loadOrCreateCompanionSession(storage, () => 'session-second'),
    'session-first'
  )
})
