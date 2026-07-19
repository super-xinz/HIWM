import assert from 'node:assert/strict'
import { test } from 'node:test'

import { segmentTaskRelevantTranscript } from '../src/renderer/src/utils/transcriptHighlightUtils.ts'

test('highlights traceable task phrases and preserves the original transcript', () => {
  const transcript = '实施太慢，而且预算要审批，我们下周再确认。'
  const segments = segmentTaskRelevantTranscript(transcript, [
    {
      id: 'concern-1',
      category: 'concern',
      statement: '客户明确表示实施太慢',
    },
    {
      id: 'unknown-1',
      category: 'unknown',
      statement: '“预算要审批”仍是未知约束',
    },
  ])

  assert.equal(segments.map((segment) => segment.text).join(''), transcript)
  assert.deepEqual(
    segments.filter((segment) => segment.highlighted).map((segment) => segment.text),
    ['实施太慢', '预算要审批']
  )
})

test('does not mark paraphrases or generic signal words that are not traceable verbatim', () => {
  const transcript = '方案价格还需要内部讨论。'
  const segments = segmentTaskRelevantTranscript(transcript, [
    { id: 'concern-1', category: 'concern', statement: '客户存在成本顾虑' },
    { id: 'generic-1', category: 'question', statement: '问题' },
  ])

  assert.deepEqual(segments, [{ text: transcript, highlighted: false }])
})

test('keeps markup-looking input as inert plain text segments', () => {
  const transcript = '<img src=x onerror=alert(1)>预算要审批'
  const segments = segmentTaskRelevantTranscript(transcript, [
    { id: 'unknown-1', category: 'unknown', statement: '预算要审批' },
  ])

  assert.equal(segments.map((segment) => segment.text).join(''), transcript)
  assert.equal(segments[0].text, '<img src=x onerror=alert(1)>')
  assert.equal(segments[0].highlighted, false)
})
