import assert from 'node:assert/strict'
import { afterEach, test } from 'node:test'

import {
  describeMediaAccessError,
  getStream,
  MediaPermissionTimeoutError,
} from '../src/renderer/src/utils/streamUtils.ts'

const originalNavigatorDescriptor = Object.getOwnPropertyDescriptor(globalThis, 'navigator')

function installMediaDevices(getUserMedia: () => Promise<MediaStream>): void {
  Object.defineProperty(globalThis, 'navigator', {
    configurable: true,
    value: {
      mediaDevices: {
        getUserMedia,
      },
    },
  })
}

afterEach(() => {
  if (originalNavigatorDescriptor) {
    Object.defineProperty(globalThis, 'navigator', originalNavigatorDescriptor)
  } else {
    Reflect.deleteProperty(globalThis, 'navigator')
  }
})

test('a pending media permission request fails with a safe timeout error', async () => {
  let requestCount = 0
  installMediaDevices(() => {
    requestCount += 1
    return new Promise<MediaStream>(() => {})
  })

  const request = getStream(true, true, undefined, 5)
  assert.equal(requestCount, 1, 'getUserMedia should run synchronously in the click call stack')

  await assert.rejects(request, (error) => {
    assert.ok(error instanceof MediaPermissionTimeoutError)
    assert.equal(error.message, '设备权限请求超时，请检查浏览器权限后重试')
    return true
  })
  assert.equal(requestCount, 1)
})

test('Safari permission denial is translated into actionable recovery guidance', () => {
  const error = new DOMException(
    'The request is not allowed by the user agent or the platform in the current context',
    'NotAllowedError'
  )

  const description = describeMediaAccessError(
    error,
    true,
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/18.5 Safari/605.1.15'
  )

  assert.match(description, /Safari/)
  assert.match(description, /网站设置/)
  assert.match(description, /隐私与安全性/)
})

test('tracks from a stream granted after the timeout are stopped', async () => {
  let resolveMediaRequest: (stream: MediaStream) => void = () => undefined
  installMediaDevices(
    () =>
      new Promise<MediaStream>((resolve) => {
        resolveMediaRequest = resolve
      })
  )

  const request = getStream(true, true, undefined, 5)
  await assert.rejects(request, MediaPermissionTimeoutError)

  let stoppedTrackCount = 0
  resolveMediaRequest({
    getTracks: () => [
      { stop: () => (stoppedTrackCount += 1) },
      { stop: () => (stoppedTrackCount += 1) },
    ],
    getAudioTracks: () => [],
    getVideoTracks: () => [],
  } as unknown as MediaStream)
  await new Promise((resolve) => setImmediate(resolve))

  assert.equal(stoppedTrackCount, 2)
})
