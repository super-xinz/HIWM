<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

import {
  DISPLAYED_FACE_LANDMARK_COUNT,
  type FacePerceptionFrame,
  type PerceptionEvidence,
  type PerceptionLandmark,
  usePerceptionStore,
} from '@/store/perception'

type NormalizedLandmark = {
  x: number
  y: number
  z?: number
}

type BlendshapeCategory = {
  categoryName?: string
  displayName?: string
  score?: number
}

type FaceLandmarkerResult = {
  faceLandmarks?: NormalizedLandmark[][]
  faceBlendshapes?: Array<{ categories?: BlendshapeCategory[] }>
  facialTransformationMatrixes?: Array<{ data?: number[] | Float32Array }>
}

type FaceLandmarkerInstance = {
  detectForVideo: (video: HTMLVideoElement, timestampMs: number) => FaceLandmarkerResult
  close?: () => void
}

type VisionTasksModule = {
  FilesetResolver: {
    forVisionTasks: (wasmBaseUrl: string) => Promise<unknown>
  }
  FaceLandmarker: {
    createFromOptions: (
      fileset: unknown,
      options: Record<string, unknown>
    ) => Promise<FaceLandmarkerInstance>
  }
}

type OverlayFit = 'cover' | 'contain' | 'fill'

type ActiveMarker = {
  region: 'brow' | 'mouth'
  text: string
  expiresAt: number
}

/**
 * A deliberately sparse, stable subset of MediaPipe's face mesh. It contains
 * contour, brows, eyes, nose and mouth points without drawing a full-face grid.
 */
const DISPLAY_LANDMARK_INDICES = [
  // Face contour (20)
  10, 338, 284, 389, 454, 361, 397, 379, 400, 152, 176, 150, 172, 132, 234, 162, 54, 67, 109, 151,
  // Brows (10)
  70, 63, 105, 66, 107, 336, 296, 334, 293, 300,
  // Eyes (16)
  33, 160, 158, 133, 153, 144, 163, 7, 362, 385, 387, 263, 373, 380, 390, 249,
  // Nose (8)
  168, 6, 1, 2, 98, 327, 197, 195,
  // Mouth (14)
  61, 185, 40, 39, 0, 269, 270, 409, 291, 375, 17, 146, 91, 181,
] as const

const SPARSE_CONNECTIONS = [
  [70, 63, 105, 66, 107],
  [336, 296, 334, 293, 300],
  [33, 160, 158, 133, 153, 144, 163, 7, 33],
  [362, 385, 387, 263, 373, 380, 390, 249, 362],
  [168, 6, 1, 2],
  [61, 185, 40, 39, 0, 269, 270, 409, 291, 375, 17, 146, 91, 181, 61],
] as const

if (DISPLAY_LANDMARK_INDICES.length !== DISPLAYED_FACE_LANDMARK_COUNT) {
  throw new Error('Face landmark display subset must contain exactly 68 points')
}

const props = withDefaults(
  defineProps<{
    video: HTMLVideoElement | null
    enabled?: boolean
    mirror?: boolean
    fit?: OverlayFit
    maxFps?: number
    showStatus?: boolean
    moduleUrl?: string
    wasmBaseUrl?: string
    modelAssetUrl?: string
  }>(),
  {
    enabled: true,
    mirror: true,
    fit: 'cover',
    maxFps: 24,
    showStatus: true,
    moduleUrl: 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.35/+esm',
    wasmBaseUrl: 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.35/wasm',
    modelAssetUrl:
      'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task',
  }
)

const emit = defineEmits<{
  ready: []
  frame: [frame: FacePerceptionFrame]
  evidence: [evidence: PerceptionEvidence]
  'face-lost': []
  error: [message: string]
}>()

const store = usePerceptionStore()
const canvasRef = ref<HTMLCanvasElement | null>(null)
const mounted = ref(false)
const localError = ref('')

