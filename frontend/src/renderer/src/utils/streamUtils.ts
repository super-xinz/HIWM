export function getDevices(): Promise<MediaDeviceInfo[]> {
  return navigator.mediaDevices.enumerateDevices()
}

export function handleError(error: string): void {
  throw new Error(error)
}

export function setLocalStream(
  local_stream: MediaStream | null,
  video_source: HTMLVideoElement
): void {
  video_source.srcObject = local_stream
  video_source.muted = true
  video_source.play()
}

export const MEDIA_PERMISSION_REQUEST_TIMEOUT_MS = 12_000

export class MediaPermissionTimeoutError extends Error {
  constructor() {
    super('设备权限请求超时，请检查浏览器权限后重试')
    this.name = 'MediaPermissionTimeoutError'
  }
}

const isSafariUserAgent = (userAgent: string): boolean =>
  /Safari/i.test(userAgent) && !/(Chrome|Chromium|CriOS|Edg|OPR|Firefox|FxiOS)/i.test(userAgent)

export function describeMediaAccessError(
  error: unknown,
  videoRequired: boolean,
  userAgent = typeof navigator === 'undefined' ? '' : navigator.userAgent
): string {
  const deviceLabel = videoRequired ? '摄像头和麦克风' : '麦克风'
  const errorName = error instanceof Error ? error.name : ''

  switch (errorName) {
    case 'NotAllowedError':
    case 'SecurityError':
      return isSafariUserAgent(userAgent)
        ? `${deviceLabel}权限被 Safari 或 macOS 阻止。请在 Safari 地址栏的网站设置中将相关权限设为“允许”，并在 macOS“系统设置 → 隐私与安全性”中确认 Safari 已获授权，然后再次点击。`
        : `${deviceLabel}权限被浏览器或系统阻止。请在当前网站的权限设置中改为“允许”，并检查系统隐私设置后再次点击。`
    case 'NotFoundError':
      return `未检测到可用的${deviceLabel}，请连接设备后再次点击。`
    case 'NotReadableError':
    case 'AbortError':
      return `${deviceLabel}暂时无法读取，可能正被其他应用占用。请关闭占用设备的应用后再次点击。`
    case 'OverconstrainedError':
      return `之前选择的${deviceLabel}已不可用，请重新选择设备后再次点击。`
    default:
      return error instanceof Error ? error.message : String(error)
  }
}

function stopStreamTracks(stream: MediaStream): void {
  stream.getTracks().forEach((track) => track.stop())
}

export async function requestMediaStreamWithTimeout(
  constraints: MediaStreamConstraints,
  timeoutMs = MEDIA_PERMISSION_REQUEST_TIMEOUT_MS
): Promise<MediaStream> {
  let timedOut = false
  let timeoutId: ReturnType<typeof setTimeout> | undefined
  const mediaRequest = navigator.mediaDevices.getUserMedia(constraints).then((stream) => {
    // A browser permission prompt cannot be cancelled. If it resolves after our
    // timeout, release the newly-created tracks instead of leaking camera/mic use.
    if (timedOut) stopStreamTracks(stream)
    return stream
  })

  try {
    return await Promise.race([
      mediaRequest,
      new Promise<never>((_, reject) => {
        timeoutId = setTimeout(() => {
          timedOut = true
          reject(new MediaPermissionTimeoutError())
        }, timeoutMs)
      }),
    ])
  } finally {
    if (timeoutId !== undefined) clearTimeout(timeoutId)
  }
}

export async function getStream(
  audio: { deviceId: { exact: string } } | boolean,
  video: { deviceId: { exact: string } } | boolean,
  track_constraints?: {
    video: MediaTrackConstraints
    audio: MediaTrackConstraints
  },
  permissionTimeoutMs = MEDIA_PERMISSION_REQUEST_TIMEOUT_MS
): Promise<MediaStream> {
  const video_fallback_constraints = track_constraints?.video || {}
  const audio_fallback_constraints = track_constraints?.audio || {}
  const constraints = {
    video:
      typeof video === 'object'
        ? { ...video, ...video_fallback_constraints }
        : video && video_fallback_constraints,
    audio:
      typeof audio === 'object'
        ? { ...audio, ...audio_fallback_constraints }
        : audio && audio_fallback_constraints,
  }
  console.debug('Requesting local media access', {
    audioRequested: constraints.audio !== false,
    videoRequested: constraints.video !== false,
  })
  return requestMediaStreamWithTimeout(constraints, permissionTimeoutMs).then(
    (local_stream: MediaStream) => {
      console.debug('Local media access ready', {
        audioTrackCount: local_stream.getAudioTracks().length,
        videoTrackCount: local_stream.getVideoTracks().length,
      })
      return local_stream
    }
  )
}

export function setAvailableDevices(
  devices: MediaDeviceInfo[],
  kind: 'videoinput' | 'audioinput' = 'videoinput'
): MediaDeviceInfo[] {
  const cameras = devices.filter((device: MediaDeviceInfo) => device.kind === kind)

  return cameras
}
