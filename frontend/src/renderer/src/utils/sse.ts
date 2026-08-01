export function extractSseFrames(buffer: string): {
  events: Array<Record<string, unknown>>
  rest: string
} {
  const frames = buffer.replace(/\r\n/g, '\n').split('\n\n')
  const rest = frames.pop() || ''
  const events: Array<Record<string, unknown>> = []
  for (const frame of frames) {
    const data = frame
      .split('\n')
      .filter((line) => line.startsWith('data:'))
      .map((line) => line.slice(5).trimStart())
      .join('\n')
    if (!data) continue
    try {
      const value = JSON.parse(data)
      if (value && typeof value === 'object' && !Array.isArray(value)) events.push(value)
    } catch {
      events.push({
        type: 'error',
        code: 'invalid_stream_event',
        message: '服务返回了无效的流式事件',
      })
    }
  }
  return { events, rest }
}