let landmarker: FaceLandmarkerInstance | null = null
let initialization: Promise<void> | null = null
let animationFrameId = 0
let generation = 0
let lastDetectionAt = 0
let lastVideoTime = -1
let hadFace = false
let previousBrowInnerUp: number | null = null
let previousJawOpen: number | null = null
let previousYaw: number | null = null
let previousPitch: number | null = null
let activeMarkers: ActiveMarker[] = []

const active = computed(
  () => mounted.value && props.enabled && store.analysisAuthorized && Boolean(props.video)
)

const statusText = computed(() => {
  if (!props.showStatus) return ''
  if (!store.analysisAuthorized) return '分析未授权'
  if (store.face.modelStatus === 'loading') return '正在加载面部点阵…'
  if (store.face.modelStatus === 'unavailable') return '面部点阵暂不可用'
  if (store.face.modelStatus === 'ready' && !store.face.tracked) return '等待面部进入画面'
  return ''
})

const clamp = (value: number, minimum: number, maximum: number): number =>
  Math.min(maximum, Math.max(minimum, value))

const normalizeError = (error: unknown): string =>
  error instanceof Error ? error.message : String(error)

const moduleShape = (loaded: unknown): VisionTasksModule => {
  const candidate = loaded as Partial<VisionTasksModule> & { default?: Partial<VisionTasksModule> }
  const source = candidate.FilesetResolver ? candidate : candidate.default
  if (!source?.FilesetResolver || !source.FaceLandmarker) {
    throw new Error('MediaPipe vision module did not expose the expected API')
  }
  return source as VisionTasksModule
}

const createLandmarker = async (
  vision: VisionTasksModule,
  fileset: unknown,
  delegate?: 'GPU' | 'CPU'
): Promise<FaceLandmarkerInstance> =>
  vision.FaceLandmarker.createFromOptions(fileset, {
    baseOptions: {
      modelAssetPath: props.modelAssetUrl,
      ...(delegate ? { delegate } : {}),
    },
    runningMode: 'VIDEO',
    numFaces: 1,
    minFaceDetectionConfidence: 0.55,
    minFacePresenceConfidence: 0.55,
    minTrackingConfidence: 0.55,
    outputFaceBlendshapes: true,
    outputFacialTransformationMatrixes: true,
  })

async function initialize(): Promise<void> {
  if (landmarker || initialization) return initialization ?? Promise.resolve()
  const currentGeneration = generation
  store.setFaceModelStatus('loading')
  localError.value = ''

  initialization = (async () => {
    try {
      // A variable URL plus vite-ignore keeps MediaPipe optional and avoids a
      // package/lockfile change. Integrators may replace these URLs to self-host.
      const loaded: unknown = await import(/* @vite-ignore */ props.moduleUrl)
      const vision = moduleShape(loaded)
      const fileset = await vision.FilesetResolver.forVisionTasks(props.wasmBaseUrl)
      let instance: FaceLandmarkerInstance
      try {
        instance = await createLandmarker(vision, fileset, 'GPU')
      } catch {
        instance = await createLandmarker(vision, fileset, 'CPU')
      }

      if (currentGeneration !== generation || !mounted.value) {
        instance.close?.()
        return
      }
      landmarker = instance
      store.setFaceModelStatus('ready')
      emit('ready')
    } catch (error: unknown) {
      if (currentGeneration !== generation) return
      const detail = normalizeError(error)
      localError.value = detail
      store.setFaceModelStatus('unavailable', detail)
      emit('error', detail)
    } finally {
      initialization = null
    }
  })()

  return initialization
}

function clearCanvas(): void {
  const canvas = canvasRef.value
  if (!canvas) return
  const context = canvas.getContext('2d')
  context?.clearRect(0, 0, canvas.width, canvas.height)
}

function stopLoop(clearTracking = true): void {
  if (animationFrameId) cancelAnimationFrame(animationFrameId)
  animationFrameId = 0
  lastVideoTime = -1
  if (clearTracking) {
    hadFace = false
    previousBrowInnerUp = null
    previousJawOpen = null
    previousYaw = null
    previousPitch = null
    activeMarkers = []
    store.clearFace(true)
    clearCanvas()
  }
}

