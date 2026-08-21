<template>
  <main class="companion-dashboard">
    <aside class="dashboard-panel profile-panel">
      <header class="panel-heading">
        <div>
          <span>PERSONALIZED CONTEXT</span>
          <h2>人物画像</h2>
        </div>
        <button class="icon-button" title="刷新画像" @click="store.refreshProfile">↻</button>
      </header>
      <label class="user-field">
        <span>当前测试用户</span>
        <input v-model="store.userId" maxlength="256" @change="store.refreshProfile" />
      </label>
      <template v-if="profile">
        <div class="profile-version">
          <strong>v{{ profile.profile_version || '—' }}</strong>
          <span title="表示当前有效信息的覆盖与稳定程度，不代表对人的准确率">
            画像成熟度 {{ formatPercent(profile.overall_confidence) }}
          </span>
        </div>
        <section v-if="profile.portrait?.essence" class="profile-card emphasis">
          <span>稳定画像摘要</span>
          <p>{{ profile.portrait.essence }}</p>
        </section>
        <section class="profile-card">
          <span>沟通偏好</span>
          <div class="tag-list">
            <i v-for="(value, key) in profile.interaction_preferences" :key="key">
              {{ key }} · {{ value }}
            </i>
            <em v-if="!Object.keys(profile.interaction_preferences || {}).length">暂无明确偏好</em>
          </div>
        </section>
        <section class="profile-card">
          <span>主要互动特征</span>
          <div
            v-for="trait in profile.top_traits || []"
            :key="`${trait.group}.${trait.name}`"
            class="trait-row"
          >
            <small>{{ trait.name }}</small>
            <b>{{ formatPercent(trait.value) }}</b>
          </div>
        </section>
        <section class="profile-card">
          <span>当前状态</span>
          <pre>{{ prettyState }}</pre>
        </section>
        <small class="updated-at">最近更新：{{ formatDate(profile.updated_at) }}</small>
      </template>
      <div v-else class="empty-state">等待画像引擎返回数据</div>
    </aside>

    <section class="dashboard-panel chat-panel">
      <header class="panel-heading chat-heading">
        <div>
          <span>PROFILE-AWARE CHAT</span>
          <h2>陪伴对话</h2>
        </div>
        <div class="chat-actions">
          <button @click="store.newSession(false)">新建会话</button>
          <button @click="clearConversation">清空当前</button>
        </div>
      </header>
      <div class="demo-notice">
        系统会在回复前读取画像，并在本轮结束后更新画像。人物画像只用于改善表达与连续性。
      </div>
      <div ref="messageList" class="message-list">
        <article
          v-for="item in store.messages"
          :key="`${item.turn_id}-${item.role}`"
          :class="['message', item.role]"
        >
          <span>{{ item.role === 'user' ? '我' : 'HIWM' }}</span>
          <p>{{ item.content || (item.pending ? '正在生成…' : '未生成内容') }}</p>
          <small v-if="item.failed">生成已中断，可重新发送</small>
        </article>
        <div v-if="!store.messages.length" class="chat-empty">
          <b>从一段真实对话开始</b>
          <span>例如：“最近做决定时我总是想太久。”</span>
        </div>
      </div>
      <form class="composer" @submit.prevent="send">
        <textarea
          v-model="draft"
          rows="3"
          maxlength="4000"
          placeholder="输入你想聊的内容…"
          @keydown.enter.exact.prevent="send"
        />
        <div>
          <small>{{ draft.length }} / 4000</small>
          <button v-if="store.sending" type="button" class="stop" @click="store.stop">
            停止生成
          </button>
          <button v-else type="submit" :disabled="!draft.trim()">发送</button>
        </div>
      </form>
    </section>

    <aside class="dashboard-panel status-panel">
      <header class="panel-heading">
        <div>
          <span>ADAPTIVE CONTEXT</span>
          <h2>个性化状态</h2>
        </div>
        <button class="icon-button" title="刷新状态" @click="store.refreshHealth">↻</button>
      </header>
      <section class="status-card">
        <div v-for="(value, key) in health?.services || {}" :key="key" class="service-row">
          <span>
            <i :class="statusClass(value)" />
            {{ serviceLabel(key) }}
          </span>
          <b>{{ statusLabel(value) }}</b>
        </div>
      </section>
      <label class="profile-toggle">
        <span>
          <b>画像增强</b>
          <small>读取并更新人物画像</small>
        </span>
        <input v-model="store.profileEnabled" type="checkbox" />
      </label>
      <section class="status-card update-card">
        <span>本轮画像更新</span>
        <template v-if="store.lastProfileUpdate">
          <strong :class="`is-${store.lastProfileUpdate.status}`">{{ updateLabel }}</strong>
          <ul v-if="store.lastProfileUpdate.summary?.length">
            <li v-for="item in store.lastProfileUpdate.summary" :key="item">{{ item }}</li>
          </ul>
          <p v-if="store.lastProfileUpdate.error">{{ store.lastProfileUpdate.error }}</p>
          <button v-if="store.lastProfileUpdate.retryable" @click="retryUpdate">
            重试画像更新
          </button>
        </template>
        <em v-else>完成一轮对话后显示结构化更新结果</em>
      </section>
      <section class="status-card latency-card">
        <span>最近调用耗时</span>
        <dl>
          <div v-for="(value, key) in store.lastLatency || {}" :key="key">
            <dt>{{ key }}</dt>
            <dd>{{ value }} ms</dd>
          </div>
        </dl>
      </section>
      <p v-if="store.error" class="system-error" role="alert">{{ store.error }}</p>
      <button class="danger-button" @click="resetProfile">重置当前用户画像</button>
    </aside>
  </main>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { message } from 'ant-design-vue'

