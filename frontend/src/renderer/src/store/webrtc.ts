import { WS } from '@/helpers/ws'
import { SignalBody, TextPayload, WsEventTypes, WsProtocol } from '@/interface/eventType'
import { StreamState } from '@/interface/voiceChat'
import { AvatarHandler } from '@renderer/handlers/avatarHandler'
import { releaseWebRTC, setupWebRTC, stop } from '@/utils/webrtcUtils'
import { message } from 'ant-design-vue'
import { nanoid } from 'nanoid'
import { defineStore } from 'pinia'
import { createWS } from '@/apis'
import { useAppStore } from './app'
import { useChatStore } from './chat'
import { useHiwmStore } from './hiwm'
import { useMediaStore } from './media'
import { type ClientObservationPayload, usePerceptionStore } from './perception'
import { type ClientSessionProfilePayload, useProfileStore } from './profile'
import { useVisionStore } from './vision'
import { watch } from 'vue'

interface VideoChatState {
  streamState: StreamState
  peerConnection: RTCPeerConnection | null
  webRTCId: string
  gsLoadPercent: number
  localAvatarRenderer: AvatarHandler | null
  chatDataChannel: RTCDataChannel | null
  chatChannelState: 'closed' | 'connecting' | 'open' | 'error'
}

const RTC_DISCONNECT_RECOVERY_MS = 5_000
const disconnectRecoveryTimers = new WeakMap<RTCPeerConnection, ReturnType<typeof setTimeout>>()

const hasLiveTrack = (stream: MediaStream | null, kind: 'audio' | 'video'): boolean =>
  Boolean(stream?.getTracks().some((track) => track.kind === kind && track.readyState === 'live'))

const clearDisconnectRecovery = (peerConnection: RTCPeerConnection): void => {
  const timer = disconnectRecoveryTimers.get(peerConnection)
  if (timer) clearTimeout(timer)
  disconnectRecoveryTimers.delete(peerConnection)
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)

const isIncomingTextPayload = (
  value: unknown
): value is Partial<TextPayload> & Record<string, unknown> => {
  if (!isRecord(value)) return false
  if (value.text !== undefined && typeof value.text !== 'string') return false
  if (value.metadata !== undefined && !isRecord(value.metadata)) return false
  if (
    isRecord(value.metadata) &&
    value.metadata.continue_from_stream !== undefined &&
    typeof value.metadata.continue_from_stream !== 'string'
  ) {
    return false
  }
  return true
}

