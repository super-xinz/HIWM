import assert from 'node:assert/strict'
import test from 'node:test'

import { hasRenderableVideo } from '../src/renderer/src/utils/mediaVisual.ts'

test('audio-only media is not treated as a renderable avatar video', () => {
  assert.equal(hasRenderableVideo({ videoWidth: 0, videoHeight: 0 }), false)
  assert.equal(hasRenderableVideo({ videoWidth: 0, videoHeight: 720 }), false)
})

test('a video with real dimensions is renderable', () => {
  assert.equal(hasRenderableVideo({ videoWidth: 1280, videoHeight: 720 }), true)
})

test('an absent media element is not renderable', () => {
  assert.equal(hasRenderableVideo(null), false)
  assert.equal(hasRenderableVideo(undefined), false)
})