import { useCompanionStore } from '@/store/companion'

const store = useCompanionStore()
const { profile, health } = storeToRefs(store)
const draft = ref('')
const messageList = ref<HTMLElement>()

const prettyState = computed(() => {
  const state = profile.value?.current_state || {}
  return Object.keys(state).length ? JSON.stringify(state, null, 2) : '暂无短期状态'
})
const updateLabel = computed(
  () =>
    ({
      updated: '画像已更新',
      unchanged: '画像无变化',
      failed: '画像更新暂时失败',
      skipped: '本轮未启用画像',
    })[store.lastProfileUpdate?.status || 'skipped']
)

watch(
  () => store.messages.map((item) => item.content).join('|'),
  async () => {
    await nextTick()
    if (messageList.value) messageList.value.scrollTop = messageList.value.scrollHeight
  }
)

function formatPercent(value?: number): string {
  return typeof value === 'number' ? `${Math.round(value * 100)}%` : '—'
}
function formatDate(value?: string): string {
  return value ? new Date(value).toLocaleString('zh-CN') : '暂无记录'
}
function statusClass(value: string): string {
  return ['ok', 'configured'].includes(value) ? 'ok' : 'warn'
}
function serviceLabel(key: string): string {
  return (
    (
      {
        application: 'Chat API',
        profile_engine: '画像能力服务',
        llm: '原模型 API',
        database: '会话数据库',
      } as Record<string, string>
    )[key] || key
  )
}
function statusLabel(value: string): string {
  return (
    (
      {
        ok: '正常',
        configured: '已配置',
        unavailable: '不可用',
        not_configured: '未配置',
      } as Record<string, string>
    )[value] || value
  )
}
async function send(): Promise<void> {
  const content = draft.value.trim()
  if (!content) return
  draft.value = ''
  await store.send(content)
}
async function clearConversation(): Promise<void> {
  if (!window.confirm('确认清空当前会话吗？此操作不会重置人物画像。')) return
  await store.newSession(true)
}
async function resetProfile(): Promise<void> {
  if (!window.confirm(`确认重置用户 ${store.userId} 的画像和测试会话吗？此操作不可撤销。`)) return
  try {
    await store.resetProfile()
    message.success('人物画像已重置')
  } catch (error) {
    message.error(error instanceof Error ? error.message : '画像重置失败')
  }
}
async function retryUpdate(): Promise<void> {
  try {
    await store.retryProfileUpdate()
    message.success('画像更新已重试')
  } catch (error) {
    message.error(error instanceof Error ? error.message : '重试失败')
  }
}
</script>

