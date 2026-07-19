import { webrtcClose, webrtcOffer } from '@/apis'
import { attachAndPlayRemoteMedia, type RemoteMediaPlaybackNode } from './remoteAudio'
import { waitForRTCReady } from './rtcReadiness'
import { readWebRTCAnswer } from './rtcSignaling'

const errorName = (error: unknown): string =>
  error instanceof Error && error.name ? error.name : 'UnknownError'

const trackKind = (kind: string): 'audio' | 'video' | 'other' =>
  kind === 'audio' || kind === 'video' ? kind : 'other'

const rtcMessageType = (raw: unknown, parsed: unknown): string => {
  const allowed = new Set([
    'change',
    'tick',
    'stopword',
    'warning',
    'error',
    'send_input',
    'fetch_output',
    'end_stream',
  ])
  const parsedType =
    typeof parsed === 'object' &&
    parsed !== null &&
    'type' in parsed &&
    typeof parsed.type === 'string'
      ? parsed.type
      : undefined
  const candidate = parsedType ?? (typeof raw === 'string' ? raw : undefined)
  return candidate && allowed.has(candidate) ? candidate : 'other'
}

export function createPeerConnection(pc: RTCPeerConnection, node: RemoteMediaPlaybackNode) {
  // register some listeners to help debugging
  pc.addEventListener(
    'icegatheringstatechange',
    () => {
      console.debug(pc.iceGatheringState)
    },
    false
  )

  pc.addEventListener(
    'iceconnectionstatechange',
    () => {
      console.debug(pc.iceConnectionState)
    },
    false
  )

  pc.addEventListener(
    'signalingstatechange',
    () => {
      console.debug(pc.signalingState)
    },
    false
  )

  // connect audio / video from server to local
  pc.addEventListener('track', (evt) => {
    const remoteStream = evt.streams[0] ?? new MediaStream([evt.track])
    console.debug('RTC remote track attached', {
      kind: trackKind(evt.track.kind),
      streamCount: evt.streams.length,
    })
    void attachAndPlayRemoteMedia(node, remoteStream)
  })

  return pc
}

export async function start(
  stream: MediaStream,
  pc: RTCPeerConnection,
  node: RemoteMediaPlaybackNode,
  server_fn: any,
  webrtc_id: string,
  modality: 'video' | 'audio' = 'video',
  on_change_cb: (msg: 'change' | 'tick') => void = () => {},
  rtp_params = {},
  additional_message_cb: (msg: object) => void = () => {},
  reject_cb: (msg: object) => void = () => {}
) {
  pc = createPeerConnection(pc, node)
  const data_channel = pc.createDataChannel('text')

  data_channel.onopen = () => {
    console.debug('Data channel is open')
    data_channel.send('handshake')
    data_channel.send(JSON.stringify({ type: 'init' }))
  }

  data_channel.onmessage = (event) => {
    let event_json
    try {
      event_json = JSON.parse(event.data)
    } catch {
      // Control frames such as "change" are intentionally not JSON.
    }
    console.debug('RTC data channel message received', {
      type: rtcMessageType(event.data, event_json),
    })
    if (
      event.data === 'change' ||
      event.data === 'tick' ||
      event.data === 'stopword' ||
      event_json?.type === 'warning' ||
      event_json?.type === 'error' ||
      event_json?.type === 'send_input' ||
      event_json?.type === 'fetch_output' ||
      event_json?.type === 'stopword' ||
      event_json?.type === 'end_stream'
    ) {
      on_change_cb(event_json ?? event.data)
    }
    additional_message_cb(event_json ?? event.data)
  }

  if (stream) {
    stream.getTracks().forEach(async (track) => {
      console.debug('RTC local track attached', {
        kind: trackKind(track.kind),
        readyState: track.readyState,
      })
      const sender = pc.addTrack(track, stream)
      const params = sender.getParameters()
      const updated_params = { ...params, ...rtp_params }
      await sender.setParameters(updated_params)
    })
  } else {
    console.debug('Creating transceiver!')
    pc.addTransceiver(modality, { direction: 'recvonly' })
  }

  await negotiate(pc, server_fn, webrtc_id, reject_cb)
  return [pc, data_channel] as const
}

function make_offer(
  server_fn: any,
  body: { sdp: string; type: RTCSdpType; webrtc_id: string },
  reject_cb: (msg: object) => void = () => {}
): Promise<any> {
  return new Promise((resolve, reject) => {
    server_fn(body).then((data: any) => {
      console.debug('RTC offer response received', {
        status: data?.status === 'failed' ? 'failed' : 'received',
      })
      if (data?.status === 'failed') {
        reject_cb(data)
        console.debug('rejecting')
        reject('error')
      }
      resolve(data)
    })
  })
}

