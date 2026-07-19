import { defineStore } from 'pinia'

export const DISPLAYED_FACE_LANDMARK_COUNT = 68

export type AnalysisConsentRecord = {
  readonly consentId: string
  readonly version: string
  readonly grantedAt: number
  readonly scopes: {
    readonly aiInteraction: true
    readonly camera: boolean
    readonly microphone: true
    readonly localFaceSignals: boolean
    readonly localProsodySignals: true
    readonly derivedDataToBackend: true
    readonly recentCameraFrameToCloud: boolean
  }
  readonly rawMediaStored: false
}

export type FaceModelStatus = 'idle' | 'loading' | 'ready' | 'unavailable'

export type PerceptionLandmark = {
  sourceIndex: number
  x: number
  y: number
  z: number
}

export type FaceBoundingBox = {
  x: number
  y: number
  width: number
  height: number
}

export type FacePerceptionFrame = {
  landmarks: PerceptionLandmark[]
  boundingBox: FaceBoundingBox
  yaw: number
  pitch: number
  quality: number
  browInnerUp: number
  jawOpen: number
  observedAt: number
}

export type FacePerceptionState = FacePerceptionFrame & {
  tracked: boolean
  modelStatus: FaceModelStatus
  error: string
}

export type ProsodyFrame = {
  waveform: number[]
  rms: number
  energyDb: number | null
  pitchHz: number | null
  relativePitchSemitones: number | null
  relativeEnergyDb: number | null
  speaking: boolean
  pauseMs: number
  speechRateWpm: number | null
  gated: boolean
  observedAt: number
}

export type ProsodyBaseline = {
  pitchHz: number | null
  rms: number | null
  pitchSamples: number
  rmsSamples: number
  startedAt: number | null
  updatedAt: number | null
}

export type ClientObservationPayload = {
  consent: boolean
  face?: {
    face_present: boolean
    yaw?: number | null
    pitch?: number | null
    tracking_quality: number
    observable_features: Array<'browInnerUp' | 'jawOpen'>
  }
  speech?: {
    speech_active: boolean
    rms: number
    pitch_hz: number | null
    pitch_delta: number | null
    energy_delta: number | null
    pause_ms: number
    speech_rate: number | null
  }
}

export type PerceptionEvidenceKind =
  | 'face-tracked'
  | 'face-lost'
  | 'head-yaw'
  | 'head-pitch'
  | 'brow-inner-up'
  | 'jaw-open'
  | 'speech-start'
  | 'speech-end'
  | 'pitch-shift'
  | 'energy-shift'
  | 'speech-rate'
  | 'pause'

export type PerceptionEvidence = {
  id: string
  modality: 'visual' | 'prosody'
  kind: PerceptionEvidenceKind
  label: string
  value: number | null
  unit: string | null
  quality: number
  observedAt: number
  metadata: Record<string, string | number | boolean | null>
}

export type RecordEvidenceInput = {
  kind: PerceptionEvidenceKind
  value?: number | null
  unit?: string | null
  quality?: number
  observedAt?: number
  cooldownMs?: number
  metadata?: Record<string, string | number | boolean | null>
}

interface PerceptionState {
  analysisAuthorized: boolean
  consentUpdatedAt: number | null
  consentRecord: AnalysisConsentRecord | null
  ttsSpeaking: boolean
  face: FacePerceptionState
  prosody: ProsodyFrame
  baseline: ProsodyBaseline
  evidence: PerceptionEvidence[]
  lastEvidenceAt: Record<string, number>
  evidenceSequence: number
}

const emptyBoundingBox = (): FaceBoundingBox => ({ x: 0, y: 0, width: 0, height: 0 })

const emptyFaceFrame = (): FacePerceptionFrame => ({
  landmarks: [],
  boundingBox: emptyBoundingBox(),
  yaw: 0,
  pitch: 0,
  quality: 0,
  browInnerUp: 0,
  jawOpen: 0,
  observedAt: 0,
})

const emptyFaceState = (): FacePerceptionState => ({
  ...emptyFaceFrame(),
  tracked: false,
  modelStatus: 'idle',
  error: '',
})

const emptyProsody = (): ProsodyFrame => ({
  waveform: [],
  rms: 0,
  energyDb: null,
  pitchHz: null,
  relativePitchSemitones: null,
  relativeEnergyDb: null,
  speaking: false,
  pauseMs: 0,
  speechRateWpm: null,
  gated: false,
  observedAt: 0,
})

const emptyBaseline = (): ProsodyBaseline => ({
  pitchHz: null,
  rms: null,
  pitchSamples: 0,
  rmsSamples: 0,
  startedAt: null,
  updatedAt: null,
})

const clamp = (value: number, minimum = 0, maximum = 1): number =>
  Math.min(maximum, Math.max(minimum, Number.isFinite(value) ? value : minimum))

const rounded = (value: number, digits = 1): string => value.toFixed(digits)

