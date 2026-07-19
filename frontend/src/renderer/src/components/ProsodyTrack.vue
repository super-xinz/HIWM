<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

import { type PerceptionEvidence, type ProsodyFrame, usePerceptionStore } from '@/store/perception'

const props = withDefaults(
  defineProps<{
    stream: MediaStream | null
    enabled?: boolean
    ttsSpeaking?: boolean
    speechRateWpm?: number | null
    vadThreshold?: number
    minimumPauseMs?: number
    maxFps?: number
    waveformPoints?: number
    showMetrics?: boolean
  }>(),
  {
    enabled: true,
    ttsSpeaking: false,
    speechRateWpm: null,
    vadThreshold: 0.018,
    minimumPauseMs: 500,
    maxFps: 30,
    waveformPoints: 96,
    showMetrics: true,
  }
)

const emit = defineEmits<{
  ready: []
  frame: [frame: ProsodyFrame]
  evidence: [evidence: PerceptionEvidence]
  'speech-start': [observedAt: number]
  'speech-end': [observedAt: number]
  pause: [durationMs: number, observedAt: number]
  error: [message: string]
}>()

const store = usePerceptionStore()
const canvasRef = ref<HTMLCanvasElement | null>(null)
const mounted = ref(false)
const localError = ref('')
const ready = ref(false)
const trackRevision = ref(0)

let audioContext: AudioContext | null = null
let mediaSource: MediaStreamAudioSourceNode | null = null
let analyser: AnalyserNode | null = null
let monitoredTrack: MediaStreamTrack | null = null
let sampleBuffer: Float32Array | null = null
let animationFrameId = 0
let generation = 0
let lastFrameAt = 0
let lastPitchAt = 0
let lastPitchHz: number | null = null
let smoothedRms = 0
let wasSpeaking = false
let hasSpoken = false
let silenceStartedAt: number | null = null
let pitchEvidenceSide = 0
let energyEvidenceSide = 0
const pitchHistory: number[] = []
const energyHistory: number[] = []
const speakingHistory: boolean[] = []

const gated = computed(() => props.ttsSpeaking || store.ttsSpeaking)
const activeAudioTrack = computed(() => {
  const revision = trackRevision.value
  const track = props.stream?.getAudioTracks().find((item) => item.readyState === 'live') ?? null
  return revision >= 0 ? track : null
})
const active = computed(
  () =>
    mounted.value &&
    props.enabled &&
    store.analysisAuthorized &&
    Boolean(props.stream && activeAudioTrack.value)
)

const statusText = computed(() => {
  if (!store.analysisAuthorized) return '声音分析未授权'
  if (gated.value) return '机器人发声中，用户语音分析已门控'
  if (localError.value) return '语音特征暂不可用'
  if (!activeAudioTrack.value) return '等待麦克风音频'
  return ''
})

const pitchText = computed(() => {
  const pitch = store.prosody.pitchHz
  const relative = store.prosody.relativePitchSemitones
  if (pitch === null) return '音高 --'
  const delta = relative === null ? '' : `  Δ ${relative >= 0 ? '+' : ''}${relative.toFixed(1)} st`
  return `音高 ${Math.round(pitch)} Hz${delta}`
})

const energyText = computed(() => {
  const relative = store.prosody.relativeEnergyDb
  const suffix = relative === null ? '' : `  Δ ${relative >= 0 ? '+' : ''}${relative.toFixed(1)} dB`
  return `RMS ${store.prosody.rms.toFixed(3)}${suffix}`
})

const pauseText = computed(() =>
  store.prosody.speaking
    ? '说话中'
    : store.prosody.pauseMs >= props.minimumPauseMs
      ? `停顿 ${(store.prosody.pauseMs / 1000).toFixed(1)} s`
      : '静音'
)

const clamp = (value: number, minimum: number, maximum: number): number =>
  Math.min(maximum, Math.max(minimum, value))

const normalizeError = (error: unknown): string =>
  error instanceof Error ? error.message : String(error)

