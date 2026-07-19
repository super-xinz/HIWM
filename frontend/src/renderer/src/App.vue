<script setup lang="ts">
import { computed, ref } from 'vue'
import { ConfigProvider } from 'ant-design-vue'
import { storeToRefs } from 'pinia'

import SessionSetupGate from '@/components/SessionSetupGate.vue'
import { antdLocale, locale } from '@/langs'
import VideoChat from '@/views/VideoChat/index.vue'
import WSVideoChat from './views/WSVideoChat/index.vue'
import { useAppStore } from './store/app'
import { useMediaStore } from './store/media'
import { type AnalysisConsentRecord, usePerceptionStore } from './store/perception'
import { isDashscopeRuntimeKeyReady } from './interface/apiConfig'

const appState = useAppStore()
const mediaState = useMediaStore()
const perceptionState = usePerceptionStore()
const { chatMode } = storeToRefs(appState)
appState.init()

const setupBusy = ref(false)
const setupError = ref<string | null>(null)
const setupVisible = computed(
  () => !perceptionState.analysisAuthorized || !mediaState.webcamAccessed
)
const videoRequired = computed(() => {
  const modalities = appState.apiConfig?.hiwm?.input_modalities
  return modalities ? modalities.includes('image') : true
})

const completeSetup = async (decision: AnalysisConsentRecord): Promise<void> => {
  if (setupBusy.value) return
  setupBusy.value = true
  setupError.value = null

  if (!isDashscopeRuntimeKeyReady(appState.apiConfig)) {
    setupError.value = 'AI 服务正在准备，请稍后重试'
    setupBusy.value = false
    return
  }

  const mediaReady = mediaState.webcamAccessed
    ? true
    : await mediaState.accessDevice(videoRequired.value)

  if (!mediaReady) {
    setupError.value = mediaState.permissionError || '设备权限尚未开启，请检查后重试'
  } else {
    perceptionState.setAnalysisAuthorized(true, decision)
  }
  setupBusy.value = false
}
// import dayjs from 'dayjs';
// import 'dayjs/locale/zh-cn';
// dayjs.locale('zh-cn');
</script>
<template>
  <ConfigProvider :locale="antdLocale[locale]">
    <div class="wrap">
      <SessionSetupGate
        :visible="setupVisible"
        :busy="setupBusy"
        :error="setupError"
        consent-version="hiwm-demo-1.0"
        @start="completeSetup"
      />
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
  background: #f5f7f6;
  position: relative;

  *::-webkit-scrollbar {
    width: 8px;
    height: 8px;
  }

  *::-webkit-scrollbar-track {
    background: transparent;
  }

  *::-webkit-scrollbar-thumb {
    border: 2px solid transparent;
    border-radius: 999px;
    background: #b9c7c1;
    background-clip: padding-box;
  }

  *::-webkit-scrollbar-thumb:hover {
    background: #8fa39b;
    background-clip: padding-box;
  }
}
</style>
