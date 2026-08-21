<template>
  <main class="companion-dashboard">
    <section class="role-showcase" aria-labelledby="example-role-heading">
      <header class="showcase-heading">
        <div>
          <span>READY-TO-TRY COMPANIONS</span>
          <h1 id="example-role-heading">选择一种陪伴风格</h1>
          <p>每个示例都有清晰的互动特点。切换后会自动开启独立的新会话。</p>
        </div>
        <small v-if="store.sending">完成当前回复后即可切换</small>
      </header>
      <div v-if="!store.examplesReady" class="showcase-loading">正在准备示例角色…</div>
      <div v-else class="example-grid">
        <button
          v-for="(example, index) in store.examples"
          :key="example.id"
          type="button"
          :class="['example-card', { active: example.id === store.userId }]"
          :disabled="store.sending || store.switchingExample"
          :aria-pressed="example.id === store.userId"
          @click="selectExample(example.id)"
        >
          <span class="example-index">示例 {{ String(index + 1).padStart(2, '0') }}</span>
          <strong>{{ example.name }}</strong>
          <b>{{ example.tagline }}</b>
          <p>{{ example.description }}</p>
          <small v-if="example.prompt_suggestions[0]">
            可以这样开始：{{ example.prompt_suggestions[0] }}
          </small>
          <i>{{ example.id === store.userId ? '正在体验' : '选择体验' }}</i>
        </button>
      </div>
    </section>

    <aside class="dashboard-panel profile-panel">
      <header class="panel-heading">
        <div>
          <span>PERSONALIZED CONTEXT</span>
          <h2>人物画像</h2>
        </div>
        <button class="icon-button" title="刷新画像" @click="store.refreshProfile">↻</button>
      </header>
      <section v-if="activeExample" class="active-example">
        <span>当前陪伴角色</span>
        <strong>{{ activeExample.name }}</strong>
        <small>{{ activeExample.tagline }}</small>
      </section>
      <template v-if="profile">
        <div class="profile-readiness">
          <strong>完整示例</strong>
          <span>人物特点与沟通偏好已准备</span>
        </div>
        <section v-if="profile.portrait?.essence" class="profile-card emphasis">
          <span>稳定画像摘要</span>
          <p>{{ profile.portrait.essence }}</p>
        </section>
        <section v-if="strengths.length" class="profile-card">
          <span>主要优势</span>
          <ul class="portrait-list">
            <li v-for="item in strengths" :key="item">{{ item }}</li>
          </ul>
        </section>
        <section v-if="coreTension" class="profile-card">
          <span>需要平衡的方向</span>
          <p>{{ coreTension }}</p>
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
            <b>{{ trait.level }}</b>
          </div>
        </section>
        <section class="profile-card">
          <span>当前状态</span>
          <pre>{{ prettyState }}</pre>
        </section>
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
        当前由“{{ activeExample?.name || '陪伴角色' }}”与你对话。人物画像只用于改善表达与连续性。
      </div>
      <div v-if="activeExample?.prompt_suggestions.length" class="prompt-suggestions">
        <span>不知道从哪里开始？试试：</span>
        <button
          v-for="prompt in activeExample.prompt_suggestions"
          :key="prompt"
          type="button"
          @click="draft = prompt"
        >
          {{ prompt }}
        </button>
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
      <section class="status-card status-overview">
        <div class="service-row">
          <span>
            <i :class="{ ok: health?.status === 'ok' }" />
            体验服务
          </span>
          <b>{{ health?.status === 'ok' ? '正常' : '正在恢复' }}</b>
        </div>
        <p>页面仅展示整理后的互动结论，不显示内部计算过程。</p>
      </section>
      <section class="status-card example-policy">
        <span>示例说明</span>
        <strong>固定、只读、彼此独立</strong>
        <p>五个示例保持原有特点，不会被其他访问者的对话改写；切换角色会自动开启新会话。</p>
      </section>
      <p v-if="store.error" class="system-error" role="alert">{{ store.error }}</p>
    </aside>
  </main>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'

import { useCompanionStore } from '@/store/companion'

const store = useCompanionStore()
const { profile, health } = storeToRefs(store)
const draft = ref('')
const messageList = ref<HTMLElement>()
const activeExample = computed(() => store.examples.find((item) => item.id === store.userId))

const prettyState = computed(() => {
  const state = profile.value?.current_state || {}
  return Object.keys(state).length ? JSON.stringify(state, null, 2) : '暂无短期状态'
})
const strengths = computed(() => {
  const value = profile.value?.portrait?.strengths
  if (Array.isArray(value)) return value.filter((item): item is string => typeof item === 'string')
  return typeof value === 'string' && value ? [value] : []
})
const coreTension = computed(() => {
  const value = profile.value?.portrait?.core_tension
  return typeof value === 'string' ? value : ''
})

