import { defineStore } from 'pinia'
import { nanoid } from 'nanoid'
import { message } from 'ant-design-vue'

import EventEmitter from 'eventemitter3'

import { EventTypes, SignalBody, TextPayload } from '@/interface/eventType'
import { TYVoiceChatState } from '@/interface/voiceChat'

import { useAppStore } from './app'
import { useVisionStore } from './vision'

interface AvatarLike {
  setAvatarMute?(isMute: boolean): void
  interrupt?(): void
}

interface ChatState {
  volumeMuted: boolean
  showChatRecords: boolean
  replying: boolean
  playbackActive: boolean
  activeRenderer: AvatarLike | null
}

const accountStandingError = 'Access denied, please make sure your account is in good standing.'

export const useChatStore = defineStore('chatStore', {
  state: (): ChatState => ({
    volumeMuted: false,
    showChatRecords: false,
    replying: false,
    playbackActive: false,
    activeRenderer: null,
  }),
  actions: {
    setActiveRenderer(renderer: AvatarLike | null) {
      this.activeRenderer = renderer
    },

    handleVolumeMute() {
      this.volumeMuted = !this.volumeMuted
      this.activeRenderer?.setAvatarMute?.(this.volumeMuted)
    },

    handleSubtitleToggle() {
      this.showChatRecords = !this.showChatRecords
      this.updateWrapperRect()
    },

    updateWrapperRect() {
      const visionState = useVisionStore()
      const { wrapperRef, wrapperRect } = visionState
      if (!wrapperRef || !wrapperRect) return
      wrapperRef.getBoundingClientRect()
      wrapperRect.width = wrapperRef.clientWidth
      wrapperRect.height = wrapperRef.clientHeight
      visionState.isLandscape = wrapperRect.width > wrapperRect.height
    },

    updateChatRecords(
      payload: Partial<TextPayload> & Record<string, unknown>,
      role: 'human' | 'avatar'
    ) {
      const appStore = useAppStore()
      const streamKey =
        (payload?.stream_key as string) || (payload?.request_id as string) || nanoid()
      const id = `${role}-${streamKey}`
      const continueFromStream = payload.metadata?.continue_from_stream
      if (continueFromStream !== undefined && continueFromStream !== null) {
        const prevIndex = appStore.chatRecords.findLastIndex(
          (item) => item.role === role && item.id !== id
        )
        if (prevIndex >= 0) {
          const prev = appStore.chatRecords[prevIndex]
          appStore.chatRecords.splice(prevIndex, 1, {
            ...prev,
            invalid: true,
          })
          appStore.chatRecords = [...appStore.chatRecords]
        }
      }
      const index = appStore.chatRecords.findIndex((item) => item.id === id)
      const content = payload?.text || ''
      if (index !== -1) {
        const target = appStore.chatRecords[index]
        target.message = payload?.mode === 'increment' ? target.message + content : content
        Object.assign(target, payload)
        target.role = role
        appStore.chatRecords.splice(index, 1, target)
        appStore.chatRecords = [...appStore.chatRecords]
      } else {
        appStore.chatRecords = [
          ...appStore.chatRecords,
          {
            id,
            role,
            message: content,
            created_at_ms: Date.now(),
            ...(payload as TextPayload),
          },
        ]
      }
    },

    handleTextPayloadError(payload: Partial<TextPayload>, role: 'human' | 'avatar'): boolean {
      if (role !== 'human' || payload.metadata?.error !== true) return false

      const backendMessage =
        typeof payload.metadata.error_message === 'string'
          ? payload.metadata.error_message.trim()
          : ''
      const content = backendMessage.includes(accountStandingError)
        ? '语音服务暂时不可用，请联系管理员确认服务账户状态'
        : `语音识别暂时失败：${backendMessage || '请稍后重试'}`

      this.replying = false
      this.playbackActive = false
      message.error(content, 8)
      return true
    },

    markStreamCancelled(streamKey?: string) {
      if (!streamKey) return
      const appStore = useAppStore()
      const index = appStore.chatRecords.findIndex((item) => item.stream_key === streamKey)
      if (index === -1) return
      const target = appStore.chatRecords[index]
      appStore.chatRecords.splice(index, 1, {
        ...target,
        cancelled: true,
      })
      appStore.chatRecords = [...appStore.chatRecords]
    },

    handleChatSignal(signal?: SignalBody) {
      if (!signal) return
      if (signal.type === 'stream_cancel') {
        const keys = [signal.stream_key, ...(signal.parent_stream_keys || [])].filter(
          (key): key is string => Boolean(key)
        )
        const uniqueKeys = new Set(keys)
        uniqueKeys.forEach((key) => this.markStreamCancelled(key))
      }
      const signalType =
        signal.type === 'stream_begin' ||
        signal.type === 'stream_end' ||
        signal.type === 'stream_cancel' ||
        signal.type === 'interrupt'
          ? signal.type
          : 'other'
      console.debug('Chat signal handled', {
        type: signalType,
        clientPlayback: signal.stream_type === 'client_playback',
      })
      if (
        (signal.type === 'stream_cancel' || signal.type === 'stream_end') &&
        signal.stream_type === 'client_playback'
      ) {
        this.replying = false
        this.playbackActive = false
      } else if (signal.type === 'stream_begin' && signal.stream_type === 'client_playback') {
        this.replying = true
        this.playbackActive = true
      } else if (signal.type === 'interrupt') {
        this.replying = false
        this.playbackActive = false
      }
    },

    bindAvatarHandler(handler: EventEmitter) {
      handler.on(EventTypes.StateChanged, (state: TYVoiceChatState) => {
        this.playbackActive = state === TYVoiceChatState.Responding
        if (state === TYVoiceChatState.Responding) this.replying = true
        if (state === TYVoiceChatState.Idle) this.replying = false
      })

      handler.on(EventTypes.MessageReceived, (data) => {
        const eventData = data as {
          role?: 'human' | 'avatar'
          payload?: Partial<TextPayload>
        }
        const { payload, role } = eventData || {}
        if (!payload) return

        const normalizedRole = role === 'human' ? 'human' : 'avatar'
        if (this.handleTextPayloadError(payload, normalizedRole)) return
        if (typeof payload.text !== 'string' || payload.text.length === 0) return

        if (normalizedRole === 'human' && payload.end_of_speech !== false) {
          this.replying = true
          this.playbackActive = false
        }
        this.updateChatRecords({ ...payload, role: normalizedRole }, normalizedRole)
      })

      handler.on(EventTypes.SignalReceived, (data) => {
        this.handleChatSignal(data as SignalBody | undefined)
      })
    },
  },
})
