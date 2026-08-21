<template>
  <div v-if="visible" class="access-gate">
    <section class="access-card" aria-labelledby="access-title">
      <span class="access-kicker">HIWM · PERSONALIZED COMPANION</span>
      <h1 id="access-title">持续理解，自然陪伴</h1>
      <p>系统根据授权信息与持续交流逐步适应你的沟通方式，请输入访问口令。</p>
      <form @submit.prevent="submit">
        <label for="demo-access-code">访问口令</label>
        <input
          id="demo-access-code"
          v-model="code"
          type="password"
          autocomplete="current-password"
          maxlength="256"
          :disabled="busy"
          placeholder="请输入口令"
        />
        <span v-if="error" class="access-error" role="alert">{{ error }}</span>
        <button type="submit" :disabled="busy || !code.trim()">
          {{ busy ? '正在验证…' : '进入系统' }}
        </button>
      </form>
      <small>页面只展示整合后的互动结论，不公开内部计算路径；相关结果不构成医学或心理诊断。</small>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

defineProps<{ visible: boolean; error?: string | null }>()
const emit = defineEmits<{ submit: [code: string] }>()
const code = ref('')
const busy = ref(false)

async function submit(): Promise<void> {
  if (!code.value.trim() || busy.value) return
  busy.value = true
  emit('submit', code.value)
  window.setTimeout(() => {
    busy.value = false
  }, 800)
}
</script>

<style scoped lang="less">
.access-gate {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: grid;
  place-items: center;
  padding: 24px;
  color: #17372f;
  background:
    radial-gradient(circle at 20% 20%, rgba(48, 151, 116, 0.2), transparent 32%),
    linear-gradient(145deg, #eef5f1, #dce9e3);
}
.access-card {
  width: min(460px, 100%);
  padding: 38px;
  border: 1px solid rgba(20, 130, 103, 0.24);
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 24px 80px rgba(24, 63, 52, 0.16);
}
.access-kicker {
  color: #148267;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.14em;
}
h1 {
  margin: 12px 0 8px;
  font-size: 30px;
}
p {
  margin: 0 0 26px;
  color: #557068;
  line-height: 1.7;
}
form {
  display: grid;
  gap: 10px;
}
label {
  font-size: 13px;
  font-weight: 700;
}
input {
  padding: 13px 15px;
  border: 1px solid #bdd0c9;
  border-radius: 12px;
  font-size: 16px;
  outline: none;
}
input:focus {
  border-color: #148267;
  box-shadow: 0 0 0 3px rgba(20, 130, 103, 0.12);
}
button {
  margin-top: 4px;
  padding: 13px;
  border: 0;
  border-radius: 12px;
  color: white;
  background: #148267;
  font-weight: 700;
  cursor: pointer;
}
button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.access-error {
  color: #b42318;
  font-size: 13px;
}
small {
  display: block;
  margin-top: 22px;
  color: #74877f;
  line-height: 1.6;
}
</style>
