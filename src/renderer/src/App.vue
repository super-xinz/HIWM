<script setup lang="ts">
import { ConfigProvider } from 'ant-design-vue'
import { storeToRefs } from 'pinia'

import ApiConfigPanel from '@/components/ApiConfigPanel.vue'
import WebcamPermission from '@/components/WebcamPermission.vue'
import { antdLocale, locale } from '@/langs'
import VideoChat from '@/views/VideoChat/index.vue'
import WSVideoChat from './views/WSVideoChat/index.vue'
import { useAppStore } from './store/app'
import { useMediaStore } from './store/media'
import isElectron from './utils/isElectron'

const appState = useAppStore()
const mediaState = useMediaStore()
const { chatMode } = storeToRefs(appState)
appState.init()
// import dayjs from 'dayjs';
// import 'dayjs/locale/zh-cn';
// dayjs.locale('zh-cn');
</script>
<template>
  <ConfigProvider :locale="antdLocale[locale]">
    <div
      v-if="isElectron"
      class="wrap"
      :style="{
        backgroundImage: 'none',
      }"
    >
      <WebcamPermission v-if="!mediaState.webcamAccessed">
        <ApiConfigPanel permission-mode />
      </WebcamPermission>
      <template v-if="chatMode === 'ws'">
        <WSVideoChat />
      </template>
      <template v-else>
        <VideoChat />
      </template>
    </div>
    <div v-else class="wrap">
      <WebcamPermission v-if="!mediaState.webcamAccessed">
        <ApiConfigPanel permission-mode />
      </WebcamPermission>
      <template v-if="chatMode === 'ws'">
        <WSVideoChat />
      </template>
      <template v-else>
        <VideoChat />
      </template>
    </div>
  </ConfigProvider>
</template>
<style lang="less" scoped>
.wrap {
  min-height: 100vh;
  background: #07100f;
  position: relative;
  *::-webkit-scrollbar {
    display: none;
  }
}
</style>
