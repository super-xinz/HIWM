const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)

const signalingFailureMessage = (code: string): string => {
  const messages: Record<string, string> = {
    concurrency_limit_reached: '上一会话仍在释放，请稍后重试',
    connection_already_exists: '这个会话已经存在，请重新开始',
    connection_closed: '会话连接已关闭，请重新开始',
  }
  return messages[code] ?? '会话服务拒绝了连接请求'
}

export class RTCSignalingError extends Error {
  readonly code: string

  constructor(code: string, message: string) {
    super(message)
    this.name = 'RTCSignalingError'
    this.code = code
  }
}

export async function readWebRTCAnswer(response: Response): Promise<RTCSessionDescriptionInit> {
  let payload: unknown
  try {
    payload = await response.json()
  } catch {
    throw new RTCSignalingError('invalid_json', '会话服务返回了无法识别的响应')
  }

  if (!response.ok) {
    throw new RTCSignalingError('http_error', `会话服务暂时不可用（HTTP ${response.status}）`)
  }

  if (isRecord(payload) && payload.status === 'failed') {
    const meta = isRecord(payload.meta) ? payload.meta : undefined
    const code = typeof meta?.error === 'string' ? meta.error : 'request_failed'
    throw new RTCSignalingError(code, signalingFailureMessage(code))
  }

  if (
    !isRecord(payload) ||
    payload.type !== 'answer' ||
    typeof payload.sdp !== 'string' ||
    !payload.sdp.trimStart().startsWith('v=0')
  ) {
    throw new RTCSignalingError('invalid_answer', '会话服务未返回有效的 WebRTC 应答')
  }

  return { type: 'answer', sdp: payload.sdp }
}