function scheduleFrame(): void {
  if (!animationFrameId && active.value) animationFrameId = requestAnimationFrame(processFrame)
}

async function reconcile(): Promise<void> {
  if (!active.value) {
    stopLoop()
    return
  }
  if (!landmarker) await initialize()
  if (landmarker && active.value) scheduleFrame()
}

function processFrame(timestamp: number): void {
  animationFrameId = 0
  if (!active.value || !landmarker) return

  const video = props.video
  const frameInterval = 1000 / clamp(props.maxFps, 1, 60)
  if (
    !video ||
    video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA ||
    timestamp - lastDetectionAt < frameInterval ||
    video.currentTime === lastVideoTime
  ) {
    scheduleFrame()
    return
  }

  lastDetectionAt = timestamp
  lastVideoTime = video.currentTime
  try {
    const result = landmarker.detectForVideo(video, timestamp)
    handleResult(result)
  } catch (error: unknown) {
    const detail = normalizeError(error)
    localError.value = detail
    store.setFaceModelStatus('unavailable', detail)
    emit('error', detail)
    stopLoop()
    return
  }
  scheduleFrame()
}

function handleResult(result: FaceLandmarkerResult): void {
  const fullLandmarks = result.faceLandmarks?.[0]
  if (!fullLandmarks?.length) {
    handleFaceLost()
    return
  }

  const observedAt = Date.now()
  const selectedLandmarks = DISPLAY_LANDMARK_INDICES.flatMap<PerceptionLandmark>((sourceIndex) => {
    const point = fullLandmarks[sourceIndex]
    return point
      ? [
          {
            sourceIndex,
            x: clamp(point.x, -0.25, 1.25),
            y: clamp(point.y, -0.25, 1.25),
            z: Number.isFinite(point.z) ? (point.z as number) : 0,
          },
        ]
      : []
  })
  const boundingBox = calculateBoundingBox(fullLandmarks)
  const pose = estimatePose(fullLandmarks, result.facialTransformationMatrixes?.[0]?.data)
  const categories = result.faceBlendshapes?.[0]?.categories ?? []
  const browInnerUp = blendshapeScore(categories, 'browInnerUp')
  const jawOpen = blendshapeScore(categories, 'jawOpen')
  const inFrame = fullLandmarks.filter(
    (point) => point.x >= 0 && point.x <= 1 && point.y >= 0 && point.y <= 1
  ).length
  const completeness = clamp(fullLandmarks.length / 468, 0, 1)
  const quality = clamp((inFrame / fullLandmarks.length) * 0.72 + completeness * 0.28, 0, 1)

  const frame: FacePerceptionFrame = {
    landmarks: selectedLandmarks,
    boundingBox,
    yaw: pose.yaw,
    pitch: pose.pitch,
    quality,
    browInnerUp,
    jawOpen,
    observedAt,
  }
  store.updateFace(frame)
  emit('frame', frame)

  if (!hadFace) emitEvidence({ kind: 'face-tracked', quality, observedAt, cooldownMs: 0 })
  detectVisibleChanges(frame)
  hadFace = true
  drawOverlay(fullLandmarks, frame)
}

function handleFaceLost(): void {
  if (hadFace) {
    emitEvidence({ kind: 'face-lost', observedAt: Date.now(), cooldownMs: 0 })
    emit('face-lost')
  }
  hadFace = false
  previousBrowInnerUp = null
  previousJawOpen = null
  previousYaw = null
  previousPitch = null
  activeMarkers = []
  store.clearFace(true)
  clearCanvas()
}

function emitEvidence(
  input: Parameters<typeof store.recordEvidence>[0]
): PerceptionEvidence | null {
  const evidence = store.recordEvidence(input)
  if (evidence) emit('evidence', evidence)
  return evidence
}

