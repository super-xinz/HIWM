import assert from 'node:assert/strict'
import test from 'node:test'

import {
  RTCReadinessError,
  waitForRTCReady,
} from '../src/renderer/src/utils/rtcReadiness.ts'

class FakePeerConnection extends EventTarget {
  connectionState: RTCPeerConnectionState = 'new'
  iceConnectionState: RTCIceConnectionState = 'new'

  connect(): void {
    this.connectionState = 'connected'
    this.iceConnectionState = 'connected'
    this.dispatchEvent(new Event('connectionstatechange'))
  }
}

class FakeDataChannel extends EventTarget {
  readyState: RTCDataChannelState = 'connecting'

  open(): void {
    this.readyState = 'open'
    this.dispatchEvent(new Event('open'))
  }

  closeBeforeReady(): void {
    this.readyState = 'closed'
    this.dispatchEvent(new Event('close'))
  }
}

test('RTC readiness requires both a connected peer and an open text channel', async () => {
  const peer = new FakePeerConnection()
  const channel = new FakeDataChannel()
  let resolved = false
  const readiness = waitForRTCReady(
    peer as unknown as RTCPeerConnection,
    channel as unknown as RTCDataChannel,
    100
  ).then(() => {
    resolved = true
  })

  channel.open()
  await new Promise((resolve) => setImmediate(resolve))
  assert.equal(resolved, false)

  peer.connect()
  await readiness
  assert.equal(resolved, true)
})

test('a text channel that closes during setup fails visibly', async () => {
  const peer = new FakePeerConnection()
  const channel = new FakeDataChannel()
  const readiness = waitForRTCReady(
    peer as unknown as RTCPeerConnection,
    channel as unknown as RTCDataChannel,
    100
  )

  peer.connect()
  channel.closeBeforeReady()

  await assert.rejects(readiness, (error) => {
    assert.ok(error instanceof RTCReadinessError)
    assert.match(error.message, /字幕与控制通道/)
    return true
  })
})

test('RTC readiness times out instead of reporting a false online state', async () => {
  const peer = new FakePeerConnection()
  const channel = new FakeDataChannel()

  await assert.rejects(
    waitForRTCReady(
      peer as unknown as RTCPeerConnection,
      channel as unknown as RTCDataChannel,
      5
    ),
    (error) => {
      assert.ok(error instanceof RTCReadinessError)
      assert.match(error.message, /连接超时/)
      return true
    }
  )
})
