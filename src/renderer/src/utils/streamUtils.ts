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

export async function getStream(
  audio: { deviceId: { exact: string } } | boolean,
  video: { deviceId: { exact: string } } | boolean,
  track_constraints?: {
    video: MediaTrackConstraints
    audio: MediaTrackConstraints
  }
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
  console.log(constraints, 'constraints')
  return navigator.mediaDevices.getUserMedia(constraints).then((local_stream: MediaStream) => {
    console.log(local_stream)
    return local_stream
  })
}

export function setAvailableDevices(
  devices: MediaDeviceInfo[],
  kind: 'videoinput' | 'audioinput' = 'videoinput'
): MediaDeviceInfo[] {
  const cameras = devices.filter((device: MediaDeviceInfo) => device.kind === kind)

  return cameras
}
