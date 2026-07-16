import { message } from 'ant-design-vue'
import { defineStore } from 'pinia'
import { getDevices, getStream, setAvailableDevices } from '@/utils/streamUtils'
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
    async accessDevice(): Promise<boolean> {
      try {
        this.micMuted = false
        this.cameraOff = false
        this.webcamAccessed = false
        if (!navigator.mediaDevices) {
          throw new Error('无法获取真实媒体设备，请使用 localhost 或 HTTPS 访问')
        }

        const permissionStream = await navigator.mediaDevices.getUserMedia({
          audio: true,
          video: true,
        })
        permissionStream.getTracks().forEach((track) => track.stop())
        this.hasMicPermission = true
        this.hasCameraPermission = true

        const devices = await getDevices()
        this.devices = devices
        const hasRealMic = devices.some(
          (device) => device.kind === 'audioinput' && Boolean(device.deviceId)
        )
        const hasRealCamera = devices.some(
          (device) => device.kind === 'videoinput' && Boolean(device.deviceId)
        )
        if (!hasRealMic || !hasRealCamera) {
          throw new Error(
            !hasRealMic && !hasRealCamera
              ? '未检测到真实摄像头和麦克风'
              : !hasRealMic
                ? '未检测到真实麦克风'
                : '未检测到真实摄像头'
          )
        }
        const videoDeviceId =
          this.selectedVideoDevice &&
          devices.some((device) => device.deviceId === this.selectedVideoDevice?.deviceId)
            ? this.selectedVideoDevice.deviceId
            : ''
        const audioDeviceId =
          this.selectedAudioDevice &&
          devices.some((device) => device.deviceId === this.selectedAudioDevice?.deviceId)
            ? this.selectedAudioDevice.deviceId
            : ''
        await this.fillStream(audioDeviceId, videoDeviceId)
        this.webcamAccessed = true
        return true
      } catch (err: unknown) {
        this.webcamAccessed = false
        this.hasCamera = false
        this.hasMic = false
        if (err instanceof DOMException && err.name === 'NotAllowedError') {
          this.hasCameraPermission = false
          this.hasMicPermission = false
        }
        const errorMessage = err instanceof Error ? err.message : String(err)
        message.error(`无法开始真实会话：${errorMessage}`)
        return false
      }
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
      this.availableVideoDevices = setAvailableDevices(devices, 'videoinput')
      this.availableAudioDevices = setAvailableDevices(devices, 'audioinput')
    },
    async fillStream(audioDeviceId: string, videoDeviceId: string) {
      const { devices } = this
      const visionState = useVisionStore()
      const node = visionState.localVideoRef
      this.hasMic =
        devices.some((device) => {
          return device.kind === 'audioinput' && device.deviceId
        }) && this.hasMicPermission
      this.hasCamera =
        devices.some((device) => device.kind === 'videoinput' && device.deviceId) &&
        this.hasCameraPermission
      if (!this.hasMic || !this.hasCamera) {
        throw new Error(!this.hasMic ? '未检测到真实麦克风' : '未检测到真实摄像头')
      }

      const localStream = await getStream(
        audioDeviceId && audioDeviceId !== 'default'
          ? { deviceId: { exact: audioDeviceId } }
          : this.hasMic,
        videoDeviceId && videoDeviceId !== 'default'
          ? { deviceId: { exact: videoDeviceId } }
          : this.hasCamera,
        this.trackConstraints
          ? {
              video:
                typeof this.trackConstraints.video === 'boolean' ? {} : this.trackConstraints.video,
              audio:
                typeof this.trackConstraints.audio === 'boolean' ? {} : this.trackConstraints.audio,
            }
          : undefined
      )

      const hasRealAudioTrack = localStream
        .getAudioTracks()
        .some((track) => track.readyState === 'live')
      const hasRealVideoTrack = localStream
        .getVideoTracks()
        .some((track) => track.readyState === 'live')
      if (!hasRealAudioTrack || !hasRealVideoTrack) {
        localStream.getTracks().forEach((track) => track.stop())
        throw new Error(!hasRealAudioTrack ? '真实麦克风轨道不可用' : '真实摄像头轨道不可用')
      }

      this.stream?.getTracks().forEach((track) => track.stop())
      this.stream = localStream
      this.localStream = localStream
      this.webcamAccessed = true
      await this.updateAvailableDevices()

      const usedDevices = localStream.getTracks().map((track) => track.getSettings()?.deviceId)
      usedDevices.forEach((deviceId) => {
        const usedDevice = devices.find((device) => device.deviceId === deviceId)
        if (usedDevice?.kind.includes('video')) {
          this.selectedVideoDevice = usedDevice
        } else if (usedDevice?.kind.includes('audio')) {
          this.selectedAudioDevice = usedDevice
        }
      })
      if (!this.selectedVideoDevice) {
        this.selectedVideoDevice = this.availableVideoDevices[0] || null
      }
      if (!this.selectedAudioDevice) {
        this.selectedAudioDevice = this.availableAudioDevices[0] || null
      }

      if (node) {
        node.srcObject = localStream
        node.muted = true
        await node.play()
      }
    },
  },
})