watch(
  () => store.messages.map((item) => item.content).join('|'),
  async () => {
    await nextTick()
    if (messageList.value) messageList.value.scrollTop = messageList.value.scrollHeight
  }
)

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
async function selectExample(exampleId: string): Promise<void> {
  await store.selectExample(exampleId)
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
.role-showcase {
  grid-column: 1 / -1;
  padding: 18px;
  border: 1px solid #cbded7;
  border-radius: 18px;
  background:
    radial-gradient(circle at 8% 10%, rgba(34, 164, 126, 0.12), transparent 28%),
    linear-gradient(135deg, #f9fcfb, #edf7f3);
  box-shadow: 0 10px 28px rgba(38, 73, 62, 0.07);
}
.showcase-heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}
.showcase-heading span {
  color: #238066;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.14em;
}
.showcase-heading h1 {
  margin: 3px 0 2px;
  color: #173f34;
  font-size: 22px;
}
.showcase-heading p,
.showcase-heading small {
  margin: 0;
  color: #637a72;
  font-size: 12px;
}
.showcase-loading {
  padding: 24px;
  color: #6f857e;
  text-align: center;
}
.example-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
}
.example-card {
  position: relative;
  min-width: 0;
  min-height: 190px;
  padding: 14px;
  border: 1px solid #d2e1dc;
  border-radius: 14px;
  color: #244c41;
  background: rgba(255, 255, 255, 0.9);
  text-align: left;
  transition:
    transform 160ms ease,
    border-color 160ms ease,
    box-shadow 160ms ease;
}
.example-card:hover:not(:disabled) {
  transform: translateY(-2px);
  border-color: #56a990;
  box-shadow: 0 8px 20px rgba(30, 104, 81, 0.1);
}
.example-card.active {
  border-color: #148267;
  background: #f2fbf7;
  box-shadow: inset 0 0 0 1px rgba(20, 130, 103, 0.15);
}
.example-card:disabled {
  cursor: not-allowed;
  opacity: 0.72;
}
.example-card .example-index {
  display: block;
  margin-bottom: 8px;
  color: #7c918a;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.1em;
}
.example-card > strong,
.example-card > b,
.example-card > small {
  display: block;
}
.example-card > strong {
  color: #174b3d;
  font-size: 17px;
}
.example-card > b {
  margin-top: 4px;
  color: #258066;
  font-size: 11px;
}
.example-card > p {
  margin: 9px 0;
  color: #536f66;
  font-size: 11px;
  line-height: 1.5;
}
.example-card > small {
  padding-top: 8px;
  border-top: 1px solid #e5eeeb;
  color: #788c85;
  font-size: 10px;
  line-height: 1.45;
}
.example-card > i {
  display: inline-block;
  margin-top: 10px;
  color: #14755c;
  font-size: 10px;
  font-style: normal;
  font-weight: 800;
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
.active-example {
  display: grid;
  gap: 4px;
  margin-bottom: 12px;
  padding: 11px;
  border: 1px solid #c9ded6;
  border-radius: 11px;
  background: #f3f9f7;
}
.active-example span {
  color: #758982;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.1em;
}
.active-example strong {
  color: #17664f;
}
.active-example small {
  color: #617a71;
}
.profile-readiness {
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
.portrait-list {
  margin: 8px 0 0;
  padding-left: 18px;
  color: #456259;
  font-size: 12px;
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
.prompt-suggestions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin: 0 18px 4px;
}
.prompt-suggestions > span {
  color: #768a83;
  font-size: 10px;
}
.prompt-suggestions button {
  max-width: 100%;
  padding: 5px 8px;
  overflow: hidden;
  color: #35685a;
  background: #f8fbfa;
  font-size: 10px;
  text-overflow: ellipsis;
  white-space: nowrap;
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
.example-policy strong {
  display: block;
  margin: 10px 0 5px;
  color: #148267;
}
.status-overview p,
.example-policy p {
  margin: 9px 0 0;
  color: #657b74;
  font-size: 12px;
  line-height: 1.6;
}
.system-error {
  color: #a63d35;
  font-size: 12px;
}
.empty-state {
  padding: 30px 10px;
  color: #8a9b95;
  text-align: center;
}
@media (max-width: 1050px) {
  .example-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
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
  .role-showcase {
    padding: 14px;
  }
  .showcase-heading {
    align-items: flex-start;
    flex-direction: column;
  }
  .example-grid {
    display: flex;
    margin-right: -14px;
    padding-right: 14px;
    overflow-x: auto;
    scroll-snap-type: x mandatory;
  }
  .example-card {
    flex: 0 0 min(82vw, 290px);
    scroll-snap-align: start;
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
