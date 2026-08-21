import { defineStore } from 'pinia'

import {
  accessLogin,
  accessLogout,
  accessStatus,
  clearCompanionSession,
  companionChatStream,
  companionHealth,
  companionMessages,
  companionProfile,
  resetCompanionProfile,
  retryCompanionProfileUpdate,
} from '@/apis'
import { extractSseFrames } from '@/utils/sse'
import { COMPANION_SESSION_KEY, loadOrCreateCompanionSession } from '@/utils/companionSession'

export type CompanionMessage = {
  session_id: string
  user_id: string
  turn_id: string
  role: 'user' | 'assistant'
  content: string
  created_at: string
  model?: string | null
  profile_version?: number | null
  request_id: string
  pending?: boolean
  failed?: boolean
}

export type CompanionProfile = {
  profile_version?: number
  updated_at?: string
  overall_confidence?: number
  portrait?: Record<string, string | string[] | null>
  top_traits?: Array<{ group: string; name: string; value: number; confidence?: number }>
  interaction_preferences?: Record<string, unknown>
  current_state?: Record<string, unknown>
}

type Health = {
  status: 'ok' | 'degraded'
  services: Record<string, string>
  version: string
  access_protection: string
}

type ProfileUpdate = {
  status: 'updated' | 'unchanged' | 'failed' | 'skipped'
  profile_version?: number | null
  summary: string[]
  retryable: boolean
  error?: string | null
}

type StreamFinalResponse = {
  model?: string
  profile_update?: ProfileUpdate
  latency_ms?: Record<string, number>
}

type CompanionState = {
  authorized: boolean
  accessRequired: boolean
  accessReady: boolean
  userId: string
  sessionId: string
  messages: CompanionMessage[]
  profile: CompanionProfile | null
  health: Health | null
  profileEnabled: boolean
  sending: boolean
  error: string | null
  lastProfileUpdate: ProfileUpdate | null
  lastTurnId: string | null
  lastLatency: Record<string, number> | null
  abortController: AbortController | null
}

