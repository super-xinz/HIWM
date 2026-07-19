import assert from 'node:assert/strict'
import { test } from 'node:test'

import { isDisplayableChatRecord } from '../src/renderer/src/utils/evidenceStreamUtils.ts'

test('chat evidence excludes invalid and cancelled records while preserving partial and final records', () => {
  const records = [
    { id: 'invalid', message: '作废字幕', invalid: true, final: true },
    { id: 'cancelled', message: '已中断字幕', cancelled: true, final: true },
    { id: 'partial', message: '正常实时字幕', final: false },
    { id: 'final', message: '正常已确认字幕', final: true },
  ]

  const displayed = records.filter(isDisplayableChatRecord)

  assert.deepEqual(
    displayed.map((record) => record.id),
    ['partial', 'final']
  )
  assert.equal(displayed[0].final, false)
  assert.equal(displayed[1].final, true)
})