const direction = (metadata: Record<string, string | number | boolean | null>): string =>
  typeof metadata.direction === 'string' ? metadata.direction : ''

/**
 * Evidence labels deliberately describe observable motion/acoustic changes only.
 * The perception layer must not turn these signals into emotion, personality,
 * deception, health, or other latent-person judgements.
 */
const evidenceLabel = (
  kind: PerceptionEvidenceKind,
  value: number | null,
  metadata: Record<string, string | number | boolean | null>
): string => {
  switch (kind) {
    case 'face-tracked':
      return '面部跟踪已建立'
    case 'face-lost':
      return '面部跟踪丢失'
    case 'head-yaw':
      return direction(metadata) === 'left' ? '头部向左转动' : '头部向右转动'
    case 'head-pitch':
      return direction(metadata) === 'up' ? '抬头幅度上升' : '低头幅度上升'
    case 'brow-inner-up':
      return `browInnerUp ${direction(metadata) === 'down' ? '↓' : '↑'}`
    case 'jaw-open':
      return `jawOpen ${direction(metadata) === 'down' ? '↓' : '↑'}`
    case 'speech-start':
      return '检测到用户开始说话'
    case 'speech-end':
      return '检测到用户停止说话'
    case 'pitch-shift':
      return `音高较本轮基线${(value ?? 0) >= 0 ? '上升' : '下降'} ${rounded(Math.abs(value ?? 0))} 半音`
    case 'energy-shift':
      return `声音能量较本轮基线${(value ?? 0) >= 0 ? '上升' : '下降'} ${rounded(Math.abs(value ?? 0))} dB`
    case 'speech-rate':
      return `当前语速约 ${Math.round(value ?? 0)} 词/分钟`
    case 'pause':
      return `回答中停顿 ${rounded((value ?? 0) / 1000)} 秒`
  }
}

const modalityFor = (kind: PerceptionEvidenceKind): 'visual' | 'prosody' =>
  ['face-tracked', 'face-lost', 'head-yaw', 'head-pitch', 'brow-inner-up', 'jaw-open'].includes(
    kind
  )
    ? 'visual'
    : 'prosody'