const createId = (prefix: string): string => {
  const value =
    typeof crypto?.randomUUID === 'function'
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random()}`
  return `${prefix}-${value}`
}

const loadSession = (): string =>
  loadOrCreateCompanionSession(typeof localStorage === 'undefined' ? undefined : localStorage, () =>
    createId('session')
  )

async function errorMessage(response: Response, fallback: string): Promise<string> {
  try {
    const body = await response.json()
    return typeof body.detail === 'string' ? body.detail : fallback
  } catch {
    return fallback
  }
}

export const useCompanionStore = defineStore('companionStore', {
  state: (): CompanionState => ({
    authorized: false,
    accessRequired: true,
    accessReady: false,
    userId: 'demo-xu',
    sessionId: loadSession(),
    messages: [],
    profile: null,
    health: null,
    profileEnabled: true,
    sending: false,
    error: null,
    lastProfileUpdate: null,
    lastTurnId: null,
    lastLatency: null,
    abortController: null,
  }),
  actions: {
    async initialize(): Promise<void> {
      try {
        const response = await accessStatus()
        const body = await response.json()
        this.authorized = body.authorized === true
        this.accessRequired = body.required === true
        if (typeof body.default_user_id === 'string') this.userId = body.default_user_id
        if (this.authorized) await this.refreshAll()
      } catch {
        this.error = '无法连接 HIWM 服务，请检查服务是否已启动'
      } finally {
        this.accessReady = true
      }
    },

    async login(code: string): Promise<boolean> {
      const response = await accessLogin(code)
      if (!response.ok) {
        this.error = await errorMessage(response, '访问口令验证失败')
        return false
      }
      this.authorized = true
      this.error = null
      await this.refreshAll()
      return true
    },

    async logout(): Promise<void> {
      await accessLogout()
      this.authorized = false
      this.messages = []
      this.profile = null
    },

    async refreshAll(): Promise<void> {
      await Promise.all([this.refreshHealth(), this.refreshProfile(), this.loadMessages()])
    },

    async refreshHealth(): Promise<void> {
      const response = await companionHealth()
      if (response.status === 401) {
        this.authorized = false
        return
      }
      if (response.ok) this.health = await response.json()
    },

    async refreshProfile(): Promise<void> {
      if (!this.profileEnabled) return
      const response = await companionProfile(this.userId)
      if (response.ok) {
        const body = await response.json()
        this.profile = body.profile
      }
    },

    async loadMessages(): Promise<void> {
      const response = await companionMessages(this.sessionId)
      if (response.ok) {
        const body = await response.json()
        this.messages = Array.isArray(body.messages) ? body.messages : []
      }
    },

    async send(message: string): Promise<void> {
      const text = message.trim()
      if (!text || this.sending) return
      const turnId = createId('turn')
      const requestId = createId('request')
      const createdAt = new Date().toISOString()
      this.messages.push({
        session_id: this.sessionId,
        user_id: this.userId,
        turn_id: turnId,
        role: 'user',
        content: text,
        created_at: createdAt,
        request_id: requestId,
      })
      const assistant: CompanionMessage = {
        session_id: this.sessionId,
        user_id: this.userId,
        turn_id: turnId,
        role: 'assistant',
        content: '',
        created_at: createdAt,
        request_id: requestId,
        pending: true,
      }
      this.messages.push(assistant)
      this.sending = true
      this.error = null
      this.lastTurnId = turnId
      const controller = new AbortController()
      this.abortController = controller
      try {
        const response = await companionChatStream(
          {
            user_id: this.userId,
            session_id: this.sessionId,
            turn_id: turnId,
            message: text,
            profile_enabled: this.profileEnabled,
          },
          controller.signal
        )
        if (!response.ok || !response.body) {
          throw new Error(await errorMessage(response, '聊天服务暂时不可用'))
        }
        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''
        while (true) {
          const { done, value } = await reader.read()
          buffer += decoder.decode(value || new Uint8Array(), { stream: !done })
          const parsed = extractSseFrames(buffer)
          buffer = parsed.rest
          for (const event of parsed.events) {
            if (event.type === 'meta' && typeof event.request_id === 'string') {
              assistant.request_id = event.request_id
            } else if (event.type === 'delta' && typeof event.content === 'string') {
              assistant.content += event.content
              this.messages = [...this.messages]
            } else if (
              event.type === 'final' &&
              event.response &&
              typeof event.response === 'object'
            ) {
              const result = event.response as StreamFinalResponse
              assistant.pending = false
              assistant.model = result.model
              assistant.profile_version = result.profile_update?.profile_version
              this.lastProfileUpdate = result.profile_update || null
              this.lastLatency = result.latency_ms || null
            } else if (event.type === 'error') {
              throw new Error(typeof event.message === 'string' ? event.message : '生成失败')
            }
          }
          if (done) break
        }
        assistant.pending = false
        await Promise.all([this.refreshProfile(), this.refreshHealth()])
      } catch (error) {
        assistant.pending = false
        assistant.failed = true
        this.error =
          error instanceof DOMException && error.name === 'AbortError'
            ? '已停止生成'
            : error instanceof Error
              ? error.message
              : '生成失败，请重试'
      } finally {
        this.sending = false
        this.abortController = null
        this.messages = [...this.messages]
      }
    },

    stop(): void {
      this.abortController?.abort()
    },

    async newSession(clearCurrent = false): Promise<void> {
      if (clearCurrent) await clearCompanionSession(this.sessionId)
      this.sessionId = createId('session')
      if (typeof localStorage !== 'undefined') {
        localStorage.setItem(COMPANION_SESSION_KEY, this.sessionId)
      }
      this.messages = []
      this.lastProfileUpdate = null
      this.lastTurnId = null
    },

    async resetProfile(): Promise<void> {
      const response = await resetCompanionProfile(this.userId)
      if (!response.ok) throw new Error(await errorMessage(response, '画像重置失败'))
      const body = await response.json()
      this.profile = body.profile
      await this.newSession(false)
    },

    async retryProfileUpdate(): Promise<void> {
      if (!this.lastTurnId) return
      const response = await retryCompanionProfileUpdate(this.sessionId, this.lastTurnId)
      if (!response.ok) throw new Error(await errorMessage(response, '画像更新重试失败'))
      const body = await response.json()
      this.lastProfileUpdate = body.profile_update
      await this.refreshProfile()
    },
  },
})
