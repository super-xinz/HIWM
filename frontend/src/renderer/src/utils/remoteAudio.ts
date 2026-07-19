export interface RemoteMediaPlaybackNode {
  srcObject: unknown
  volume: number
  muted: boolean
  autoplay: boolean
  play: () => Promise<unknown>
}

interface RemoteAudioOutputState {
  context: AudioContext | null
  gain: GainNode | null
  source: MediaStreamAudioSourceNode | null
  stream: MediaStream | null
  muted: boolean
  webAudioActive: boolean
}

const remoteAudioOutputs = new WeakMap<object, RemoteAudioOutputState>()

const playbackErrorName = (error: unknown): string =>
  error instanceof Error && error.name ? error.name : 'UnknownError'

const isMediaStream = (value: unknown): value is MediaStream =>
  typeof value === 'object' &&
  value !== null &&
  'getAudioTracks' in value &&
  typeof value.getAudioTracks === 'function'

function getOutputState(node: RemoteMediaPlaybackNode): RemoteAudioOutputState {
  const existing = remoteAudioOutputs.get(node)
  if (existing) return existing
  const created: RemoteAudioOutputState = {
    context: null,
    gain: null,
    source: null,
    stream: null,
    muted: false,
    webAudioActive: false,
  }
  remoteAudioOutputs.set(node, created)
  return created
}

async function connectWebAudioOutput(
  node: RemoteMediaPlaybackNode,
  stream: MediaStream
): Promise<boolean> {
  const state = getOutputState(node)
  const { context, gain } = state
  if (!context || !gain || stream.getAudioTracks().length === 0) return false

  try {
    if (context.state === 'suspended') await context.resume()
    if (state.stream !== stream || !state.source) {
      state.source?.disconnect()
      const source = context.createMediaStreamSource(stream)
      source.connect(gain)
      state.source = source
      state.stream = stream
    }
    gain.gain.value = state.muted ? 0 : 1
    state.webAudioActive = true
    // Web Audio owns speaker output. Keep native media muted to avoid double playback.
    node.muted = true
    return true
  } catch (error) {
    state.webAudioActive = false
    node.muted = state.muted
    console.debug('Web Audio speaker output failed', { errorName: playbackErrorName(error) })
    return false
  }
}

export async function unlockRemoteAudioOutput(node: RemoteMediaPlaybackNode): Promise<boolean> {
  const state = getOutputState(node)
  const AudioContextConstructor =
    (globalThis as typeof globalThis & { webkitAudioContext?: typeof AudioContext }).AudioContext ||
    (globalThis as typeof globalThis & { webkitAudioContext?: typeof AudioContext })
      .webkitAudioContext

  if (!AudioContextConstructor) return false

  try {
    if (!state.context) {
      state.context = new AudioContextConstructor({ latencyHint: 'interactive' })
      state.gain = state.context.createGain()
      state.gain.connect(state.context.destination)
      state.gain.gain.value = state.muted ? 0 : 1
    }
    if (state.context.state === 'suspended') await state.context.resume()
    if (isMediaStream(node.srcObject)) {
      await connectWebAudioOutput(node, node.srcObject)
    }
    return state.context.state === 'running'
  } catch (error) {
    console.debug('Web Audio output could not be unlocked', {
      errorName: playbackErrorName(error),
    })
    return false
  }
}

export function setRemoteAudioMuted(node: RemoteMediaPlaybackNode, muted: boolean): void {
  const state = getOutputState(node)
  state.muted = muted
  if (state.gain) state.gain.gain.value = muted ? 0 : 1
  node.muted = state.webAudioActive ? true : muted
}

export function releaseRemoteAudioOutput(node: RemoteMediaPlaybackNode): void {
  const state = remoteAudioOutputs.get(node)
  if (!state) return
  state.source?.disconnect()
  state.gain?.disconnect()
  if (state.context && state.context.state !== 'closed') void state.context.close()
  remoteAudioOutputs.delete(node)
}

export async function attachAndPlayRemoteMedia(
  node: RemoteMediaPlaybackNode,
  stream: MediaStream
): Promise<boolean> {
  if (node.srcObject !== stream) node.srcObject = stream
  node.volume = 1
  node.autoplay = true
  const webAudioReady = await connectWebAudioOutput(node, stream)
  try {
    await node.play()
    return true
  } catch (error) {
    console.debug('RTC autoplay failed', { errorName: playbackErrorName(error) })
    return webAudioReady
  }
}
