<template>
  <div class="action-group">
    <div v-if="hasCamera">
      <div
        v-click-outside="() => (cameraListShow = false)"
        class="action"
        role="button"
        tabindex="0"
        :aria-label="cameraOff ? '开启摄像头' : '关闭摄像头'"
        :aria-pressed="!cameraOff"
        @click="handleCameraOff"
        @keydown.enter.prevent="handleCameraOff"
        @keydown.space.prevent="handleCameraOff"
      >
        <Iconfont :icon="cameraOff ? CameraOff : CameraOn" />
        <div
          v-if="streamState === 'closed'"
          class="corner"
          role="button"
          tabindex="0"
          aria-label="选择摄像头"
          @click.stop.prevent="() => (cameraListShow = !cameraListShow)"
          @keydown.enter.stop.prevent="() => (cameraListShow = !cameraListShow)"
          @keydown.space.stop.prevent="() => (cameraListShow = !cameraListShow)"
        >
          <div class="corner-inner" />
        </div>
        <div
          v-show="cameraListShow && streamState === 'closed'"
          class="selectors"
          :class="{ left: isLandscape }"
        >
          <div
            v-for="device in availableVideoDevices"
            :key="device.deviceId"
            class="selector"
            role="button"
            tabindex="0"
            @click.stop="
              () => {
                handleDeviceChange(device.deviceId)
                cameraListShow = false
              }
            "
            @keydown.enter.stop.prevent="
              () => {
                handleDeviceChange(device.deviceId)
                cameraListShow = false
              }
            "
            @keydown.space.stop.prevent="
              () => {
                handleDeviceChange(device.deviceId)
                cameraListShow = false
              }
            "
          >
            {{ device.label }}
            <div
              v-if="selectedVideoDevice && device.deviceId === selectedVideoDevice.deviceId"
              class="active-icon"
            >
              <CheckIcon />
            </div>
          </div>
        </div>
      </div>
    </div>
    <div v-if="hasMic">
      <div
        v-click-outside="() => (micListShow = false)"
        class="action"
        role="button"
        tabindex="0"
        :aria-label="micMuted ? '开启麦克风' : '关闭麦克风'"
        :aria-pressed="!micMuted"
        @click="handleMicMuted"
        @keydown.enter.prevent="handleMicMuted"
        @keydown.space.prevent="handleMicMuted"
      >
        <Iconfont :icon="micMuted ? MicOff : MicOn" />
        <div
          v-if="streamState === 'closed'"
          class="corner"
          role="button"
          tabindex="0"
          aria-label="选择麦克风"
          @click.stop.prevent="() => (micListShow = !micListShow)"
          @keydown.enter.stop.prevent="() => (micListShow = !micListShow)"
          @keydown.space.stop.prevent="() => (micListShow = !micListShow)"
        >
          <div class="corner-inner" />
        </div>
        <div
          v-show="micListShow && streamState === 'closed'"
          class="selectors"
          :class="{ left: isLandscape }"
        >
          <div
            v-for="device in availableAudioDevices"
            :key="device.deviceId"
            class="selector"
            role="button"
            tabindex="0"
            @click.stop="
              () => {
                handleDeviceChange(device.deviceId)
                micListShow = false
              }
            "
            @keydown.enter.stop.prevent="
              () => {
                handleDeviceChange(device.deviceId)
                micListShow = false
              }
            "
            @keydown.space.stop.prevent="
              () => {
                handleDeviceChange(device.deviceId)
                micListShow = false
              }
            "
          >
            {{ device.label }}
            <div
              v-if="selectedAudioDevice && device.deviceId === selectedAudioDevice.deviceId"
              class="active-icon"
            >
              <CheckIcon />
            </div>
          </div>
        </div>
      </div>
    </div>

    <div
      class="action"
      role="button"
      tabindex="0"
      :aria-label="volumeMuted ? '开启声音' : '关闭声音'"
      :aria-pressed="!volumeMuted"
      @click="handleVolumeMute"
      @keydown.enter.prevent="handleVolumeMute"
      @keydown.space.prevent="handleVolumeMute"
    >
      <Iconfont :icon="volumeMuted ? VolumeOff : VolumeOn" />
    </div>
    <div v-if="wrapperRect.width > 300">
      <div
        class="action"
        role="button"
        tabindex="0"
        :aria-label="showChatRecords ? '隐藏字幕' : '显示字幕'"
        :aria-pressed="showChatRecords"
        @click="handleSubtitleToggle"
        @keydown.enter.prevent="handleSubtitleToggle"
        @keydown.space.prevent="handleSubtitleToggle"
      >
        <Iconfont :icon="showChatRecords ? SubtitleOn : SubtitleOff" />
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
import { computed, ref } from 'vue'
import { storeToRefs } from 'pinia'