function detectVisibleChanges(frame: FacePerceptionFrame): void {
  const markerLifetime = 950
  const now = frame.observedAt
  if (previousBrowInnerUp !== null) {
    const delta = frame.browInnerUp - previousBrowInnerUp
    if (Math.abs(delta) >= 0.1) {
      const evidence = emitEvidence({
        kind: 'brow-inner-up',
        value: delta,
        quality: frame.quality,
        observedAt: now,
        metadata: { direction: delta >= 0 ? 'up' : 'down' },
      })
      if (evidence)
        activeMarkers.push({
          region: 'brow',
          text: evidence.label,
          expiresAt: now + markerLifetime,
        })
    }
  }
  if (previousJawOpen !== null) {
    const delta = frame.jawOpen - previousJawOpen
    if (Math.abs(delta) >= 0.12) {
      const evidence = emitEvidence({
        kind: 'jaw-open',
        value: delta,
        quality: frame.quality,
        observedAt: now,
        metadata: { direction: delta >= 0 ? 'up' : 'down' },
      })
      if (evidence)
        activeMarkers.push({
          region: 'mouth',
          text: evidence.label,
          expiresAt: now + markerLifetime,
        })
    }
  }
  if (previousYaw !== null && Math.abs(frame.yaw - previousYaw) >= 7) {
    emitEvidence({
      kind: 'head-yaw',
      value: frame.yaw,
      unit: 'degree',
      quality: frame.quality,
      observedAt: now,
      metadata: { direction: frame.yaw < previousYaw ? 'left' : 'right' },
      cooldownMs: 1200,
    })
  }
  if (previousPitch !== null && Math.abs(frame.pitch - previousPitch) >= 6) {
    emitEvidence({
      kind: 'head-pitch',
      value: frame.pitch,
      unit: 'degree',
      quality: frame.quality,
      observedAt: now,
      metadata: { direction: frame.pitch < previousPitch ? 'up' : 'down' },
      cooldownMs: 1200,
    })
  }
  previousBrowInnerUp = frame.browInnerUp
  previousJawOpen = frame.jawOpen
  previousYaw = frame.yaw
  previousPitch = frame.pitch
}

function calculateBoundingBox(landmarks: NormalizedLandmark[]): FacePerceptionFrame['boundingBox'] {
  let minimumX = 1
  let minimumY = 1
  let maximumX = 0
  let maximumY = 0
  landmarks.forEach((point) => {
    minimumX = Math.min(minimumX, point.x)
    minimumY = Math.min(minimumY, point.y)
    maximumX = Math.max(maximumX, point.x)
    maximumY = Math.max(maximumY, point.y)
  })
  return {
    x: clamp(minimumX, 0, 1),
    y: clamp(minimumY, 0, 1),
    width: clamp(maximumX - minimumX, 0, 1),
    height: clamp(maximumY - minimumY, 0, 1),
  }
}

function blendshapeScore(categories: BlendshapeCategory[], name: string): number {
  const category = categories.find(
    (item) => item.categoryName === name || item.displayName === name
  )
  return clamp(category?.score ?? 0, 0, 1)
}

function estimatePose(
  landmarks: NormalizedLandmark[],
  matrixData?: number[] | Float32Array
): { yaw: number; pitch: number } {
  if (matrixData && matrixData.length >= 16) {
    const matrix = Array.from(matrixData)
    const yaw = (Math.asin(clamp(-matrix[8], -1, 1)) * 180) / Math.PI
    const pitch = (Math.atan2(matrix[9], matrix[10]) * 180) / Math.PI
    if (
      Number.isFinite(yaw) &&
      Number.isFinite(pitch) &&
      Math.abs(yaw) <= 90 &&
      Math.abs(pitch) <= 90
    ) {
      return { yaw, pitch }
    }
  }

  const leftEye = averagePoint(landmarks, [33, 133])
  const rightEye = averagePoint(landmarks, [362, 263])
  const nose = landmarks[1]
  const chin = landmarks[152]
  if (!leftEye || !rightEye || !nose || !chin) return { yaw: 0, pitch: 0 }
  const eyeDistance = Math.max(0.001, Math.abs(rightEye.x - leftEye.x))
  const eyeMiddleX = (leftEye.x + rightEye.x) / 2
  const eyeMiddleY = (leftEye.y + rightEye.y) / 2
  const faceHeight = Math.max(0.001, chin.y - eyeMiddleY)
  return {
    yaw: clamp(((nose.x - eyeMiddleX) / eyeDistance) * 58, -50, 50),
    pitch: clamp((0.45 - (nose.y - eyeMiddleY) / faceHeight) * 75, -40, 40),
  }
}

