import { message } from 'ant-design-vue'
import { defineStore } from 'pinia'
import {
  describeMediaAccessError,
  getDevices,
  getStream,
  setAvailableDevices,
} from '@/utils/streamUtils'
import { useVisionStore } from './vision'

const defaultTrackConstraints = {
  video: {
    width: 500,
    height: 500,
  },
  audio: {},
}

type TrackConstraints =
  | {
      video: MediaTrackConstraints | boolean
      audio: MediaTrackConstraints | boolean
    }
  | undefined

interface MediaState {
  devices: MediaDeviceInfo[]
  availableVideoDevices: MediaDeviceInfo[]
  availableAudioDevices: MediaDeviceInfo[]
  selectedVideoDevice: MediaDeviceInfo | null
  selectedAudioDevice: MediaDeviceInfo | null
  stream: MediaStream | null
  localStream: MediaStream | null
  webcamAccessed: boolean
  permissionPending: boolean
  permissionError: string | null
  videoRequired: boolean
  trackConstraints: TrackConstraints

  hasCamera: boolean
  hasCameraPermission: boolean
  hasMic: boolean
  hasMicPermission: boolean

  cameraOff: boolean
  micMuted: boolean
}

export const useMediaStore = defineStore('mediaStore', {
  state: (): MediaState => {
    return {
      devices: [],
      availableVideoDevices: [],
      availableAudioDevices: [],
      selectedVideoDevice: null,
      selectedAudioDevice: null,
      stream: null,
      localStream: null,
      webcamAccessed: false,
      permissionPending: false,
      permissionError: null,
      videoRequired: true,
      trackConstraints: defaultTrackConstraints,
      hasCamera: false,
      hasCameraPermission: true,
      hasMic: false,
      hasMicPermission: true,
      cameraOff: false,
      micMuted: false,
    }
  },
  actions: {
    setTrackConstraints(trackConstraints: TrackConstraints) {
      this.trackConstraints = trackConstraints || defaultTrackConstraints
    },
    async accessDevice(videoRequired?: boolean): Promise<boolean> {
      if (this.permissionPending) return false
      const requireVideo = videoRequired ?? this.videoRequired
      this.permissionPending = true
      this.permissionError = null
      let requestedStream: MediaStream | null = null
      try {
        this.micMuted = false
        this.cameraOff = false
        this.webcamAccessed = false
        this.videoRequired = requireVideo
        if (!navigator.mediaDevices) {
          throw new Error('无法获取真实媒体设备，请使用 localhost 或 HTTPS 访问')
        }

        // Keep getUserMedia in the original click call stack. Safari may require a
        // fresh user gesture after access was previously denied; awaiting device
        // enumeration here would consume that gesture before the permission request.
        const videoDeviceId = this.selectedVideoDevice?.deviceId || ''
        const audioDeviceId = this.selectedAudioDevice?.deviceId || ''

        requestedStream = await getStream(
          audioDeviceId && audioDeviceId !== 'default'
            ? { deviceId: { exact: audioDeviceId } }
            : true,
          requireVideo
            ? videoDeviceId && videoDeviceId !== 'default'
              ? { deviceId: { exact: videoDeviceId } }
              : true
            : false,
          this.normalizedTrackConstraints()
        )
        this.hasMicPermission = true
        if (requireVideo) this.hasCameraPermission = true
        await this.adoptLocalStream(requestedStream)
        requestedStream = null
        return true
      } catch (err: unknown) {
        requestedStream?.getTracks().forEach((track) => track.stop())
        this.webcamAccessed = false
        this.hasCamera = false
        this.hasMic = false
        if (err instanceof DOMException && err.name === 'NotAllowedError') {
          this.hasMicPermission = false
          if (requireVideo) this.hasCameraPermission = false
        }
        this.permissionError = describeMediaAccessError(err, requireVideo)
        message.error(`无法开始真实会话：${this.permissionError}`)
        return false
      } finally {
        this.permissionPending = false
      }
    },
    normalizedTrackConstraints() {
      return this.trackConstraints
        ? {
            video:
              typeof this.trackConstraints.video === 'boolean' ? {} : this.trackConstraints.video,
            audio:
              typeof this.trackConstraints.audio === 'boolean' ? {} : this.trackConstraints.audio,
          }
        : undefined
    },
    handleCameraOff() {
      this.cameraOff = !this.cameraOff
      this.stream?.getTracks().forEach((track) => {
        if (track.kind.includes('video')) track.enabled = !this.cameraOff
      })
    },
    handleMicMuted() {
      this.micMuted = !this.micMuted
      this.stream?.getTracks().forEach((track) => {
        if (track.kind.includes('audio')) track.enabled = !this.micMuted
      })
    },
    async handleDeviceChange(deviceId: string) {
      const device_id = deviceId
      const devices = await getDevices()
      this.devices = devices
      let videoDeviceId =
        this.selectedVideoDevice &&
        devices.some((device) => device.deviceId === this.selectedVideoDevice?.deviceId)
          ? this.selectedVideoDevice.deviceId
          : ''
      let audioDeviceId =
        this.selectedAudioDevice &&
        devices.some((device) => device.deviceId === this.selectedAudioDevice?.deviceId)
          ? this.selectedAudioDevice.deviceId
          : ''
      if (this.availableVideoDevices.find((video_device) => video_device.deviceId === device_id)) {
        videoDeviceId = device_id
        this.cameraOff = false
      } else if (
        this.availableAudioDevices.find((audio_device) => audio_device.deviceId === device_id)
      ) {
        audioDeviceId = device_id
        this.micMuted = false
      }
      try {
        await this.fillStream(audioDeviceId, videoDeviceId)
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error)
        message.error(`切换真实媒体设备失败：${errorMessage}`)
      }
    },
    async updateAvailableDevices() {
      const devices = await getDevices()
      this.devices = devices
      this.availableVideoDevices = setAvailableDevices(devices, 'videoinput')
      this.availableAudioDevices = setAvailableDevices(devices, 'audioinput')
    },
    async fillStream(audioDeviceId: string, videoDeviceId: string) {
      const { devices } = this
      this.hasMic =
        devices.some((device) => {
          return device.kind === 'audioinput'
        }) && this.hasMicPermission
      this.hasCamera =
        devices.some((device) => device.kind === 'videoinput') && this.hasCameraPermission
      if (!this.hasMic || (this.videoRequired && !this.hasCamera)) {
        throw new Error(
          !this.hasMic ? '未检测到真实麦克风' : '当前模型需要摄像头，但未检测到真实摄像头'
        )
      }

      const localStream = await getStream(
        audioDeviceId && audioDeviceId !== 'default'
          ? { deviceId: { exact: audioDeviceId } }
          : this.hasMic,
        this.videoRequired
          ? videoDeviceId && videoDeviceId !== 'default'
            ? { deviceId: { exact: videoDeviceId } }
            : this.hasCamera
          : false,
        this.normalizedTrackConstraints()
      )

      await this.adoptLocalStream(localStream)
    },
    async adoptLocalStream(localStream: MediaStream) {
      const visionState = useVisionStore()
      const node = visionState.localVideoRef

      const hasRealAudioTrack = localStream
        .getAudioTracks()
        .some((track) => track.readyState === 'live')
      const hasRealVideoTrack = localStream
        .getVideoTracks()
        .some((track) => track.readyState === 'live')
      if (!hasRealAudioTrack || (this.videoRequired && !hasRealVideoTrack)) {
        localStream.getTracks().forEach((track) => track.stop())
        throw new Error(
          !hasRealAudioTrack ? '真实麦克风轨道不可用' : '当前模型需要摄像头，但真实摄像头轨道不可用'
        )
      }

      this.stream?.getTracks().forEach((track) => track.stop())
      this.stream = localStream
      this.localStream = localStream
      this.hasMic = hasRealAudioTrack
      this.hasCamera = hasRealVideoTrack
      this.webcamAccessed = true
      await this.updateAvailableDevices()

      const usedDevices = localStream.getTracks().map((track) => track.getSettings()?.deviceId)
      usedDevices.forEach((deviceId) => {
        const usedDevice = this.devices.find((device) => device.deviceId === deviceId)
        if (usedDevice?.kind.includes('video')) {
          this.selectedVideoDevice = usedDevice
        } else if (usedDevice?.kind.includes('audio')) {
          this.selectedAudioDevice = usedDevice
        }
      })
      if (hasRealVideoTrack && !this.selectedVideoDevice) {
        this.selectedVideoDevice = this.availableVideoDevices[0] || null
      } else if (!hasRealVideoTrack) {
        this.selectedVideoDevice = null
      }
      if (!this.selectedAudioDevice) {
        this.selectedAudioDevice = this.availableAudioDevices[0] || null
      }

      if (node && hasRealVideoTrack) {
        node.srcObject = localStream
        node.muted = true
        await node.play()
      } else if (node) {
        node.srcObject = null
      }
    },
    releaseDevices() {
      const streams = new Set([this.stream, this.localStream].filter(Boolean) as MediaStream[])
      streams.forEach((stream) => stream.getTracks().forEach((track) => track.stop()))
      this.stream = null
      this.localStream = null
      this.webcamAccessed = false
      this.hasCamera = false
      this.hasMic = false
      this.cameraOff = true
      this.micMuted = true
      const node = useVisionStore().localVideoRef
      if (node) node.srcObject = null
    },
  },
})
