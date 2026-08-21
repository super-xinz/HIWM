import assert from 'node:assert/strict'
import { test } from 'node:test'

import { parseCompanionExampleCatalog } from '../src/renderer/src/utils/companionExamples.ts'
import {
  COMPANION_SESSION_KEY,
  replaceCompanionSession,
} from '../src/renderer/src/utils/companionSession.ts'

test('example catalog keeps only public presentation fields and safe ids', () => {
  const catalog = parseCompanionExampleCatalog(
    {
      default_example_id: 'steady-guide',
      examples: [
        {
          id: 'steady-guide',
          name: '稳健规划者',
          tagline: '耐心、务实、有条理',
          description: '适合梳理复杂问题并形成下一步行动。',
          prompt_suggestions: ['帮我把今天的事情排个优先级。'],
          source_user_id: 'must-not-reach-the-view',
          implementation_notes: 'must-not-reach-the-view',
        },
        {
          id: 'unsafe/id',
          name: '不安全项',
          tagline: '不会进入目录',
          description: '非法标识应被过滤。',
          prompt_suggestions: [],
        },
      ],
    },
    'demo-xu'
  )

  assert.deepEqual(catalog, {
    defaultExampleId: 'steady-guide',
    examples: [
      {
        id: 'steady-guide',
        name: '稳健规划者',
        tagline: '耐心、务实、有条理',
        description: '适合梳理复杂问题并形成下一步行动。',
        prompt_suggestions: ['帮我把今天的事情排个优先级。'],
      },
    ],
  })
  assert.equal(JSON.stringify(catalog).includes('must-not-reach-the-view'), false)
})

test('malformed catalog retains the safe default companion', () => {
  const catalog = parseCompanionExampleCatalog(null, 'showcase-anchor')

  assert.equal(catalog.defaultExampleId, 'showcase-anchor')
  assert.equal(catalog.examples.length, 1)
  assert.equal(catalog.examples[0].id, 'showcase-anchor')
})

test('switching examples creates and persists an independent session id', () => {
  const values = new Map<string, string>([[COMPANION_SESSION_KEY, 'session-before-switch']])
  const storage = {
    getItem: (key: string): string | null => values.get(key) ?? null,
    setItem: (key: string, value: string): void => {
      values.set(key, value)
    },
  }

  const next = replaceCompanionSession(storage, () => 'session-after-switch')

  assert.equal(next, 'session-after-switch')
  assert.equal(values.get(COMPANION_SESSION_KEY), 'session-after-switch')
})
