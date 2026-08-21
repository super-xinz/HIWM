import { defineStore } from 'pinia'

import {
  accessLogin,
  accessLogout,
  accessStatus,
  clearCompanionSession,
  companionChatStream,
  companionExamples,
  companionHealth,
  companionMessages,
  companionProfile,
} from '@/apis'
import { extractSseFrames } from '@/utils/sse'
import { loadOrCreateCompanionSession, replaceCompanionSession } from '@/utils/companionSession'
import { type CompanionExample, parseCompanionExampleCatalog } from '@/utils/companionExamples'

export type { CompanionExample } from '@/utils/companionExamples'

export type CompanionMessage = {
  turn_id: string
  role: 'user' | 'assistant'
  content: string
  created_at: string
  pending?: boolean
  failed?: boolean
}

export type CompanionProfile = {
  portrait?: Record<string, string | string[] | null>
  top_traits?: Array<{ group: string; name: string; level: string }>
  interaction_preferences?: Record<string, unknown>
  current_state?: Record<string, unknown>
}

type Health = {
  status: 'ok' | 'degraded'
}

type CompanionState = {
  authorized: boolean
  accessRequired: boolean
  accessReady: boolean
  userId: string
  examples: CompanionExample[]
  defaultExampleId: string
  examplesReady: boolean
  switchingExample: boolean
  sessionId: string
  messages: CompanionMessage[]
  profile: CompanionProfile | null
  health: Health | null
  sending: boolean
  error: string | null
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
    userId: 'showcase-anchor',
    examples: [],
    defaultExampleId: 'showcase-anchor',
    examplesReady: false,
    switchingExample: false,
    sessionId: loadSession(),
    messages: [],
    profile: null,
    health: null,
    sending: false,
    error: null,
    abortController: null,
  }),
  actions: {
    async initialize(): Promise<void> {
      try {
        const response = await accessStatus()
        const body = await response.json()
        this.authorized = body.authorized === true
        this.accessRequired = body.required === true
        if (typeof body.default_example_id === 'string') this.userId = body.default_example_id
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
      await this.newSession(false)
      this.authorized = false
      this.messages = []
      this.profile = null
    },

    async refreshAll(): Promise<void> {
      await this.refreshExamples()
      await Promise.all([this.refreshHealth(), this.refreshProfile(), this.loadMessages()])
    },

    async refreshExamples(): Promise<void> {
      try {
        const response = await companionExamples()
        if (response.status === 401) {
          this.authorized = false
          return
        }
        if (!response.ok) throw new Error('示例角色加载失败')
        const catalog = parseCompanionExampleCatalog(await response.json(), this.userId)
        this.examples = catalog.examples
        this.defaultExampleId = catalog.defaultExampleId
        if (!this.examples.some((item) => item.id === this.userId)) {
          this.userId = this.defaultExampleId
        }
      } catch (error) {
        const catalog = parseCompanionExampleCatalog(null, this.userId)
        this.examples = catalog.examples
        this.defaultExampleId = catalog.defaultExampleId
        this.error = error instanceof Error ? error.message : '示例角色加载失败'
      } finally {
        this.examplesReady = true
      }
    },

    async selectExample(exampleId: string): Promise<void> {
      if (
        this.sending ||
        this.switchingExample ||
        exampleId === this.userId ||
        !this.examples.some((item) => item.id === exampleId)
      ) {
        return
      }
      this.switchingExample = true
      this.userId = exampleId
      this.profile = null
      this.error = null
      try {
        await this.newSession(false)
        await this.refreshProfile()
      } catch (error) {
        this.error = error instanceof Error ? error.message : '示例角色切换失败'
      } finally {
        this.switchingExample = false
      }
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
      const response = await companionProfile(this.userId)
      if (response.ok) {
        const body = await response.json()
        this.profile = body.profile
      }
    },

    async loadMessages(): Promise<void> {
      const response = await companionMessages(this.sessionId)
      if (response.status === 401) {
        this.authorized = false
        return
      }
      if (response.status === 403) {
        await this.newSession(false)
        return
      }
      if (response.ok) {
        const body = await response.json()
        this.messages = Array.isArray(body.messages) ? body.messages : []
      }
    },

    async send(message: string): Promise<void> {
      const text = message.trim()
      if (!text || this.sending) return
      const turnId = createId('turn')
      const createdAt = new Date().toISOString()
      this.messages.push({
        turn_id: turnId,
        role: 'user',
        content: text,
        created_at: createdAt,
      })
      const assistant: CompanionMessage = {
        turn_id: turnId,
        role: 'assistant',
        content: '',
        created_at: createdAt,
        pending: true,
      }
      this.messages.push(assistant)
      this.sending = true
      this.error = null
      const controller = new AbortController()
      this.abortController = controller
      try {
        const response = await companionChatStream(
          {
            user_id: this.userId,
            session_id: this.sessionId,
            turn_id: turnId,
            message: text,
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
            if (event.type === 'delta' && typeof event.content === 'string') {
              assistant.content += event.content
              this.messages = [...this.messages]
            } else if (
              event.type === 'final' &&
              event.response &&
              typeof event.response === 'object'
            ) {
              assistant.pending = false
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
      this.sessionId = replaceCompanionSession(
        typeof localStorage === 'undefined' ? undefined : localStorage,
        () => createId('session')
      )
      this.messages = []
    },
  },
})