function averagePoint(
  landmarks: NormalizedLandmark[],
  indices: number[]
): NormalizedLandmark | null {
  const points = indices
    .map((index) => landmarks[index])
    .filter((point): point is NormalizedLandmark => Boolean(point))
  if (!points.length) return null
  return {
    x: points.reduce((sum, point) => sum + point.x, 0) / points.length,
    y: points.reduce((sum, point) => sum + point.y, 0) / points.length,
    z: points.reduce((sum, point) => sum + (point.z ?? 0), 0) / points.length,
  }
}

function drawOverlay(landmarks: NormalizedLandmark[], frame: FacePerceptionFrame): void {
  const canvas = canvasRef.value
  const video = props.video
  if (!canvas || !video) return
  const cssWidth = canvas.clientWidth
  const cssHeight = canvas.clientHeight
  if (!cssWidth || !cssHeight || !video.videoWidth || !video.videoHeight) return

  const density = Math.min(window.devicePixelRatio || 1, 2)
  const pixelWidth = Math.round(cssWidth * density)
  const pixelHeight = Math.round(cssHeight * density)
  if (canvas.width !== pixelWidth || canvas.height !== pixelHeight) {
    canvas.width = pixelWidth
    canvas.height = pixelHeight
  }
  const context = canvas.getContext('2d')
  if (!context) return
  context.setTransform(density, 0, 0, density, 0, 0)
  context.clearRect(0, 0, cssWidth, cssHeight)

  const project = projector(
    video.videoWidth,
    video.videoHeight,
    cssWidth,
    cssHeight,
    props.fit,
    props.mirror
  )
  const projectedBoxStart = project(frame.boundingBox.x, frame.boundingBox.y)
  const projectedBoxEnd = project(
    frame.boundingBox.x + frame.boundingBox.width,
    frame.boundingBox.y + frame.boundingBox.height
  )
  const boxX = Math.min(projectedBoxStart.x, projectedBoxEnd.x)
  const boxY = Math.min(projectedBoxStart.y, projectedBoxEnd.y)
  const boxWidth = Math.abs(projectedBoxEnd.x - projectedBoxStart.x)
  const boxHeight = Math.abs(projectedBoxEnd.y - projectedBoxStart.y)

  context.save()
  context.strokeStyle = 'rgba(104, 224, 210, 0.62)'
  context.lineWidth = 1
  context.setLineDash([6, 5])
  context.strokeRect(boxX, boxY, boxWidth, boxHeight)
  context.setLineDash([])

  context.strokeStyle = 'rgba(106, 219, 211, 0.38)'
  context.lineWidth = 0.8
  SPARSE_CONNECTIONS.forEach((connection) => {
    context.beginPath()
    let started = false
    connection.forEach((sourceIndex) => {
      const point = landmarks[sourceIndex]
      if (!point) return
      const projected = project(point.x, point.y)
      if (!started) {
        context.moveTo(projected.x, projected.y)
        started = true
      } else {
        context.lineTo(projected.x, projected.y)
      }
    })
    context.stroke()
  })

  context.fillStyle = 'rgba(116, 235, 221, 0.72)'
  DISPLAY_LANDMARK_INDICES.forEach((sourceIndex) => {
    const point = landmarks[sourceIndex]
    if (!point) return
    const projected = project(point.x, point.y)
    context.beginPath()
    context.arc(projected.x, projected.y, 1.35, 0, Math.PI * 2)
    context.fill()
  })

  context.font = '500 11px ui-monospace, SFMono-Regular, Menlo, monospace'
  context.fillStyle = 'rgba(218, 255, 248, 0.92)'
  context.fillText(
    `yaw ${frame.yaw.toFixed(1)}°  pitch ${frame.pitch.toFixed(1)}°  track ${Math.round(frame.quality * 100)}%`,
    clamp(boxX, 8, Math.max(8, cssWidth - 270)),
    Math.max(14, boxY - 7)
  )

  const now = Date.now()
  activeMarkers = activeMarkers.filter((marker) => marker.expiresAt > now)
  activeMarkers.forEach((marker, index) => {
    const anchorX = boxX + boxWidth * 0.5
    const anchorY = marker.region === 'brow' ? boxY + boxHeight * 0.24 : boxY + boxHeight * 0.72
    const alpha = clamp((marker.expiresAt - now) / 500, 0.2, 1)
    context.fillStyle = `rgba(138, 255, 232, ${alpha})`
    context.fillText(marker.text, anchorX + 10, anchorY + index * 13)
  })
  context.restore()
}