function emitEvidence(
  input: Parameters<typeof store.recordEvidence>[0]
): PerceptionEvidence | null {
  const evidence = store.recordEvidence(input)
  if (evidence) emit('evidence', evidence)
  return evidence
}

async function releaseAudio(): Promise<void> {
  if (animationFrameId) cancelAnimationFrame(animationFrameId)
  animationFrameId = 0

  const oldSource = mediaSource
  const oldAnalyser = analyser
  const oldContext = audioContext
  const oldTrack = monitoredTrack
  mediaSource = null
  analyser = null
  audioContext = null
  monitoredTrack = null
  sampleBuffer = null
  ready.value = false

  try {
    oldTrack?.removeEventListener('ended', handleTrackEnded)
    oldSource?.disconnect()
    oldAnalyser?.disconnect()
  } catch {
    // Nodes may already have been disconnected by the browser.
  }
  if (oldContext && oldContext.state !== 'closed') {
    try {
      await oldContext.close()
    } catch {
      // Closing is best-effort during a stream switch or unmount.
    }
  }
}

async function reconcile(): Promise<void> {
  const currentGeneration = ++generation
  await releaseAudio()
  resetLiveState()

  if (!active.value || !props.stream) {
    store.clearProsody(gated.value)
    drawTrack()
    return
  }

  try {
    const audioWindow = window as typeof window & {
      webkitAudioContext?: typeof AudioContext
    }
    const AudioContextConstructor = audioWindow.AudioContext ?? audioWindow.webkitAudioContext
    if (!AudioContextConstructor) throw new Error('Web Audio API is unavailable')

    const context = new AudioContextConstructor({ latencyHint: 'interactive' })
    const source = context.createMediaStreamSource(props.stream)
    const nextAnalyser = context.createAnalyser()
    nextAnalyser.fftSize = 2048
    nextAnalyser.smoothingTimeConstant = 0.25
    source.connect(nextAnalyser)

    if (context.state === 'suspended') await context.resume()
    if (currentGeneration !== generation || !active.value) {
      source.disconnect()
      await context.close()
      return
    }

    audioContext = context
    mediaSource = source
    analyser = nextAnalyser
    monitoredTrack = activeAudioTrack.value
    monitoredTrack?.addEventListener('ended', handleTrackEnded)
    sampleBuffer = new Float32Array(nextAnalyser.fftSize)
    localError.value = ''
    ready.value = true
    emit('ready')
    scheduleFrame()
  } catch (error: unknown) {
    if (currentGeneration !== generation) return
    const detail = normalizeError(error)
    localError.value = detail
    store.clearProsody()
    emit('error', detail)
    drawTrack()
  }
}

function handleTrackEnded(): void {
  trackRevision.value += 1
  void reconcile()
}

function resetLiveState(): void {
  lastFrameAt = 0
  lastPitchAt = 0
  lastPitchHz = null
  smoothedRms = 0
  wasSpeaking = false
  hasSpoken = false
  silenceStartedAt = null
  pitchEvidenceSide = 0
  energyEvidenceSide = 0
  pitchHistory.length = 0
  energyHistory.length = 0
  speakingHistory.length = 0
}

function scheduleFrame(): void {
  if (!animationFrameId && active.value && analyser && sampleBuffer) {
    animationFrameId = requestAnimationFrame(processFrame)
  }
}

