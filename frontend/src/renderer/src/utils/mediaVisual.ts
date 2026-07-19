export interface VideoDimensions {
  videoWidth: number
  videoHeight: number
}

export function hasRenderableVideo(video?: VideoDimensions | null): boolean {
  return Boolean(video && video.videoWidth > 0 && video.videoHeight > 0)
}
