<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ConfigProvider } from 'ant-design-vue'
import { storeToRefs } from 'pinia'

import SessionSetupGate from '@/components/SessionSetupGate.vue'
import AccessGate from '@/components/AccessGate.vue'
import CompanionDashboard from '@/components/CompanionDashboard.vue'
import { antdLocale, locale } from '@/langs'
import VideoChat from '@/views/VideoChat/index.vue'
import WSVideoChat from './views/WSVideoChat/index.vue'
import { useAppStore } from './store/app'
import { useMediaStore } from './store/media'
import { useCompanionStore } from './store/companion'
import { type AnalysisConsentRecord, usePerceptionStore } from './store/perception'
import { isDashscopeRuntimeKeyReady } from './interface/apiConfig'

const appState = useAppStore()
const mediaState = useMediaStore()
const perceptionState = usePerceptionStore()
const companionState = useCompanionStore()
const { chatMode } = storeToRefs(appState)
const experienceMode = ref<'companion' | 'live'>('companion')
const runtimeInitialized = ref(false)
const liveAvailable = computed(() => Boolean(appState.apiConfig?.hiwm))

const setupBusy = ref(false)
const setupError = ref<string | null>(null)
const setupVisible = computed(
  () =>
    experienceMode.value === 'live' &&
    (!perceptionState.analysisAuthorized || !mediaState.webcamAccessed)
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

async function initializeRuntime(): Promise<void> {
  if (runtimeInitialized.value) return
  runtimeInitialized.value = true
  await appState.init()
}

async function login(code: string): Promise<void> {
  if (await companionState.login(code)) await initializeRuntime()
}

onMounted(async () => {
  await companionState.initialize()
  if (companionState.authorized) await initializeRuntime()
})

watch(
  () => companionState.authorized,
  (authorized) => {
    if (authorized) void initializeRuntime()
  }
)
// import dayjs from 'dayjs';
// import 'dayjs/locale/zh-cn';
// dayjs.locale('zh-cn');
</script>
<template>
  <ConfigProvider :locale="antdLocale[locale]">
    <div class="wrap">
      <AccessGate
        :visible="companionState.accessReady && !companionState.authorized"
        :error="companionState.error"
        @submit="login"
      />
      <div v-if="!companionState.accessReady" class="boot-screen">正在连接 HIWM 服务…</div>
      <header v-if="companionState.authorized" class="product-header">
        <div class="product-brand">
          <i />
          <div>
            <strong>HIWM</strong>
            <small>Human Interaction World Model</small>
          </div>
        </div>
        <nav aria-label="体验模式">
          <button
            :class="{ active: experienceMode === 'companion' }"
            @click="experienceMode = 'companion'"
          >
            画像聊天
          </button>
          <button
            v-if="liveAvailable"
            :class="{ active: experienceMode === 'live' }"
            @click="experienceMode = 'live'"
          >
            实时互动
          </button>
        </nav>
        <button class="logout" @click="companionState.logout">退出</button>
      </header>
      <SessionSetupGate
        :visible="companionState.authorized && setupVisible"
        :busy="setupBusy"
        :error="setupError"
        consent-version="hiwm-demo-1.0"
        @start="completeSetup"
      />
      <template v-if="companionState.authorized">
        <CompanionDashboard v-if="experienceMode === 'companion'" />
        <template v-else-if="chatMode === 'ws'"><WSVideoChat /></template>
        <template v-else><VideoChat /></template>
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
.boot-screen {
  min-height: 100vh;
  display: grid;
  place-items: center;
  color: #5e756d;
}
.product-header {
  height: 64px;
  box-sizing: border-box;
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  padding: 0 20px;
  border-bottom: 1px solid #d5e1dc;
  background: rgba(255, 255, 255, 0.96);
}
.product-brand {
  display: flex;
  align-items: center;
  gap: 10px;
}
.product-brand > i {
  width: 11px;
  height: 11px;
  border-radius: 50%;
  background: #148267;
  box-shadow: 0 0 0 5px rgba(20, 130, 103, 0.12);
}
.product-brand div {
  display: grid;
}
.product-brand strong {
  color: #174b3d;
  letter-spacing: 0.12em;
}
.product-brand small {
  color: #82938d;
  font-size: 9px;
}
nav {
  display: flex;
  gap: 4px;
  padding: 4px;
  border-radius: 10px;
  background: #edf3f0;
}
nav button {
  padding: 7px 14px;
  border: 0;
  border-radius: 7px;
  color: #657a73;
  background: transparent;
  cursor: pointer;
}
nav button.active {
  color: #145c49;
  background: white;
  box-shadow: 0 2px 8px rgba(42, 74, 64, 0.1);
  font-weight: 700;
}
.logout {
  justify-self: end;
  border: 0;
  color: #73857f;
  background: transparent;
  cursor: pointer;
}
@media (max-width: 640px) {
  .product-header {
    grid-template-columns: auto 1fr;
    padding: 0 10px;
  }
  .product-brand small,
  .logout {
    display: none;
  }
  nav {
    justify-self: end;
  }
}
</style>