import { useMediaStore } from '@/store/media'
import { useChatStore } from '@/store/chat'
import { useVideoChatStore } from '@/store/webrtc'
import { useWSVideoChatStore } from '@/store/ws'
import { useAppStore } from '@/store/app'
import { useVisionStore } from '@/store/vision'
import Iconfont, {
  CameraOff,
  CameraOn,
  CheckIcon,
  MicOff,
  MicOn,
  SubtitleOff,
  SubtitleOn,
  VolumeOff,
  VolumeOn,
} from './Iconfont'

const chatStore = useChatStore()
const mediaStore = useMediaStore()
const visionStore = useVisionStore()
const appStore = useAppStore()
const videoChatStore = useVideoChatStore()
const wsChatStore = useWSVideoChatStore()

const {
  hasCamera,
  hasMic,
  cameraOff,
  micMuted,
  selectedAudioDevice,
  selectedVideoDevice,
  availableAudioDevices,
  availableVideoDevices,
} = storeToRefs(mediaStore)

const { volumeMuted, showChatRecords } = storeToRefs(chatStore)
const streamState = computed(() =>
  appStore.chatMode === 'ws' ? wsChatStore.streamState : videoChatStore.streamState
)

const { handleVolumeMute, handleSubtitleToggle } = chatStore
const { handleCameraOff, handleMicMuted, handleDeviceChange } = mediaStore

const { wrapperRect, isLandscape } = storeToRefs(visionStore)
const micListShow = ref(false)
const cameraListShow = ref(false)
</script>

<style lang="less" scoped>
.action-group {
  border-radius: 12px;
  border: 1px solid #dfe7e3;
  background: rgba(255, 255, 255, 0.92);
  box-shadow: 0 8px 24px rgba(32, 58, 49, 0.1);
  padding: 2px;
  backdrop-filter: blur(8px);

  .action {
    cursor: pointer;
    width: 42px;
    height: 42px;
    border-radius: 8px;
    font-size: 20px;
    display: flex;
    align-items: center;
    justify-content: center;
    position: relative;
    color: #33443e;

    :deep(svg path) {
      fill: currentColor;
    }

    .corner {
      position: absolute;
      right: 0px;
      bottom: 0px;
      padding: 3px;

      &:focus-visible {
        outline: 2px solid rgba(20, 130, 103, 0.48);
        outline-offset: 1px;
      }

      .corner-inner {
        width: 6px;
        height: 6px;
        border-top: 3px transparent solid;
        border-left: 3px transparent solid;
        border-bottom: 3px #66756f solid;
        border-right: 3px #66756f solid;
      }
    }

    // &:hover {
    // 	.selectors {
    // 		display: block !important;
    // 	}
    // }
    .selectors {
      position: absolute;
      top: 0;
      left: calc(100%);
      margin-left: 3px;
      max-height: 150px;

      &.left {
        left: 0;
        margin-left: -3px;
        transform: translateX(-100%);
      }

      border-radius: 12px;
      width: max-content;
      overflow: hidden;
      overflow: auto;

      border: 1px solid #dfe7e3;
      background: rgba(255, 255, 255, 0.98);
      box-shadow: 0 12px 30px rgba(32, 58, 49, 0.14);
      backdrop-filter: blur(8px);

      .selector {
        max-width: 250px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        position: relative;
        cursor: pointer;
        height: 42px;
        line-height: 42px;
        color: #33443e;
        font-size: 14px;

        &:focus-visible {
          outline: 2px solid rgba(20, 130, 103, 0.48);
          outline-offset: -3px;
          background: #eef7f4;
        }

        &:hover {
          background: #eef7f4;
        }

        padding-left: 15px;
        padding-right: 50px;

        .active-icon {
          position: absolute;
          right: 10px;
          width: 40px;
          height: 40px;
          display: flex;
          align-items: center;
          justify-content: center;
          top: 0;
        }
      }
    }
  }

  .action:hover {
    color: #148267;
    background: #eef7f4;
  }

  .action:focus-visible {
    color: #148267;
    background: #eef7f4;
    outline: 3px solid rgba(20, 130, 103, 0.24);
    outline-offset: 2px;
  }
}

.action-group + .action-group {
  margin-top: 10px;
}
</style>