export const useVideoChatStore = defineStore('videoChatStore', {
  state: (): VideoChatState => {
    return {
      streamState: StreamState.closed,
      peerConnection: null,
      webRTCId: '',
      gsLoadPercent: 0,
      localAvatarRenderer: null,
      chatDataChannel: null,
      chatChannelState: 'closed',
    }
  },
  getters: {},
  actions: {
    async startWebRTC() {
      const visionState = useVisionStore()
      const mediaStore = useMediaStore()
      const appStore = useAppStore()
      const chatStore = useChatStore()
      const hiwmStore = useHiwmStore()
      const perceptionStore = usePerceptionStore()
      const profileStore = useProfileStore()
      if (this.streamState === 'closed') {
        hiwmStore.clearTurnSnapshot()
        appStore.resetChatRecords()
        let mediaStream = mediaStore.stream
        let hasRealAudio = hasLiveTrack(mediaStream, 'audio')
        let hasRealVideo = hasLiveTrack(mediaStream, 'video')
        if (!mediaStream || !hasRealAudio || (mediaStore.videoRequired && !hasRealVideo)) {
          const recovered = await mediaStore.accessDevice()
          if (!recovered) return
          mediaStream = mediaStore.stream
          hasRealAudio = hasLiveTrack(mediaStream, 'audio')
          hasRealVideo = hasLiveTrack(mediaStream, 'video')
        }
        if (!mediaStream || !hasRealAudio || (mediaStore.videoRequired && !hasRealVideo)) {
          message.error(
            mediaStore.videoRequired
              ? '需要真实摄像头和麦克风轨道，当前未建立连接'
              : '需要真实麦克风轨道，当前未建立连接'
          )
          return
        }
        perceptionStore.resetSession()
        const peerConnection = new RTCPeerConnection(appStore.rtcConfig)
        this.peerConnection = peerConnection
        this.chatChannelState = 'connecting'
        const closeUnexpectedConnection = (): void => {
          if (this.peerConnection !== peerConnection) return
          clearDisconnectRecovery(peerConnection)
          const activeWebRTCId = this.webRTCId
          const activeChannel = this.chatDataChannel
          this.peerConnection = null
          this.streamState = StreamState.closed
          this.webRTCId = ''
          this.chatDataChannel = null
          this.chatChannelState = 'error'
          hiwmStore.clearTurnSnapshot()
          perceptionStore.resetSession()
          chatStore.replying = false
          chatStore.playbackActive = false
          if (activeChannel?.readyState === 'open') activeChannel.close()
          if (peerConnection.connectionState !== 'closed') stop(peerConnection)
          if (activeWebRTCId) void releaseWebRTC(activeWebRTCId)
          message.error('媒体连接已断开，点击开始对话即可重新连接')
        }
        peerConnection.addEventListener('connectionstatechange', () => {
          if (this.peerConnection !== peerConnection) return
          switch (peerConnection.connectionState) {
            case 'connected':
              clearDisconnectRecovery(peerConnection)
              if (this.chatDataChannel?.readyState === 'open') {
                this.streamState = StreamState.open
                this.chatChannelState = 'open'
              }
              break
            case 'disconnected':
              if (!disconnectRecoveryTimers.has(peerConnection)) {
                disconnectRecoveryTimers.set(
                  peerConnection,
                  setTimeout(() => {
                    disconnectRecoveryTimers.delete(peerConnection)
                    if (peerConnection.connectionState === 'disconnected') {
                      closeUnexpectedConnection()
                    }
                  }, RTC_DISCONNECT_RECOVERY_MS)
                )
              }
              break
            case 'failed':
            case 'closed':
              closeUnexpectedConnection()
              break
            default:
              break
          }
        })
        this.streamState = StreamState.waiting
        await setupWebRTC(mediaStream, peerConnection, visionState.remoteVideoRef!)
          .then(([dataChannel, webRTCId]) => {
            this.streamState = StreamState.open
            this.webRTCId = webRTCId as string
            hiwmStore.beginSession(this.webRTCId)
            this.chatDataChannel = dataChannel as RTCDataChannel
            this.chatChannelState = 'open'
            this.initChatDataChannel()
            const profilePayload = profileStore.toClientPayload()
            if (!this.sendSessionProfile(profilePayload)) {
              this.chatDataChannel.addEventListener(
                'open',
                () => this.sendSessionProfile(profilePayload),
                { once: true }
              )
            }

            if (appStore.avatarType === 'lam') {
              if (appStore.wsSessionRoute) {
                const ws = this.initWebsocket(appStore.wsSessionRoute, this.webRTCId)
                this.localAvatarRenderer = this.initAvatarHandler(ws, appStore.avatarAssetsPath)
                chatStore.showChatRecords = true
              }
            }
          })
          .catch((e: unknown) => {
            console.info('RTC session setup failed', {
              errorName: e instanceof Error && e.name ? e.name : 'UnknownError',
            })
            this.streamState = StreamState.closed
            this.webRTCId = ''
            this.chatDataChannel = null
            this.chatChannelState = 'error'
            hiwmStore.clearTurnSnapshot()
            perceptionStore.resetSession()
            chatStore.replying = false
            chatStore.playbackActive = false
            if (this.peerConnection === peerConnection) this.peerConnection = null
            clearDisconnectRecovery(peerConnection)
            if (peerConnection.connectionState !== 'closed') peerConnection.close()
            const errorMessage = e instanceof Error ? e.message : String(e)
            message.error(`真实会话连接失败：${errorMessage}`)
          })
      } else if (this.streamState === 'waiting') {
        // waiting 中不允许操作
      } else {
        await this.stopWebRTC(true)
      }
    },
    async stopWebRTC(reacquireDevices = false) {
      const appStore = useAppStore()
      const chatStore = useChatStore()
      const hiwmStore = useHiwmStore()
      const mediaStore = useMediaStore()
      const perceptionStore = usePerceptionStore()
      const activeWebRTCId = this.webRTCId
      const activeChannel = this.chatDataChannel
      this.chatDataChannel = null
      this.chatChannelState = 'closed'
      if (this.peerConnection) stop(this.peerConnection)
      this.peerConnection = null
      this.streamState = StreamState.closed
      this.webRTCId = ''
      hiwmStore.clearTurnSnapshot()
      appStore.resetChatRecords()
      perceptionStore.resetSession()
      chatStore.replying = false
      chatStore.playbackActive = false
      if (activeChannel?.readyState === 'open') activeChannel.close()
      if (activeWebRTCId) await releaseWebRTC(activeWebRTCId)
      if (appStore.avatarType === 'lam') {
        this.localAvatarRenderer?.exit()
        if (this.localAvatarRenderer instanceof AvatarHandler) {
          this.localAvatarRenderer.removeAllListeners()
        }
        this.localAvatarRenderer = null
        chatStore.setActiveRenderer(null)
        this.gsLoadPercent = 0
      }
      if (reacquireDevices) await mediaStore.accessDevice()
    },
    sendText(text: string) {
      if (!text) return
      if (!this.chatDataChannel || this.chatDataChannel.readyState !== 'open') {
        message.error('字幕与控制通道未连接，请重新开始会话')
        return
      }
      const chatStore = useChatStore()
      this.chatDataChannel.send(
        JSON.stringify({
          header: {
            name: WsProtocol.SendHumanText,
            request_id: nanoid(),
          },
          payload: {
            request_id: nanoid(),
            stream_key: nanoid(),
            mode: 'full_text',
            text,
            end_of_speech: true,
          },
        })
      )
      chatStore.replying = true
      chatStore.playbackActive = false
    },
    sendClientObservation(payload: ClientObservationPayload): boolean {
      const channel = this.chatDataChannel
      if (!channel || channel.readyState !== 'open') return false
      channel.send(
        JSON.stringify({
          header: {
            name: WsProtocol.SendClientObservation,
            request_id: nanoid(),
          },
          payload,
        })
      )
      return true
    },
    sendSessionProfile(payload: ClientSessionProfilePayload): boolean {
      const channel = this.chatDataChannel
      if (!channel || channel.readyState !== 'open') return false
      channel.send(
        JSON.stringify({
          header: {
            name: WsProtocol.SendSessionProfile,
            request_id: nanoid(),
          },
          payload,
        })
      )
      return true
    },
    interrupt() {
      const chatStore = useChatStore()
      console.log('interrupt')
      const appStore = useAppStore()
      if (appStore.avatarType === 'lam') {
        this.localAvatarRenderer?.interrupt()
        chatStore.replying = false
        chatStore.playbackActive = false
      } else if (this.chatDataChannel?.readyState === 'open') {
        this.chatDataChannel.send(
          JSON.stringify({
            header: {
              name: WsProtocol.Interrupt,
              request_id: nanoid(),
            },
            payload: {},
          })
        )
      }
    },
    initChatDataChannel() {
      if (!this.chatDataChannel) return
      const channel = this.chatDataChannel
      const chatStore = useChatStore()
      const hiwmStore = useHiwmStore()
      channel.addEventListener('open', () => {
        if (this.chatDataChannel !== channel) return
        this.chatChannelState = 'open'
      })
      channel.addEventListener('close', () => {
        if (this.chatDataChannel !== channel) return
        const peerConnection = this.peerConnection
        this.peerConnection = null
        this.chatChannelState = 'closed'
        this.streamState = StreamState.closed
        this.webRTCId = ''
        this.chatDataChannel = null
        hiwmStore.clearTurnSnapshot()
        chatStore.replying = false
        chatStore.playbackActive = false
        if (peerConnection && peerConnection.connectionState !== 'closed') peerConnection.close()
        message.error('字幕与控制通道已断开，请重新开始会话')
      })
      channel.addEventListener('error', () => {
        if (this.chatDataChannel !== channel) return
        this.chatChannelState = 'error'
        chatStore.replying = false
        chatStore.playbackActive = false
        message.error('字幕与控制通道异常，本轮输入可能无法回显')
      })
      channel.addEventListener('message', (event) => {
        let data: unknown
        try {
          data = JSON.parse(event.data)
        } catch {
          console.warn('Invalid RTC data channel message')
          return
        }
        if (!isRecord(data)) return
        const headerName =
          isRecord(data.header) && typeof data.header.name === 'string'
            ? data.header.name
            : undefined
        if (headerName === WsProtocol.EchoHumanText || headerName === WsProtocol.EchoAvatarText) {
          if (!isIncomingTextPayload(data.payload)) return
          const payload = data.payload
          if (headerName === WsProtocol.EchoAvatarText) {
            hiwmStore.consumeAvatarMetadata(payload.metadata)
            if (isRecord(payload.metadata) && 'hiwm_error' in payload.metadata) {
              chatStore.replying = false
              chatStore.playbackActive = false
            }
          } else if (chatStore.handleTextPayloadError(payload, 'human')) {
            return
          }
          if (typeof payload.text !== 'string' || payload.text.length === 0) return
          const role = headerName === WsProtocol.EchoAvatarText ? 'avatar' : 'human'
          if (role === 'human' && payload.end_of_speech !== false) {
            chatStore.replying = true
            chatStore.playbackActive = false
          }
          chatStore.updateChatRecords({ ...payload, role }, role)
        } else if (
          headerName === WsProtocol.InterruptNotification ||
          headerName === WsProtocol.EndSpeech
        ) {
          chatStore.replying = false
          chatStore.playbackActive = false
        } else if (headerName === WsProtocol.ChatSignal) {
          chatStore.handleChatSignal((data.payload || {}) as SignalBody)
        } else if (headerName === WsProtocol.Error) {
          const backendMessage =
            isRecord(data.payload) && typeof data.payload.message === 'string'
              ? data.payload.message.slice(0, 240)
              : '后端返回了未知错误'
          chatStore.replying = false
          chatStore.playbackActive = false
          message.error(backendMessage)
        }
      })
    },
    initWebsocket(ws_route: string, webRTCId: string): WS {
      const ws = createWS(ws_route, webRTCId)
      ws.on(WsEventTypes.WS_OPEN, () => {
        console.log('socket opened')
      })
      ws.on(WsEventTypes.WS_CLOSE, () => {
        console.log('socket closed')
      })
      ws.on(WsEventTypes.WS_ERROR, () => {
        console.warn('Avatar WebSocket error')
      })
      ws.on(WsEventTypes.WS_MESSAGE, (data) => {
        void data
      })
      return ws
    },
    initAvatarHandler(ws: WS, assetsPath: string): AvatarHandler {
      const visionState = useVisionStore()
      const chatStore = useChatStore()
      const handler = new AvatarHandler({
        container: visionState.remoteVideoContainerRef!,
        assetsPath,
        ws,
        rendererType: 'lam',
        loadProgress: (progress) => {
          console.log('gs loadProgress', progress)
          this.gsLoadPercent = progress
        },
      })

      chatStore.bindAvatarHandler(handler)
      chatStore.setActiveRenderer(handler)

      return handler
    },
  },
})

export function setupElectron(): void {
  if (window.electron) {
    const chatStore = useChatStore()
    window.electron.ipcRenderer.on('state-changed', (_event, data) => {
      void _event
      const { key, value } = data
      console.debug('Electron state changed', {
        key:
          key === 'toolsVisible' || key === 'inputVisible' || key === 'showChatRecords'
            ? key
            : 'other',
      })
      const appStore = useAppStore()
      if (key in appStore.$state) {
        ;(appStore as unknown as Record<string, unknown>)[key] = value
      } else if (key in chatStore.$state) {
        ;(chatStore as unknown as Record<string, unknown>)[key] = value
      } else {
        const videoChatStore = useVideoChatStore()
        ;(videoChatStore as unknown as Record<string, unknown>)[key] = value
      }
    })
    window.electron.ipcRenderer.send('app-ready')
    watch(
      () => chatStore.showChatRecords,
      (newValue) => {
        console.log('🚀 ~ newValue:', newValue)
        window.electron.ipcRenderer.send('state-changed', {
          key: 'showChatRecords',
          value: newValue,
        })
      }
    )
    window.addEventListener('resize', () => {
      if (chatStore.showChatRecords) {
        chatStore.updateWrapperRect()
      }
    })
  }
}