function processFrame(timestamp: number): void {
  animationFrameId = 0
  if (!active.value || !analyser || !sampleBuffer || !audioContext) return
  const frameInterval = 1000 / clamp(props.maxFps, 1, 60)
  if (timestamp - lastFrameAt < frameInterval) {
    scheduleFrame()
    return
  }
  lastFrameAt = timestamp

  if (gated.value) {
    wasSpeaking = false
    silenceStartedAt = null
    const frame = gatedFrame()
    if (!store.ttsSpeaking) store.updateProsody(frame)
    emit('frame', frame)
    drawTrack()
    scheduleFrame()
    return
  }

  analyser.getFloatTimeDomainData(sampleBuffer as Float32Array<ArrayBuffer>)
  const observedAt = Date.now()
  const rms = calculateRms(sampleBuffer)
  smoothedRms = smoothedRms ? smoothedRms * 0.72 + rms * 0.28 : rms
  const offThreshold = props.vadThreshold * 0.72
  const speaking = smoothedRms >= (wasSpeaking ? offThreshold : props.vadThreshold)

  if (speaking && timestamp - lastPitchAt >= 80) {
    lastPitchHz = autoCorrelatePitch(sampleBuffer, audioContext.sampleRate)
    lastPitchAt = timestamp
  } else if (!speaking) {
    lastPitchHz = null
  }

  const baselinePitch = store.baseline.pitchHz
  const baselineRms = store.baseline.rms
  const relativePitchSemitones =
    speaking && lastPitchHz !== null && baselinePitch !== null && store.baseline.pitchSamples >= 5
      ? 12 * Math.log2(lastPitchHz / baselinePitch)
      : null
  const relativeEnergyDb =
    speaking && baselineRms !== null && baselineRms > 0 && store.baseline.rmsSamples >= 5
      ? 20 * Math.log10(Math.max(rms, 0.000001) / baselineRms)
      : null

  updateSpeechState(speaking, observedAt)
  const pauseMs =
    !speaking && silenceStartedAt !== null ? Math.max(0, observedAt - silenceStartedAt) : 0

  const waveform = downsample(sampleBuffer, clamp(Math.round(props.waveformPoints), 32, 128))
  const frame: ProsodyFrame = {
    waveform,
    rms,
    energyDb: 20 * Math.log10(Math.max(rms, 0.000001)),
    pitchHz: speaking ? lastPitchHz : null,
    relativePitchSemitones,
    relativeEnergyDb,
    speaking,
    pauseMs,
    speechRateWpm: props.speechRateWpm,
    gated: false,
    observedAt,
  }
  store.updateProsody(frame)
  emit('frame', frame)

  if (speaking) {
    detectAcousticChanges(relativePitchSemitones, relativeEnergyDb, observedAt)
    store.observeBaseline(lastPitchHz, rms, observedAt)
  }
  appendHistory(relativePitchSemitones, relativeEnergyDb, speaking)
  drawTrack()
  scheduleFrame()
}

function gatedFrame(): ProsodyFrame {
  return {
    waveform: [],
    rms: 0,
    energyDb: null,
    pitchHz: null,
    relativePitchSemitones: null,
    relativeEnergyDb: null,
    speaking: false,
    pauseMs: 0,
    speechRateWpm: props.speechRateWpm,
    gated: true,
    observedAt: Date.now(),
  }
}

function updateSpeechState(speaking: boolean, observedAt: number): void {
  if (speaking && !wasSpeaking) {
    const completedPauseMs =
      hasSpoken && silenceStartedAt !== null ? observedAt - silenceStartedAt : 0
    if (completedPauseMs >= props.minimumPauseMs) {
      const evidence = emitEvidence({
        kind: 'pause',
        value: completedPauseMs,
        unit: 'ms',
        observedAt,
        cooldownMs: 0,
      })
      if (evidence) emit('pause', completedPauseMs, observedAt)
    }
    hasSpoken = true
    silenceStartedAt = null
    const evidence = emitEvidence({
      kind: 'speech-start',
      observedAt,
      cooldownMs: 0,
    })
    if (evidence) emit('speech-start', observedAt)
  } else if (!speaking && wasSpeaking) {
    silenceStartedAt = observedAt
    const evidence = emitEvidence({
      kind: 'speech-end',
      observedAt,
      cooldownMs: 0,
    })
    if (evidence) emit('speech-end', observedAt)
  }
  wasSpeaking = speaking
}

