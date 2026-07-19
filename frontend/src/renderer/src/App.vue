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
import { writeRuntimeControlToken } from './utils/projectStorage'

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

const completeSetup = async (
  decision: AnalysisConsentRecord,
  apiKey: string,
  accessToken: string
): Promise<void> => {
  if (setupBusy.value) return
  setupBusy.value = true
  setupError.value = null

  if (appState.runtimeControlAuthRequired) {
    writeRuntimeControlToken(accessToken)
  }

  // Start getUserMedia synchronously from the original button gesture. Key
  // configuration runs in parallel so the app still needs only one click.
  const mediaPromise = mediaState.webcamAccessed
    ? Promise.resolve(true)
    : mediaState.accessDevice(videoRequired.value)
  const keyPromise = apiKey
    ? appState.configureRuntimeApiKey(apiKey)
    : Promise.resolve(isDashscopeRuntimeKeyReady(appState.apiConfig))

  const [mediaResult, keyResult] = await Promise.allSettled([mediaPromise, keyPromise])
  const mediaReady = mediaResult.status === 'fulfilled' && mediaResult.value
  const keyReady = keyResult.status === 'fulfilled' && keyResult.value

  if (!keyReady) {
    setupError.value =
      keyResult.status === 'rejected'
        ? keyResult.reason instanceof Error
          ? keyResult.reason.message
          : String(keyResult.reason)
        : '请先输入有效的 DashScope API Key'
  } else if (!mediaReady) {
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
        :access-control-required="appState.runtimeControlAuthRequired"
        consent-version="hiwm-demo-1.0"
        derived-retention-label="派生事件最多保留 200 条；服务端预测锁可由你主动删除"
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