export const usePerceptionStore = defineStore('perceptionStore', {
  state: (): PerceptionState => ({
    analysisAuthorized: false,
    consentUpdatedAt: null,
    consentRecord: null,
    ttsSpeaking: false,
    face: emptyFaceState(),
    prosody: emptyProsody(),
    baseline: emptyBaseline(),
    evidence: [],
    lastEvidenceAt: {},
    evidenceSequence: 0,
  }),
  getters: {
    canAnalyze: (state): boolean => state.analysisAuthorized,
    latestEvidence: (state): PerceptionEvidence | null =>
      state.evidence.length ? state.evidence[state.evidence.length - 1] : null,
  },
  actions: {
    setAnalysisAuthorized(authorized: boolean, decision?: AnalysisConsentRecord) {
      this.analysisAuthorized = authorized
      this.consentUpdatedAt = Date.now()
      this.consentRecord = authorized && decision ? Object.freeze({ ...decision }) : null
      if (!authorized) {
        this.clearFace()
        this.clearProsody()
        this.resetBaseline()
        this.clearEvidence()
      }
    },
    setTtsSpeaking(speaking: boolean) {
      this.ttsSpeaking = speaking
      if (speaking) {
        this.prosody = {
          ...emptyProsody(),
          gated: true,
          observedAt: Date.now(),
        }
      }
    },
    setFaceModelStatus(status: FaceModelStatus, error = '') {
      this.face.modelStatus = status
      this.face.error = error
      if (status === 'unavailable') this.clearFace(true)
    },
    updateFace(frame: FacePerceptionFrame) {
      if (!this.analysisAuthorized) return
      this.face = {
        ...frame,
        landmarks: frame.landmarks.slice(0, DISPLAYED_FACE_LANDMARK_COUNT),
        boundingBox: { ...frame.boundingBox },
        yaw: Number.isFinite(frame.yaw) ? frame.yaw : 0,
        pitch: Number.isFinite(frame.pitch) ? frame.pitch : 0,
        quality: clamp(frame.quality),
        browInnerUp: clamp(frame.browInnerUp),
        jawOpen: clamp(frame.jawOpen),
        tracked: true,
        modelStatus: this.face.modelStatus === 'unavailable' ? 'ready' : this.face.modelStatus,
        error: '',
      }
    },
    clearFace(preserveModelState = false) {
      const modelStatus = preserveModelState ? this.face.modelStatus : 'idle'
      const error = preserveModelState ? this.face.error : ''
      this.face = {
        ...emptyFaceState(),
        modelStatus,
        error,
      }
    },
    updateProsody(frame: ProsodyFrame) {
      if (!this.analysisAuthorized || this.ttsSpeaking) return
      this.prosody = {
        ...frame,
        waveform: frame.waveform.slice(0, 128).map((sample) => clamp(sample, -1, 1)),
        rms: clamp(frame.rms, 0, 1),
        speechRateWpm: frame.speechRateWpm === null ? null : clamp(frame.speechRateWpm, 0, 500),
        observedAt: frame.observedAt || Date.now(),
      }
    },
    clearProsody(preserveGate = false) {
      this.prosody = {
        ...emptyProsody(),
        gated: preserveGate ? this.prosody.gated : false,
      }
    },
    observeBaseline(pitchHz: number | null, rms: number, observedAt = Date.now()) {
      if (!this.analysisAuthorized || this.ttsSpeaking || rms <= 0) return
      if (this.baseline.startedAt === null) this.baseline.startedAt = observedAt

      if (pitchHz !== null && Number.isFinite(pitchHz) && pitchHz > 0) {
        const count = this.baseline.pitchSamples
        const alpha = count < 30 ? 1 / (count + 1) : 0.012
        this.baseline.pitchHz =
          this.baseline.pitchHz === null
            ? pitchHz
            : this.baseline.pitchHz + alpha * (pitchHz - this.baseline.pitchHz)
        this.baseline.pitchSamples += 1
      }

      const rmsCount = this.baseline.rmsSamples
      const rmsAlpha = rmsCount < 30 ? 1 / (rmsCount + 1) : 0.012
      this.baseline.rms =
        this.baseline.rms === null ? rms : this.baseline.rms + rmsAlpha * (rms - this.baseline.rms)
      this.baseline.rmsSamples += 1
      this.baseline.updatedAt = observedAt
    },
    setSpeechRate(speechRateWpm: number | null) {
      this.prosody.speechRateWpm = speechRateWpm === null ? null : clamp(speechRateWpm, 0, 500)
    },
    resetBaseline() {
      this.baseline = emptyBaseline()
    },
    recordEvidence(input: RecordEvidenceInput): PerceptionEvidence | null {
      if (!this.analysisAuthorized) return null
      const modality = modalityFor(input.kind)
      if (modality === 'prosody' && this.ttsSpeaking) return null

      const observedAt = input.observedAt ?? Date.now()
      const metadata = input.metadata ?? {}
      const cooldownKey = `${input.kind}:${direction(metadata)}`
      const cooldownMs = input.cooldownMs ?? 900
      const previousAt = this.lastEvidenceAt[cooldownKey] ?? 0
      if (observedAt - previousAt < cooldownMs) return null
      this.lastEvidenceAt[cooldownKey] = observedAt

      const value = input.value ?? null
      this.evidenceSequence += 1
      const evidence: PerceptionEvidence = {
        id: `perception-${observedAt}-${this.evidenceSequence}`,
        modality,
        kind: input.kind,
        label: evidenceLabel(input.kind, value, metadata),
        value,
        unit: input.unit ?? null,
        quality: clamp(input.quality ?? 1),
        observedAt,
        metadata: { ...metadata },
      }
      this.evidence.push(evidence)
      if (this.evidence.length > 250) this.evidence.splice(0, this.evidence.length - 250)
      return evidence
    },
    clearEvidence() {
      this.evidence = []
      this.lastEvidenceAt = {}
      this.evidenceSequence = 0
    },
    resetSession() {
      this.clearFace()
      this.clearProsody()
      this.resetBaseline()
      this.clearEvidence()
      this.ttsSpeaking = false
    },
    toClientObservation(): ClientObservationPayload {
      if (!this.analysisAuthorized) return { consent: false }
      const face = this.face.tracked
        ? {
            face_present: true,
            yaw: clamp(this.face.yaw, -90, 90),
            pitch: clamp(this.face.pitch, -90, 90),
            tracking_quality: clamp(this.face.quality),
            observable_features: [
              ...(this.face.browInnerUp >= 0.35 ? (['browInnerUp'] as const) : []),
              ...(this.face.jawOpen >= 0.25 ? (['jawOpen'] as const) : []),
            ],
          }
        : {
            face_present: false,
            tracking_quality: 0,
            observable_features: [] as Array<'browInnerUp' | 'jawOpen'>,
          }
      const baselinePitch = this.baseline.pitchHz
      return {
        consent: true,
        face,
        speech: {
          speech_active: this.prosody.speaking && !this.prosody.gated,
          rms: clamp(this.prosody.rms),
          pitch_hz: this.prosody.pitchHz === null ? null : clamp(this.prosody.pitchHz, 0, 2000),
          pitch_delta:
            this.prosody.pitchHz === null || baselinePitch === null
              ? null
              : clamp(this.prosody.pitchHz - baselinePitch, -2000, 2000),
          energy_delta:
            this.prosody.relativeEnergyDb === null
              ? null
              : clamp(this.prosody.relativeEnergyDb / 20, -1, 1),
          pause_ms: Math.round(clamp(this.prosody.pauseMs, 0, 60_000)),
          speech_rate:
            this.prosody.speechRateWpm === null
              ? null
              : clamp(this.prosody.speechRateWpm / 60, 0, 20),
        },
      }
    },
  },
})