function projector(
  sourceWidth: number,
  sourceHeight: number,
  targetWidth: number,
  targetHeight: number,
  fit: OverlayFit,
  mirror: boolean
): (x: number, y: number) => { x: number; y: number } {
  let scaleX = targetWidth / sourceWidth
  let scaleY = targetHeight / sourceHeight
  let offsetX = 0
  let offsetY = 0
  if (fit !== 'fill') {
    const scale = fit === 'cover' ? Math.max(scaleX, scaleY) : Math.min(scaleX, scaleY)
    scaleX = scale
    scaleY = scale
    offsetX = (targetWidth - sourceWidth * scale) / 2
    offsetY = (targetHeight - sourceHeight * scale) / 2
  }
  return (x, y) => ({
    x: offsetX + (mirror ? 1 - x : x) * sourceWidth * scaleX,
    y: offsetY + y * sourceHeight * scaleY,
  })
}

async function retry(): Promise<void> {
  generation += 1
  stopLoop()
  const pendingInitialization = initialization
  if (pendingInitialization) await pendingInitialization
  landmarker?.close?.()
  landmarker = null
  localError.value = ''
  if (active.value) await reconcile()
}

async function start(): Promise<void> {
  await reconcile()
}

function stop(): void {
  stopLoop()
}

watch(
  () => [props.video, props.enabled, store.analysisAuthorized] as const,
  () => void reconcile(),
  { flush: 'post' }
)

onMounted(() => {
  mounted.value = true
  void reconcile()
})

onUnmounted(() => {
  mounted.value = false
  generation += 1
  stopLoop()
  landmarker?.close?.()
  landmarker = null
})

defineExpose({ start, stop, retry })
</script>

<template>
  <div class="face-landmark-overlay" aria-label="可观察面部运动点阵">
    <canvas ref="canvasRef" aria-hidden="true" />
    <div v-if="statusText" class="overlay-status" :class="{ error: localError }">
      {{ statusText }}
    </div>
  </div>
</template>

<style scoped lang="less">
.face-landmark-overlay {
  position: absolute;
  z-index: 3;
  inset: 0;
  overflow: hidden;
  pointer-events: none;
}

canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.overlay-status {
  position: absolute;
  right: 12px;
  bottom: 12px;
  max-width: calc(100% - 24px);
  padding: 5px 9px;
  color: rgba(216, 255, 247, 0.82);
  border: 1px solid rgba(104, 224, 210, 0.2);
  border-radius: 6px;
  background: rgba(5, 20, 19, 0.66);
  font-size: 11px;
  line-height: 1.3;
  backdrop-filter: blur(5px);

  &.error {
    color: rgba(255, 229, 184, 0.88);
    border-color: rgba(232, 179, 92, 0.26);
  }
}
</style>