async function negotiate(
  pc: RTCPeerConnection,
  server_fn: any,
  webrtc_id: string,
  reject_cb: (msg: object) => void = () => {}
): Promise<void> {
  pc.onicecandidate = ({ candidate }) => {
    if (candidate) {
      console.debug('RTC ICE candidate ready')
      server_fn({
        candidate: candidate.toJSON(),
        webrtc_id,
        type: 'ice-candidate',
      }).catch((error: unknown) =>
        console.error('RTC ICE candidate send failed', { errorName: errorName(error) })
      )
    }
  }

  return pc
    .createOffer()
    .then((offer) => {
      return pc.setLocalDescription(offer)
    })
    .then(() => {
      const offer = pc.localDescription!
      return make_offer(
        server_fn,
        {
          sdp: offer.sdp,
          type: offer.type,
          webrtc_id,
        },
        reject_cb
      )
    })
    .then((response) => {
      return response
    })
    .then((answer) => {
      return pc.setRemoteDescription(answer)
    })
}

export function stop(pc: RTCPeerConnection) {
  console.debug('Stopping peer connection')
  // close transceivers
  if (pc.getTransceivers) {
    pc.getTransceivers().forEach((transceiver) => {
      if (transceiver.stop) {
        transceiver.stop()
      }
    })
  }

  // close local audio / video
  if (pc.getSenders()) {
    pc.getSenders().forEach((sender) => {
      if (sender.track && sender.track.stop) sender.track.stop()
    })
  }

  // close peer connection
  setTimeout(() => {
    pc.close()
  }, 500)
}

export async function releaseWebRTC(webrtcId: string): Promise<void> {
  if (!webrtcId) return
  try {
    const response = await webrtcClose(webrtcId)
    if (!response.ok) {
      console.warn('RTC server-side release failed', { status: response.status })
    }
  } catch (error) {
    console.warn('RTC server-side release failed', { errorName: errorName(error) })
  }
}

export async function setupWebRTC(
  stream: MediaStream,
  peerConnection: RTCPeerConnection,
  remoteNode: HTMLVideoElement
) {
  //  Send audio-video stream to server
  stream.getTracks().forEach((track) => {
    peerConnection.addTrack(track, stream)
  })

  peerConnection.addEventListener('track', (evt) => {
    const remoteStream = evt.streams[0] ?? new MediaStream([evt.track])
    console.debug('RTC remote track attached', {
      kind: trackKind(evt.track.kind),
      streamCount: evt.streams.length,
    })
    void attachAndPlayRemoteMedia(remoteNode, remoteStream)
  })

  // Create data channel (needed!)
  const dataChannel = peerConnection.createDataChannel('text')

  // Create and send offer
  const offer = await peerConnection.createOffer()
  await peerConnection.setLocalDescription(offer)

  const webrtc_id = Math.random().toString(36).substring(7)

  // Send ICE candidates to server
  // (especially needed when server is behind firewall)
  peerConnection.onicecandidate = ({ candidate }) => {
    if (candidate) {
      console.debug('RTC ICE candidate ready')
      void webrtcOffer({
        candidate: candidate.toJSON(),
        webrtc_id,
        type: 'ice-candidate',
      }).catch((error: unknown) =>
        console.warn('RTC ICE candidate send failed', { errorName: errorName(error) })
      )
    }
  }

  try {
    // localDescription is the canonical offer after setLocalDescription().
    const localDescription = peerConnection.localDescription
    if (!localDescription) throw new Error('本地 WebRTC 应答尚未就绪')
    const response = await webrtcOffer({
      sdp: localDescription.sdp,
      type: localDescription.type,
      webrtc_id,
    })

    // FastRTC returns signaling failures as HTTP 200 JSON. Validate that the
    // payload is a real SDP answer before handing it to the browser parser.
    const serverResponse = await readWebRTCAnswer(response)
    await peerConnection.setRemoteDescription(serverResponse)
    await waitForRTCReady(peerConnection, dataChannel)
    return [dataChannel, webrtc_id] as const
  } catch (error) {
    // Failed negotiation otherwise occupies the single FastRTC slot until its
    // timeout and makes every immediate retry fail in exactly the same way.
    await releaseWebRTC(webrtc_id)
    throw error
  }
}