function detectAcousticChanges(
  relativePitchSemitones: number | null,
  relativeEnergyDb: number | null,
  observedAt: number
): void {
  const pitchSide =
    relativePitchSemitones === null || Math.abs(relativePitchSemitones) < 2
      ? 0
      : Math.sign(relativePitchSemitones)
  if (pitchSide && pitchSide !== pitchEvidenceSide) {
    emitEvidence({
      kind: 'pitch-shift',
      value: relativePitchSemitones,
      unit: 'semitone',
      observedAt,
      cooldownMs: 1600,
    })
  }
  pitchEvidenceSide = pitchSide

  const energySide =
    relativeEnergyDb === null || Math.abs(relativeEnergyDb) < 4 ? 0 : Math.sign(relativeEnergyDb)
  if (energySide && energySide !== energyEvidenceSide) {
    emitEvidence({
      kind: 'energy-shift',
      value: relativeEnergyDb,
      unit: 'dB',
      observedAt,
      cooldownMs: 1600,
    })
  }
  energyEvidenceSide = energySide
}

function calculateRms(samples: Float32Array): number {
  let sum = 0
  for (let index = 0; index < samples.length; index += 1) sum += samples[index] ** 2
  return Math.sqrt(sum / samples.length)
}

/**
 * Normalized autocorrelation pitch detector. It intentionally exposes only a
 * fundamental-frequency estimate and never maps the signal to a latent label.
 */
function autoCorrelatePitch(samples: Float32Array, sampleRate: number): number | null {
  const rms = calculateRms(samples)
  if (rms < props.vadThreshold) return null

  let mean = 0
  for (let index = 0; index < samples.length; index += 1) mean += samples[index]
  mean /= samples.length

  const minimumLag = Math.max(2, Math.floor(sampleRate / 420))
  const maximumLag = Math.min(samples.length - 2, Math.ceil(sampleRate / 70))
  let bestLag = -1
  let bestCorrelation = 0
  const correlations = new Float32Array(maximumLag + 1)

  for (let lag = minimumLag; lag <= maximumLag; lag += 1) {
    let product = 0
    let leftEnergy = 0
    let rightEnergy = 0
    const limit = samples.length - lag
    for (let index = 0; index < limit; index += 1) {
      const left = samples[index] - mean
      const right = samples[index + lag] - mean
      product += left * right
      leftEnergy += left * left
      rightEnergy += right * right
    }
    const denominator = Math.sqrt(leftEnergy * rightEnergy)
    const correlation = denominator > 0 ? product / denominator : 0
    correlations[lag] = correlation
    if (correlation > bestCorrelation) {
      bestCorrelation = correlation
      bestLag = lag
    }
  }

  if (bestLag < 0 || bestCorrelation < 0.55) return null
  const previous = correlations[bestLag - 1] ?? correlations[bestLag]
  const current = correlations[bestLag]
  const next = correlations[bestLag + 1] ?? current
  const denominator = previous - 2 * current + next
  const offset = Math.abs(denominator) > 0.000001 ? (0.5 * (previous - next)) / denominator : 0
  const refinedLag = bestLag + clamp(offset, -1, 1)
  const pitch = sampleRate / refinedLag
  return pitch >= 70 && pitch <= 420 ? pitch : null
}

function downsample(samples: Float32Array, count: number): number[] {
  const result = new Array<number>(count)
  const stride = samples.length / count
  for (let index = 0; index < count; index += 1) {
    const start = Math.floor(index * stride)
    const end = Math.max(start + 1, Math.floor((index + 1) * stride))
    let sum = 0
    for (let sampleIndex = start; sampleIndex < end; sampleIndex += 1) {
      sum += samples[sampleIndex]
    }
    result[index] = sum / (end - start)
  }
  return result
}

function appendHistory(
  relativePitchSemitones: number | null,
  relativeEnergyDb: number | null,
  speaking: boolean
): void {
  pitchHistory.push(relativePitchSemitones ?? Number.NaN)
  energyHistory.push(relativeEnergyDb ?? Number.NaN)
  speakingHistory.push(speaking)
  const maximum = 150
  if (pitchHistory.length > maximum) pitchHistory.splice(0, pitchHistory.length - maximum)
  if (energyHistory.length > maximum) energyHistory.splice(0, energyHistory.length - maximum)
  if (speakingHistory.length > maximum) speakingHistory.splice(0, speakingHistory.length - maximum)
}