<style scoped lang="less">
.companion-dashboard {
  min-height: calc(100vh - 64px);
  padding: 18px;
  display: grid;
  grid-template-columns: minmax(250px, 0.78fr) minmax(420px, 1.55fr) minmax(260px, 0.85fr);
  gap: 14px;
  color: #193a31;
  background: #eef3f1;
}
.dashboard-panel {
  min-height: 0;
  border: 1px solid #d6e1dd;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 10px 28px rgba(38, 73, 62, 0.07);
  overflow: hidden;
}
.profile-panel,
.status-panel {
  padding: 18px;
  overflow-y: auto;
}
.chat-panel {
  display: flex;
  flex-direction: column;
}
.panel-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}
.panel-heading span,
.profile-card > span,
.status-card > span {
  color: #6f857e;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.12em;
}
.panel-heading h2 {
  margin: 3px 0 0;
  font-size: 20px;
}
button {
  border: 1px solid #bfd1ca;
  border-radius: 9px;
  padding: 8px 11px;
  color: #245346;
  background: white;
  cursor: pointer;
}
button:hover {
  border-color: #148267;
}
.icon-button {
  width: 34px;
  height: 34px;
  padding: 0;
  font-size: 18px;
}
.user-field {
  display: grid;
  gap: 6px;
  margin-bottom: 12px;
  color: #6a7e77;
  font-size: 11px;
}
.user-field input {
  min-width: 0;
  padding: 10px;
  border: 1px solid #d0ddd8;
  border-radius: 9px;
}
.profile-version {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  border-radius: 11px;
  color: #14735c;
  background: #edf8f4;
}
.profile-card,
.status-card {
  margin-top: 12px;
  padding: 13px;
  border: 1px solid #e1e9e6;
  border-radius: 12px;
}
.profile-card.emphasis {
  border-color: #b9dbcf;
  background: #f4faf7;
}
.profile-card p {
  margin: 8px 0 0;
  line-height: 1.65;
}
.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 9px;
}
.tag-list i {
  padding: 4px 7px;
  border-radius: 999px;
  color: #246653;
  background: #e8f5f0;
  font-size: 10px;
  font-style: normal;
}
.tag-list em,
.status-card em {
  color: #8b9b96;
  font-size: 12px;
  font-style: normal;
}
.trait-row {
  display: flex;
  justify-content: space-between;
  margin-top: 8px;
}
.profile-card pre {
  max-height: 150px;
  margin: 8px 0 0;
  white-space: pre-wrap;
  color: #456259;
  font: 11px/1.5 inherit;
}
.updated-at {
  display: block;
  margin-top: 14px;
  color: #81918c;
}
.chat-heading {
  padding: 18px 18px 0;
}
.chat-actions {
  display: flex;
  gap: 6px;
}
.demo-notice {
  margin: 0 18px 12px;
  padding: 9px 12px;
  border-radius: 9px;
  color: #537068;
  background: #f0f6f4;
  font-size: 12px;
}
.message-list {
  flex: 1;
  min-height: 240px;
  overflow-y: auto;
  padding: 10px 18px 18px;
}
.message {
  max-width: 82%;
  margin: 13px 0;
}
.message > span {
  color: #789087;
  font-size: 10px;
  font-weight: 800;
}
.message p {
  margin: 5px 0 0;
  padding: 11px 13px;
  border-radius: 13px;
  line-height: 1.65;
  white-space: pre-wrap;
}
.message.user {
  margin-left: auto;
  text-align: right;
}
.message.user p {
  color: white;
  background: #148267;
  text-align: left;
  border-bottom-right-radius: 4px;
}
.message.assistant p {
  background: #f0f4f2;
  border-bottom-left-radius: 4px;
}
.message small {
  color: #b42318;
}
.chat-empty {
  height: 100%;
  display: grid;
  place-content: center;
  gap: 6px;
  color: #8a9b95;
  text-align: center;
}
.composer {
  padding: 14px 18px 18px;
  border-top: 1px solid #e1e9e6;
}
.composer textarea {
  width: 100%;
  resize: none;
  box-sizing: border-box;
  padding: 12px;
  border: 1px solid #cbd9d4;
  border-radius: 11px;
  font: inherit;
  outline: none;
}
.composer textarea:focus {
  border-color: #148267;
  box-shadow: 0 0 0 3px rgba(20, 130, 103, 0.1);
}
.composer > div {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
}
.composer button {
  min-width: 80px;
  color: white;
  border-color: #148267;
  background: #148267;
}
.composer button.stop {
  color: #9b3129;
  border-color: #e5b7b2;
  background: #fff6f5;
}
.service-row {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid #edf1ef;
  font-size: 12px;
}
.service-row:last-child {
  border: 0;
}
.service-row span {
  display: flex;
  align-items: center;
  gap: 7px;
}
.service-row i {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #d7a129;
}
.service-row i.ok {
  background: #20a378;
  box-shadow: 0 0 0 3px rgba(32, 163, 120, 0.12);
}
.profile-toggle {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 12px;
  padding: 13px;
  border-radius: 12px;
  background: #eff7f4;
}
.profile-toggle span {
  display: grid;
  gap: 3px;
}
.profile-toggle small {
  color: #758982;
}
.profile-toggle input {
  width: 18px;
  height: 18px;
  accent-color: #148267;
}
.update-card strong {
  display: block;
  margin: 10px 0 5px;
  color: #148267;
}
.update-card strong.is-failed {
  color: #b5473d;
}
.update-card ul {
  padding-left: 18px;
  color: #4d6a61;
  font-size: 12px;
}
.update-card p,
.system-error {
  color: #a63d35;
  font-size: 12px;
}
.latency-card dl {
  margin: 8px 0 0;
}
.latency-card dl > div {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
}
.latency-card dt,
.latency-card dd {
  margin: 3px 0;
}
.danger-button {
  width: 100%;
  margin-top: 12px;
  color: #a13d35;
  border-color: #e4b8b4;
}
.empty-state {
  padding: 30px 10px;
  color: #8a9b95;
  text-align: center;
}
@media (max-width: 1050px) {
  .companion-dashboard {
    grid-template-columns: 260px 1fr;
  }
  .status-panel {
    grid-column: 1 / -1;
  }
}
@media (max-width: 720px) {
  .companion-dashboard {
    padding: 10px;
    grid-template-columns: 1fr;
  }
  .status-panel {
    grid-column: auto;
  }
  .profile-panel,
  .status-panel {
    max-height: none;
  }
  .chat-panel {
    min-height: 72vh;
  }
  .chat-heading {
    align-items: flex-start;
  }
  .chat-actions {
    flex-direction: column;
  }
}
</style>
