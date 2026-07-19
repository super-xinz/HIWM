import assert from 'node:assert/strict'
import { test } from 'node:test'

import { createPinia, setActivePinia } from 'pinia'

import {
  DISPLAYED_FACE_LANDMARK_COUNT,
  type FacePerceptionFrame,
  type ProsodyFrame,
  usePerceptionStore,
} from '../src/renderer/src/store/perception.ts'

function createStore(): ReturnType<typeof usePerceptionStore> {
  setActivePinia(createPinia())
  return usePerceptionStore()
}

function faceFrame(): FacePerceptionFrame {
  return {
    landmarks: Array.from({ length: 80 }, (_, sourceIndex) => ({
      sourceIndex,
      x: sourceIndex / 80,
      y: sourceIndex / 80,
      z: 0,
    })),
    boundingBox: { x: 0.1, y: 0.2, width: 0.4, height: 0.5 },
    yaw: 120,
    pitch: -120,
    quality: 1.4,
    browInnerUp: 0.5,
    jawOpen: 0.4,
    observedAt: 1_000,
  }
}

function prosodyFrame(): ProsodyFrame {
  return {
    waveform: Array.from({ length: 160 }, (_, index) => (index % 2 ? 2 : -2)),
    rms: 1.4,
    energyDb: -12,
    pitchHz: 220,
    relativePitchSemitones: 2,
    relativeEnergyDb: 30,
    speaking: true,
    pauseMs: 80_000,
    speechRateWpm: 720,
    gated: false,
    observedAt: 2_000,
  }
}

test('derived face and prosody payload is consent gated and bounded', () => {
  const store = createStore()

  assert.deepEqual(store.toClientObservation(), { consent: false })
  store.updateFace(faceFrame())
  assert.equal(store.face.tracked, false)

  store.setAnalysisAuthorized(true)
  store.updateFace(faceFrame())
  store.observeBaseline(200, 0.2, 1_500)
  store.updateProsody(prosodyFrame())

  const payload = store.toClientObservation()
  assert.equal(payload.consent, true)
  assert.deepEqual(payload.face, {
    face_present: true,
    yaw: 90,
    pitch: -90,
    tracking_quality: 1,
    observable_features: ['browInnerUp', 'jawOpen'],
  })
  assert.equal(store.face.landmarks.length, DISPLAYED_FACE_LANDMARK_COUNT)
  assert.equal(store.prosody.waveform.length, 128)
  assert.deepEqual(payload.speech, {
    speech_active: true,
    rms: 1,
    pitch_hz: 220,
    pitch_delta: 20,
    energy_delta: 1,
    pause_ms: 60_000,
    speech_rate: 500 / 60,
  })
})

test('TTS playback gates acoustic analysis and prosody evidence', () => {
  const store = createStore()
  store.setAnalysisAuthorized(true)
  store.updateProsody(prosodyFrame())
  assert.equal(store.toClientObservation().speech?.speech_active, true)

  store.setTtsSpeaking(true)
  assert.equal(store.prosody.gated, true)
  assert.equal(store.prosody.rms, 0)
  assert.equal(store.recordEvidence({ kind: 'speech-start', observedAt: 3_000 }), null)
  assert.deepEqual(store.toClientObservation().speech, {
    speech_active: false,
    rms: 0,
    pitch_hz: null,
    pitch_delta: null,
    energy_delta: null,
    pause_ms: 0,
    speech_rate: null,
  })

  store.setTtsSpeaking(false)
  store.updateProsody(prosodyFrame())
  assert.equal(store.toClientObservation().speech?.speech_active, true)
})

test('consent withdrawal clears derived state, evidence and baselines', () => {
  const store = createStore()
  store.setAnalysisAuthorized(true)
  store.updateFace(faceFrame())
  store.observeBaseline(200, 0.2, 1_500)
  store.updateProsody(prosodyFrame())
  assert.ok(store.recordEvidence({ kind: 'head-yaw', value: 12, observedAt: 4_000 }))

  store.setAnalysisAuthorized(false)

  assert.deepEqual(store.toClientObservation(), { consent: false })
  assert.equal(store.face.tracked, false)
  assert.equal(store.prosody.rms, 0)
  assert.equal(store.baseline.pitchSamples, 0)
  assert.equal(store.evidence.length, 0)
})
