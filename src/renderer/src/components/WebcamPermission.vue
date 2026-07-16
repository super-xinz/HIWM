<script setup lang="ts">
import { useMediaStore } from '@/store/media'
import { VideoCameraOutlined } from '@ant-design/icons-vue'

const mediaState = useMediaStore()
const accessClick = async (): Promise<void> => {
  await mediaState.accessDevice()
}

const text = '点击允许访问摄像头和麦克风'
</script>

<template>
  <div class="access-wrap">
    <div class="permission-config">
      <slot />
    </div>
    <button type="button" class="permission-action" @click="accessClick">
      <span class="icon-wrap">
        <VideoCameraOutlined />
      </span>
      <span>{{ text }}</span>
      <small>配置确认后，使用真实设备开始会话</small>
    </button>
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
  color: #dff7f0;
  background: radial-gradient(circle at 50% 8%, rgba(59, 141, 121, 0.18), transparent 38%), #07100f;
}

.permission-config {
  width: 100%;
  display: flex;
  justify-content: center;
}

.permission-action {
  min-width: min(420px, 100%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 22px 28px;
  color: #dff7f0;
  border: 1px solid rgba(112, 225, 193, 0.34);
  border-radius: 16px;
  background: rgba(20, 54, 47, 0.66);
  box-shadow: 0 18px 48px rgba(0, 0, 0, 0.24);
  cursor: pointer;

  &:hover,
  &:focus-visible {
    border-color: rgba(112, 225, 193, 0.72);
    background: rgba(29, 78, 66, 0.72);
    outline: none;
  }

  small {
    color: #8fa9a1;
    font-size: 11px;
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
}
</style>
