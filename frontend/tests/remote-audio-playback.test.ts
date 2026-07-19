import assert from 'node:assert/strict'
import test from 'node:test'

import {
  attachAndPlayRemoteMedia,
  releaseRemoteAudioOutput,
  setRemoteAudioMuted,
  type RemoteMediaPlaybackNode,
  unlockRemoteAudioOutput,
} from '../src/renderer/src/utils/remoteAudio.ts'

test('remote voice stream is attached and playback is started explicitly', async () => {
  const stream = {} as MediaStream
  let playCalls = 0
  const node: RemoteMediaPlaybackNode = {
    srcObject: null,
    volume: 0,
    muted: false,
    autoplay: false,
    play: async () => {
      playCalls += 1
    },
  }

  assert.equal(await attachAndPlayRemoteMedia(node, stream), true)
  assert.equal(node.srcObject, stream)
  assert.equal(node.volume, 1)
  assert.equal(node.autoplay, true)
  assert.equal(playCalls, 1)
})

test('an autoplay rejection is recoverable and does not break the RTC track handler', async () => {
  const node: RemoteMediaPlaybackNode = {
    srcObject: null,
    volume: 0,
    muted: false,
    autoplay: false,
    play: async () => {
      throw new DOMException('Not allowed', 'NotAllowedError')
    },
  }

  const result = await attachAndPlayRemoteMedia(node, {} as MediaStream)
  assert.equal(result, false)
  assert.equal(node.autoplay, true)
})

test('a start-chat gesture unlocks Web Audio and routes the RTC stream to the speakers', async () => {
  const originalAudioContext = globalThis.AudioContext
  let connectedSource = false
  let connectedDestination = false
  let closed = false
  const gain = {
    gain: { value: 0 },
    connect: () => {
      connectedDestination = true
    },
    disconnect: () => {},
  }
  const source = {
    connect: () => {
      connectedSource = true
    },
    disconnect: () => {},
  }

  class FakeAudioContext {
    state = 'suspended'
    destination = {}
    createGain = (): typeof gain => gain
    createMediaStreamSource = (): typeof source => source
    resume = async (): Promise<void> => {
      this.state = 'running'
    }
    close = async (): Promise<void> => {
      this.state = 'closed'
      closed = true
    }
  }

  Object.defineProperty(globalThis, 'AudioContext', {
    configurable: true,
    value: FakeAudioContext,
  })

  const stream = { getAudioTracks: () => [{}] } as unknown as MediaStream
  const node: RemoteMediaPlaybackNode = {
    srcObject: null,
    volume: 0,
    muted: false,
    autoplay: false,
    play: async () => {
      throw new DOMException('Not allowed', 'NotAllowedError')
    },
  }

  try {
    setRemoteAudioMuted(node, false)
    assert.equal(await unlockRemoteAudioOutput(node), true)
    assert.equal(await attachAndPlayRemoteMedia(node, stream), true)
    assert.equal(node.muted, true)
    assert.equal(connectedDestination, true)
    assert.equal(connectedSource, true)
    assert.equal(gain.gain.value, 1)

    setRemoteAudioMuted(node, true)
    assert.equal(gain.gain.value, 0)
    releaseRemoteAudioOutput(node)
    assert.equal(closed, true)
  } finally {
    if (originalAudioContext) {
      Object.defineProperty(globalThis, 'AudioContext', {
        configurable: true,
        value: originalAudioContext,
      })
    } else {
      Reflect.deleteProperty(globalThis, 'AudioContext')
    }
  }
})
