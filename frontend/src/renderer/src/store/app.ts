import { message } from 'ant-design-vue'
import { defineStore } from 'pinia'

import { configureRuntimeApiKey, initConfig, makeURL } from '@/apis'
import {
  isDashscopeRuntimeKeyReady,
  parsePublicApiConfig,
  type ApiConfigLoadState,
  type PublicApiConfig,
} from '@/interface/apiConfig'
import { useMediaStore } from './media'
import { TextPayload } from '@renderer/interface/eventType'

type ChatRecord = {
  id: string
  role: 'human' | 'avatar'
  message: string
  created_at_ms: number
  cancelled?: boolean
  invalid?: boolean
} & TextPayload

interface AppState {
  avatarType: '' | 'lam'
  avatarWSRoute: string
  wsSessionRoute: string
  avatarAssetsPath: string
  rtcConfig: RTCConfiguration | undefined
  chatMode: 'webrtc' | 'ws'
  chatRecords: ChatRecord[]
  apiConfig: PublicApiConfig | null
  apiConfigStatus: ApiConfigLoadState
  apiConfigError: string | null

  toolsVisible: boolean
  inputVisible: boolean
}

export const useAppStore = defineStore('appStore', {
  state: (): AppState => ({
    avatarType: '',
    avatarWSRoute: '',
    wsSessionRoute: '',
    avatarAssetsPath: '',
    rtcConfig: undefined,
    chatMode: 'webrtc',
    chatRecords: [],
    apiConfig: null,
    apiConfigStatus: 'loading',
    apiConfigError: null,
    toolsVisible: true,
    inputVisible: true,
  }),
  actions: {
    async init() {
      const mediaStore = useMediaStore()
      this.apiConfig = null
      this.apiConfigStatus = 'loading'
      this.apiConfigError = null
      return initConfig()
        .then((res) => res.json())
        .then((config) => {
          if (config.detail) {
            this.apiConfigStatus = 'error'
            this.apiConfigError = '初始化接口返回错误，未能读取 API 配置'
            message.error(config.detail)
            return
          }
          if (!Object.prototype.hasOwnProperty.call(config, 'api_config')) {
            this.apiConfigStatus = 'missing'
            this.apiConfigError = '后端未提供 api_config'
          } else {
            const result = parsePublicApiConfig(config.api_config)
            if (result.ok) {
              this.apiConfig = result.config
              this.apiConfigStatus = 'ready'
            } else {
              this.apiConfigStatus = 'error'
              this.apiConfigError = result.reason
            }
          }
          if (config.rtc_configuration) {
            this.rtcConfig = config.rtc_configuration
          }
          if (config.chat_mode) {
            this.chatMode = config.chat_mode === 'ws' ? 'ws' : 'webrtc'
          }
          config.avatar_config = config.avatar_config || {}
          if (config.avatar_config) {
            this.avatarType = config.avatar_config.avatar_type || ''
            this.avatarWSRoute = config.avatar_config.avatar_ws_route || ''
            this.avatarAssetsPath = config.avatar_config.avatar_assets_path
              ? makeURL(config.avatar_config.avatar_assets_path)
              : ''
            if (config.avatar_config.ws_session_route) {
              this.wsSessionRoute = config.avatar_config.ws_session_route
              if (!this.avatarWSRoute) {
                this.avatarWSRoute = config.avatar_config.ws_session_route
              }
            }
          }
          if (config.ws_session_route) {
            this.wsSessionRoute = config.ws_session_route
            if (!this.avatarWSRoute) {
              this.avatarWSRoute = config.ws_session_route
            }
          }
          if (config.track_constraints) {
            mediaStore.setTrackConstraints(config.track_constraints)
          }
        })
        .catch((e) => {
          this.apiConfig = null
          this.apiConfigStatus = 'error'
          this.apiConfigError = '无法连接后端初始化接口'
          message.error(
            `服务端链接失败，请检查是否能正确访问到 HIWM 服务端: ${e instanceof Error ? e.message : String(e)}`
          )
        })
    },
    async configureRuntimeApiKey(apiKey: string): Promise<boolean> {
      const response = await configureRuntimeApiKey(apiKey)
      const payload = await response.json().catch(() => null)
      if (!response.ok) {
        const detail =
          payload && typeof payload.detail === 'string'
            ? payload.detail
            : 'API Key 配置失败，请检查本机服务后重试'
        throw new Error(detail)
      }
      const result = parsePublicApiConfig(payload?.api_config)
      if (!result.ok) throw new Error(result.reason)

      this.apiConfig = result.config
      this.apiConfigStatus = 'ready'
      this.apiConfigError = null
      return isDashscopeRuntimeKeyReady(result.config)
    },
    resetChatRecords() {
      this.chatRecords = []
    },
  },
})