function drawTrack(): void {
  const canvas = canvasRef.value
  if (!canvas) return
  const width = canvas.clientWidth
  const height = canvas.clientHeight
  if (!width || !height) return
  const density = Math.min(window.devicePixelRatio || 1, 2)
  const pixelWidth = Math.round(width * density)
  const pixelHeight = Math.round(height * density)
  if (canvas.width !== pixelWidth || canvas.height !== pixelHeight) {
    canvas.width = pixelWidth
    canvas.height = pixelHeight
  }

  const context = canvas.getContext('2d')
  if (!context) return
  context.setTransform(density, 0, 0, density, 0, 0)
  context.clearRect(0, 0, width, height)
  context.fillStyle = '#ffffff'
  context.fillRect(0, 0, width, height)

  const labelWidth = 63
  const plotLeft = labelWidth
  const plotWidth = Math.max(1, width - plotLeft - 7)
  const rowHeight = height / 3
  context.font = '600 10px ui-monospace, SFMono-Regular, Menlo, monospace'
  context.fillStyle = 'rgba(68, 86, 80, 0.94)'
  context.fillText('WAVE', 8, rowHeight * 0.55)
  context.fillText('PITCH Δ', 8, rowHeight * 1.55)
  context.fillText('ENERGY', 8, rowHeight * 2.55)
  context.strokeStyle = 'rgba(20, 130, 103, 0.12)'
  context.lineWidth = 1
  for (let row = 1; row < 3; row += 1) {
    context.beginPath()
    context.moveTo(0, rowHeight * row)
    context.lineTo(width, rowHeight * row)
    context.stroke()
  }

  drawWaveform(context, store.prosody.waveform, plotLeft, 0, plotWidth, rowHeight)
  drawHistory(context, pitchHistory, plotLeft, rowHeight, plotWidth, rowHeight, 6, '105, 225, 211')
  drawHistory(
    context,
    energyHistory,
    plotLeft,
    rowHeight * 2,
    plotWidth,
    rowHeight,
    12,
    '111, 177, 241'
  )
  drawSpeakingSegments(context, plotLeft, rowHeight * 3 - 3, plotWidth)

  if (gated.value) {
    context.fillStyle = 'rgba(245, 247, 246, 0.82)'
    context.fillRect(plotLeft, 0, plotWidth, height)
    context.fillStyle = 'rgba(68, 86, 80, 0.94)'
    context.fillText('TTS GATED', plotLeft + 8, 13)
  }
}

function drawWaveform(
  context: CanvasRenderingContext2D,
  samples: number[],
  x: number,
  y: number,
  width: number,
  height: number
): void {
  context.strokeStyle = 'rgba(20, 130, 103, 0.82)'
  context.lineWidth = 1.1
  context.beginPath()
  if (!samples.length) {
    context.moveTo(x, y + height / 2)
    context.lineTo(x + width, y + height / 2)
  } else {
    samples.forEach((sample, index) => {
      const pointX = x + (index / Math.max(1, samples.length - 1)) * width
      const pointY = y + height / 2 - clamp(sample, -1, 1) * height * 0.42
      if (index === 0) context.moveTo(pointX, pointY)
      else context.lineTo(pointX, pointY)
    })
  }
  context.stroke()
}

function drawHistory(
  context: CanvasRenderingContext2D,
  values: number[],
  x: number,
  y: number,
  width: number,
  height: number,
  range: number,
  color: string
): void {
  context.strokeStyle = `rgba(${color}, 0.78)`
  context.lineWidth = 1.2
  context.beginPath()
  let drawing = false
  values.forEach((value, index) => {
    if (!Number.isFinite(value)) {
      drawing = false
      return
    }
    const pointX = x + (index / Math.max(1, values.length - 1)) * width
    const pointY = y + height / 2 - (clamp(value, -range, range) / range) * height * 0.42
    if (!drawing) {
      context.moveTo(pointX, pointY)
      drawing = true
    } else {
      context.lineTo(pointX, pointY)
    }
  })
  context.stroke()
}

