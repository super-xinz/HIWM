import assert from 'node:assert/strict'
import test from 'node:test'

import { RTCSignalingError, readWebRTCAnswer } from '../src/renderer/src/utils/rtcSignaling.ts'

test('a valid SDP answer is passed through as a browser session description', async () => {
  const answer = await readWebRTCAnswer(
    Response.json({ type: 'answer', sdp: 'v=0\r\no=- 1 1 IN IP4 0.0.0.0\r\n' })
  )

  assert.deepEqual(answer, {
    type: 'answer',
    sdp: 'v=0\r\no=- 1 1 IN IP4 0.0.0.0\r\n',
  })
})

test('FastRTC concurrency errors are not passed to setRemoteDescription', async () => {
  await assert.rejects(
    readWebRTCAnswer(
      Response.json({
        status: 'failed',
        meta: { error: 'concurrency_limit_reached', limit: 1 },
      })
    ),
    (error) => {
      assert.ok(error instanceof RTCSignalingError)
      assert.equal(error.code, 'concurrency_limit_reached')
      assert.match(error.message, /上一会话仍在释放/)
      return true
    }
  )
})

test('a JSON object without answer SDP is rejected before browser parsing', async () => {
  await assert.rejects(readWebRTCAnswer(Response.json({ type: 'answer' })), (error) => {
    assert.ok(error instanceof RTCSignalingError)
    assert.equal(error.code, 'invalid_answer')
    return true
  })
})
