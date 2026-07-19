<template>
  <div class="player-controls">
    <button
      type="button"
      :class="[
        'chat-btn',
        streamState === StreamState.closed && 'start-chat',
        streamState === StreamState.open && 'stop-chat',
      ]"
      :aria-label="
        streamState === StreamState.closed
          ? '开始对话'
          : streamState === StreamState.waiting
            ? '正在等待连接'
            : '停止对话'
      "
      @click="onStartChat"
    >
      <template v-if="streamState === StreamState.closed">
        <span>点击开始对话</span>
      </template>
      <template v-else-if="streamState === StreamState.waiting">
        <span class="waiting-icon-text">
          <span class="icon" title="spinner">
            <Spin wrapper-class-name="spin-icon" />
          </span>
          <span>等待中</span>
        </span>
      </template>
      <template v-else>
        <span class="stop-chat-inner" />
      </template>
    </button>
    <template v-if="streamState === StreamState.open">
      <div class="input-audio-wave">
        <AudioWave
          :audio-source-callback="audioSourceCallback"
          :stream-state="streamState"
          :wave-color="waveColor"
        />
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { Spin } from 'ant-design-vue'
import { StreamState } from '@/interface/voiceChat'
import AudioWave from '@/components/AudioWave.vue'

withDefaults(
  defineProps<{
    streamState: StreamState
    onStartChat: any
    audioSourceCallback: () => MediaStream | null
    waveColor: string
  }>(),
  {
    streamState: StreamState.closed,
  }
)

const emit = defineEmits([])
</script>

<style scoped lang="less"></style>

<style scoped lang="less">
.player-controls {
  height: 15%;
  position: relative;
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 84px;

  .chat-btn {
    height: 64px;
    width: 296px;
    display: flex;
    justify-content: center;
    align-items: center;
    border-radius: 999px;
    opacity: 1;
    background: linear-gradient(180deg, #1b9475 0%, #126d57 100%);
    box-shadow: 0 10px 24px rgba(20, 130, 103, 0.18);
    transition: all 0.3s;
    z-index: 2;
    cursor: pointer;
    border: 0;
    font: inherit;

    &:focus-visible {
      outline: 3px solid rgba(20, 130, 103, 0.28);
      outline-offset: 3px;
    }

    &:hover {
      box-shadow: 0 12px 28px rgba(20, 130, 103, 0.26);
      transform: translateY(-1px);
    }
  }

  .start-chat {
    font-size: 16px;
    font-weight: 500;
    text-align: center;
    color: #ffffff;
  }

  .waiting-icon-text {
    width: 80px;
    align-items: center;
    font-size: 16px;
    font-weight: 500;
    color: #ffffff;
    margin: 0 var(--spacing-sm, 8px);
    display: flex;
    justify-content: space-evenly;
    gap: var(--size-1, 4px);

    .icon {
      width: 25px;
      height: 25px;
      fill: #ffffff;
      stroke: #ffffff;
      color: #ffffff;
    }
    .spin-icon {
      color: #fff;
    }
    :global(.ant-spin-dot-item) {
      background-color: #fff !important;
    }
  }

  .stop-chat {
    width: 64px;

    .stop-chat-inner {
      width: 25px;
      height: 25px;
      border-radius: 6.25px;
      background: #fafafa;
    }
  }

  .input-audio-wave {
    position: absolute;
  }
}
</style>