function drawSpeakingSegments(
  context: CanvasRenderingContext2D,
  x: number,
  y: number,
  width: number
): void {
  if (!speakingHistory.length) return
  const segmentWidth = width / speakingHistory.length
  context.fillStyle = 'rgba(20, 130, 103, 0.7)'
  speakingHistory.forEach((speaking, index) => {
    if (speaking) context.fillRect(x + index * segmentWidth, y, Math.max(1, segmentWidth), 2)
  })
}

function resetBaseline(): void {
  store.resetBaseline()
  pitchHistory.length = 0
  energyHistory.length = 0
}

async function start(): Promise<void> {
  if (ready.value && audioContext?.state === 'running') return
  await reconcile()
}

async function stop(): Promise<void> {
  generation += 1
  await releaseAudio()
  store.clearProsody()
  drawTrack()
}

watch(
  () => [props.stream, props.enabled, store.analysisAuthorized] as const,
  () => void reconcile(),
  { flush: 'post' }
)

watch(
  () => props.speechRateWpm,
  (value, previous) => {
    store.setSpeechRate(value)
    if (
      value !== null &&
      store.analysisAuthorized &&
      !gated.value &&
      (previous === null || Math.abs(value - previous) >= 10)
    ) {
      emitEvidence({
        kind: 'speech-rate',
        value,
        unit: 'words_per_minute',
        observedAt: Date.now(),
        cooldownMs: 1500,
      })
    }
  }
)

watch(gated, (isGated) => {
  if (isGated) {
    wasSpeaking = false
    silenceStartedAt = null
  }
  drawTrack()
})

onMounted(() => {
  mounted.value = true
  drawTrack()
  void reconcile()
})

onUnmounted(() => {
  mounted.value = false
  generation += 1
  if (animationFrameId) cancelAnimationFrame(animationFrameId)
  animationFrameId = 0
  void releaseAudio()
})

defineExpose({ start, stop, resetBaseline })
</script>

<template>
  <section class="prosody-track" aria-label="可观察语音特征轨道">
    <canvas ref="canvasRef" />
    <div v-if="showMetrics" class="metrics" aria-live="polite">
      <span :class="{ active: store.prosody.speaking }">
        <i />
        {{ pauseText }}
      </span>
      <span>{{ pitchText }}</span>
      <span>{{ energyText }}</span>
      <span v-if="store.prosody.speechRateWpm !== null">
        语速 {{ Math.round(store.prosody.speechRateWpm) }} 词/分钟
      </span>
    </div>
    <div v-if="statusText" class="status" :class="{ error: localError }">{{ statusText }}</div>
  </section>
</template>

<style scoped lang="less">
.prosody-track {
  position: relative;
  width: 100%;
  min-width: 0;
  color: #33443e;
  border: 1px solid #dfe7e3;
  border-radius: 8px;
  background: #ffffff;
  overflow: hidden;
}

canvas {
  display: block;
  width: 100%;
  height: 108px;
}

.metrics {
  display: flex;
  align-items: center;
  gap: 14px;
  min-height: 28px;
  padding: 4px 8px;
  overflow-x: auto;
  color: #53655f;
  border-top: 1px solid #e7eeeb;
  font:
    500 11px/1.3 ui-monospace,
    SFMono-Regular,
    Menlo,
    monospace;
  white-space: nowrap;

  span:first-child {
    display: inline-flex;
    align-items: center;
    gap: 5px;
  }

  i {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: rgba(158, 181, 176, 0.55);
  }

  .active i {
    background: #148267;
    box-shadow: 0 0 8px rgba(20, 130, 103, 0.34);
  }
}

.status {
  position: absolute;
  top: 7px;
  right: 8px;
  max-width: calc(100% - 76px);
  padding: 3px 6px;
  color: #53655f;
  border: 1px solid rgba(207, 219, 214, 0.9);
  border-radius: 5px;
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 2px 8px rgba(32, 58, 49, 0.06);
  font-size: 10px;
  line-height: 1.35;
  pointer-events: none;

  &.error {
    color: #9a6417;
  }
}

@media (max-width: 620px) {
  .metrics {
    gap: 10px;
    min-height: 31px;
    padding: 5px 8px;
  }
}
</style>
