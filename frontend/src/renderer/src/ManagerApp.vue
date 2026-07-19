<script setup lang="ts">
import { ConfigProvider } from 'ant-design-vue'

import { antdLocale, locale } from '@/langs'
import ManagerView from './views/Manager/index.vue'
</script>

<template>
  <ConfigProvider :locale="antdLocale[locale]">
    <ManagerView />
  </ConfigProvider>
</template>
