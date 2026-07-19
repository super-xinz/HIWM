<script setup lang="ts">
import { computed } from 'vue'
import { storeToRefs } from 'pinia'

import { AudioOutlined, VideoCameraOutlined } from '@ant-design/icons-vue'
import { useAppStore } from '@/store/app'
import { useMediaStore } from '@/store/media'

const appState = useAppStore()
const mediaState = useMediaStore()
const { apiConfig, apiConfigStatus } = storeToRefs(appState)
const { permissionError, permissionPending } = storeToRefs(mediaState)

const videoRequired = computed(() => {
  const modalities = apiConfig.value?.hiwm?.input_modalities
  return modalities ? modalities.includes('image') : true
})

const accessClick = async (): Promise<void> => {
  if (permissionPending.value || apiConfigStatus.value === 'loading') return
  await mediaState.accessDevice(videoRequired.value)
}

const text = computed(() =>
  videoRequired.value ? '点击允许访问摄像头和麦克风' : '点击允许访问麦克风'
)
const description = computed(() =>
  videoRequired.value
    ? '当前模型需要真实摄像头与麦克风'
    : '当前 HIWM 为纯文本模型，不申请摄像头权限'
)
</script>

<template>
  <div class="access-wrap">
    <div class="permission-config">
      <slot />
    </div>
    <button
      type="button"
      class="permission-action"
      :disabled="permissionPending || apiConfigStatus === 'loading'"
      @click="accessClick"
    >
      <span class="icon-wrap">
        <VideoCameraOutlined v-if="videoRequired" />
        <AudioOutlined v-else />
      </span>
      <span>{{ text }}</span>
      <small>{{ permissionPending ? '正在请求设备权限…' : description }}</small>
    </button>
    <div v-if="permissionError" class="permission-error" role="alert">
      <strong>设备权限尚未开启</strong>
      <span>{{ permissionError }}</span>
    </div>
  </div>
</template>
<style lang="less" scoped>
.access-wrap {
  position: fixed;
  z-index: 1000;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 28px;
  padding: 28px;
  overflow: auto;
  box-sizing: border-box;
  color: #17231f;
  background: #f5f7f6;
}

.permission-config {
  width: 100%;
  display: flex;
  justify-content: center;
}

.permission-action {
  min-width: min(420px, 100%);
  max-width: 560px;
  min-height: 132px;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 22px 28px;
  color: #17231f;
  border: 1px solid #dfe7e3;
  border-radius: 16px;
  background: #ffffff;
  box-shadow: 0 18px 48px rgba(32, 58, 49, 0.1);
  cursor: pointer;

  > span:nth-child(2) {
    font-size: 15px;
    font-weight: 650;
    line-height: 1.45;
    text-align: center;
  }

  &:disabled {
    cursor: wait;
    opacity: 0.62;
  }

  &:hover,
  &:focus-visible {
    border-color: rgba(20, 130, 103, 0.5);
    background: #f4faf8;
    outline: none;
  }

  &:focus-visible {
    box-shadow:
      0 18px 48px rgba(32, 58, 49, 0.1),
      0 0 0 3px rgba(20, 130, 103, 0.2);
  }

  small {
    color: #596a64;
    font-size: 12px;
    line-height: 1.5;
    text-align: center;
  }
}

.permission-error {
  width: min(620px, 100%);
  display: grid;
  gap: 6px;
  padding: 13px 16px;
  color: #842b26;
  border: 1px solid #edc9c6;
  border-radius: 12px;
  background: #fff1ef;
  line-height: 1.55;

  strong {
    font-size: 13px;
  }

  span {
    color: #91443e;
    font-size: 12px;
    overflow-wrap: anywhere;
  }
}

.icon-wrap {
  line-height: 1;
  font-size: 40px;
}

@media (max-width: 760px) {
  .access-wrap {
    gap: 18px;
    padding: 12px;
  }

  .permission-action {
    min-height: 120px;
    padding: 18px 16px;
  }

  .permission-error {
    padding: 12px 14px;
  }
}
</style>
