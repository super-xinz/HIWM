import { WS } from '@/helpers/ws'
import { readRuntimeControlToken } from '@/utils/projectStorage'
import { fetch, serverHost, serverOrigin, useSSL } from './base'

export { fetch }

export function initConfig(): Promise<Response> {
  return fetch('/api/v1/runtime/config')
}

export function accessStatus(): Promise<Response> {
  return fetch('/api/v1/access/status')
}

export function accessLogin(code: string): Promise<Response> {
  return fetch('/api/v1/access/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code }),
  })
}

export function accessLogout(): Promise<Response> {
  return fetch('/api/v1/access/logout', { method: 'POST' })
}

export function companionHealth(): Promise<Response> {
  return fetch('/api/v1/companion/health')
}

export function companionProfile(userId: string): Promise<Response> {
  return fetch(`/api/v1/companion/profile/${encodeURIComponent(userId)}`)
}

export function companionMessages(sessionId: string): Promise<Response> {
  return fetch(`/api/v1/companion/sessions/${encodeURIComponent(sessionId)}/messages`)
}

export function companionChatStream(
  body: Record<string, unknown>,
  signal: AbortSignal
): Promise<Response> {
  return fetch('/api/v1/companion/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify(body),
    signal,
  })
}

export function clearCompanionSession(sessionId: string): Promise<Response> {
  return fetch(`/api/v1/companion/sessions/${encodeURIComponent(sessionId)}`, {
    method: 'DELETE',
  })
}

export function resetCompanionProfile(userId: string): Promise<Response> {
  return fetch(`/api/v1/companion/profile/${encodeURIComponent(userId)}/reset`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ confirm: true }),
  })
}

export function retryCompanionProfileUpdate(sessionId: string, turnId: string): Promise<Response> {
  return fetch(
    `/api/v1/companion/sessions/${encodeURIComponent(sessionId)}/turns/${encodeURIComponent(turnId)}/profile-update:retry`,
    { method: 'POST' }
  )
}

export function webrtcOffer(body: Record<string, unknown>): Promise<Response> {
  return fetch('/webrtc/offer', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export function webrtcClose(webrtcId: string): Promise<Response> {
  return fetch('/webrtc/close', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ webrtc_id: webrtcId }),
  })
}

export function createWS(ws_route: string, webRTCId: string): WS {
  const token = readRuntimeControlToken()
  let url = `${useSSL ? 'wss' : 'ws'}://${serverHost}${ws_route}/${webRTCId}`
  if (token) {
    // 浏览器 WebSocket API 不支持自定义 headers，通过 URL 查询参数传递 token
    if (token) {
      url += `?token=${encodeURIComponent(token)}`
    }
  }
  const ws = new WS(url)

  return ws
}
export function createDataToolWS(): WS {
  const token = readRuntimeControlToken()
  let url = `${useSSL ? 'wss' : 'ws'}://${serverHost}/ws/manager/data_tool`
  if (token) {
    url += `?token=${encodeURIComponent(token)}`
  }
  return new WS(url)
}

export function makeURL(path: string): string {
  if (path.startsWith('http')) {
    return path
  }
  return `${serverOrigin}${path}`
}

export function makeDataToolFileURL(filePath: string): string {
  return `${useSSL ? 'https' : 'http'}://${serverHost}/download/manager/data_tool/file?file_path=${encodeURIComponent(filePath)}`
}
