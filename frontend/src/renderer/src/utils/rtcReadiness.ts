export class RTCReadinessError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'RTCReadinessError'
  }
}

/**
 * SDP negotiation finishing does not mean the media transport and the text
 * DataChannel are usable yet. Wait for both so the UI cannot claim that the
 * assistant is online while ASR captions have no return path.
 */
export function waitForRTCReady(
  peerConnection: RTCPeerConnection,
  dataChannel: RTCDataChannel,
  timeoutMs = 15_000
): Promise<void> {
  return new Promise((resolve, reject) => {
    let settled = false

    const cleanup = (): void => {
      clearTimeout(timeout)
      peerConnection.removeEventListener('connectionstatechange', checkState)
      peerConnection.removeEventListener('iceconnectionstatechange', checkState)
      dataChannel.removeEventListener('open', checkState)
      dataChannel.removeEventListener('close', handleChannelClose)
      dataChannel.removeEventListener('error', handleChannelError)
    }

    const finish = (error?: RTCReadinessError): void => {
      if (settled) return
      settled = true
      cleanup()
      if (error) reject(error)
      else resolve()
    }

    const peerIsConnected = (): boolean =>
      peerConnection.connectionState === 'connected' ||
      peerConnection.iceConnectionState === 'connected' ||
      peerConnection.iceConnectionState === 'completed'

    function checkState(): void {
      if (
        peerConnection.connectionState === 'failed' ||
        peerConnection.connectionState === 'closed' ||
        peerConnection.iceConnectionState === 'failed' ||
        peerConnection.iceConnectionState === 'closed'
      ) {
        finish(new RTCReadinessError('互动连接失败'))
        return
      }
      if (peerIsConnected() && dataChannel.readyState === 'open') finish()
    }

    function handleChannelClose(): void {
      finish(new RTCReadinessError('字幕与控制通道在建立前已关闭'))
    }

    function handleChannelError(): void {
      finish(new RTCReadinessError('字幕与控制通道建立失败'))
    }

    const timeout = setTimeout(() => {
      finish(
        new RTCReadinessError(`连接超时（${Math.round(timeoutMs / 1000)} 秒），请检查网络后重试`)
      )
    }, timeoutMs)

    peerConnection.addEventListener('connectionstatechange', checkState)
    peerConnection.addEventListener('iceconnectionstatechange', checkState)
    dataChannel.addEventListener('open', checkState)
    dataChannel.addEventListener('close', handleChannelClose)
    dataChannel.addEventListener('error', handleChannelError)
    checkState()
  })
}
