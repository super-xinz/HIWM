import { WS } from '@/helpers/ws'
import { SignalBody, TextPayload, WsEventTypes, WsProtocol } from '@/interface/eventType'
import { StreamState } from '@/interface/voiceChat'
import { AvatarHandler } from '@renderer/handlers/avatarHandler'
import { setupWebRTC, stop } from '@/utils/webrtcUtils'
import { message } from 'ant-design-vue'
import { nanoid } from 'nanoid'
import { defineStore } from 'pinia'
import { createWS } from '@/apis'
import { useAppStore } from './app'
import { useChatStore } from './chat'
import { useHiwmStore } from './hiwm'
import { useMediaStore } from './media'
import { useVisionStore } from './vision'
import { watch } from 'vue'

interface VideoChatState {
  streamState: StreamState
  peerConnection: RTCPeerConnection | null
  webRTCId: string
  gsLoadPercent: number
  localAvatarRenderer: AvatarHandler | null
  chatDataChannel: RTCDataChannel | null
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
      if (this.streamState === 'closed') {
        hiwmStore.clearSession()
        appStore.resetChatRecords()
        const mediaStream = mediaStore.stream
        const hasRealAudio = mediaStream
          ?.getAudioTracks()
          .some((track) => track.readyState === 'live')
        const hasRealVideo = mediaStream
          ?.getVideoTracks()
          .some((track) => track.readyState === 'live')
        if (!mediaStream || !hasRealAudio || !hasRealVideo) {
          message.error('需要真实摄像头和麦克风轨道，当前未建立连接')
          return
        }
        const peerConnection = new RTCPeerConnection(appStore.rtcConfig)
        this.peerConnection = peerConnection
        peerConnection.addEventListener('connectionstatechange', async () => {
          if (this.peerConnection !== peerConnection) return
          switch (peerConnection.connectionState) {
            case 'connected':
              this.streamState = StreamState.open
              break
            case 'disconnected':
            case 'failed':
            case 'closed':
              this.streamState = StreamState.closed
              this.webRTCId = ''
              this.chatDataChannel = null
              hiwmStore.clearSession()
              if (peerConnection.connectionState !== 'closed') {
                stop(peerConnection)
              }
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
            this.initChatDataChannel()

            if (appStore.avatarType === 'lam') {
              if (appStore.wsSessionRoute) {
                const ws = this.initWebsocket(appStore.wsSessionRoute, this.webRTCId)
                this.localAvatarRenderer = this.initAvatarHandler(ws, appStore.avatarAssetsPath)
                chatStore.showChatRecords = true
              }
            }
          })
          .catch((e: unknown) => {
            console.info('catching', e)
            this.streamState = StreamState.closed
            this.webRTCId = ''
            this.chatDataChannel = null
            hiwmStore.clearSession()
            const errorMessage = e instanceof Error ? e.message : String(e)
            message.error(errorMessage)
            message.error('真实会话连接失败，请检查后端状态与网络配置')
          })
      } else if (this.streamState === 'waiting') {
        // waiting 中不允许操作
      } else {
        stop(this.peerConnection!)
        this.streamState = StreamState.closed
        this.webRTCId = ''
        hiwmStore.clearSession()
        appStore.resetChatRecords()
        this.chatDataChannel = null
        chatStore.replying = false
        await mediaStore.accessDevice()
        if (appStore.avatarType === 'lam') {
          this.localAvatarRenderer?.exit()
          if (this.localAvatarRenderer instanceof AvatarHandler) {
            this.localAvatarRenderer.removeAllListeners()
          }
          this.localAvatarRenderer = null
          chatStore.setActiveRenderer(null)
          this.gsLoadPercent = 0
        }
      }
    },
    sendText(text: string) {
      if (!text || !this.chatDataChannel) return
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
      console.log('sendText', text)
      chatStore.replying = true
    },
    interrupt() {
      const chatStore = useChatStore()
      console.log('interrupt')
      const appStore = useAppStore()
      if (appStore.avatarType === 'lam') {
        this.localAvatarRenderer?.interrupt()
        chatStore.replying = false
      } else if (this.chatDataChannel) {
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
      const chatStore = useChatStore()
      const hiwmStore = useHiwmStore()
      this.chatDataChannel.addEventListener('message', (event) => {
        let data: unknown
        try {
          data = JSON.parse(event.data)
        } catch (error) {
          console.warn('Invalid RTC data channel message', error)
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
            }
          }
          if (typeof payload.text !== 'string' || payload.text.length === 0) return
          const role = headerName === WsProtocol.EchoAvatarText ? 'avatar' : 'human'
          chatStore.updateChatRecords({ ...payload, role }, role)
        } else if (
          headerName === WsProtocol.InterruptNotification ||
          headerName === WsProtocol.EndSpeech
        ) {
          chatStore.replying = false
        } else if (headerName === WsProtocol.ChatSignal) {
          chatStore.handleChatSignal((data.payload || {}) as SignalBody)
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
      ws.on(WsEventTypes.WS_ERROR, (event) => {
        console.log('socket error', event)
      })
      ws.on(WsEventTypes.WS_MESSAGE, (data) => {
        console.log('socket on message', data)
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
      console.log('🚀 ~ state-changed:', data)
      const { key, value } = data
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
