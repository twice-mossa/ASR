<script setup>
defineProps({
  authenticated: {
    type: Boolean,
    required: true,
  },
  session: {
    type: Object,
    required: true,
  },
  conversations: {
    type: Array,
    default: () => [],
  },
  activeConversationId: {
    type: [String, Number],
    default: "",
  },
});

const emit = defineEmits(["select-conversation", "new-analysis", "request-login", "logout"]);
</script>

<template>
  <div class="sidebar">
    <div class="brand-block">
      <div class="brand-mark">AM</div>
      <div>
        <p class="brand-eyebrow">Meeting Intelligence</p>
        <h1>Audio Memo</h1>
      </div>
    </div>

    <button class="new-analysis" @click="emit('new-analysis')">+ 新建分析</button>

    <section class="history-block">
      <div class="block-header">
        <span>历史会议</span>
        <small>{{ conversations.length }}</small>
      </div>

      <div class="history-list">
        <button
          v-for="item in conversations"
          :key="item.id"
          class="history-item"
          :class="{ 'history-item--active': activeConversationId === item.id }"
          @click="emit('select-conversation', item.id)"
        >
          <strong>{{ item.title }}</strong>
          <span>{{ item.preview }}</span>
          <small>{{ item.updatedLabel }}</small>
        </button>
      </div>
    </section>

    <div class="account-block">
      <div class="account-copy">
        <p class="account-label">{{ authenticated ? "当前账号" : "访客模式" }}</p>
        <strong>{{ authenticated ? session.user.username : "登录以保存分析记录" }}</strong>
        <span>
          {{ authenticated ? session.user.email : "上传、转录、生成摘要和后续问答都会在需要时提示登录。" }}
        </span>
      </div>
      <button v-if="authenticated" class="account-action account-action--ghost" @click="emit('logout')">退出</button>
      <button v-else class="account-action" @click="emit('request-login')">登录</button>
    </div>
  </div>
</template>

<style scoped>
.sidebar {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px 12px 12px;
  overflow-y: auto;
}

.brand-block {
  display: flex;
  align-items: center;
  gap: 9px;
}

.brand-mark {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border-radius: 11px;
  background: linear-gradient(145deg, #1f4fd1, #11337d);
  color: #f8fbff;
  font-size: 0.82rem;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.brand-eyebrow {
  margin: 0 0 4px;
  color: var(--text-soft);
  font-size: 0.62rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

h1 {
  margin: 0;
  font-size: 0.98rem;
  color: var(--text-strong);
  letter-spacing: -0.02em;
}

.new-analysis,
.account-action {
  min-height: 36px;
  border: 0;
  border-radius: 11px;
  background: var(--accent);
  color: white;
  font-size: 0.88rem;
  font-weight: 700;
  cursor: pointer;
  transition: transform 180ms ease, background 180ms ease;
}

.new-analysis:hover,
.account-action:hover {
  transform: translateY(-1px);
  background: var(--accent-strong);
}

.history-block {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 10px 0 0;
}

.block-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  padding: 0 4px;
  color: var(--text-soft);
  font-size: 0.68rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.history-list {
  display: grid;
  gap: 4px;
  overflow-y: auto;
}

.history-item {
  display: grid;
  gap: 4px;
  padding: 10px 11px;
  border: 1px solid transparent;
  border-radius: 12px;
  background: transparent;
  color: var(--text-main);
  cursor: pointer;
  text-align: left;
  transition: background 180ms ease, border-color 180ms ease, transform 180ms ease;
}

.history-item strong {
  color: var(--text-strong);
  font-size: 0.82rem;
  line-height: 1.45;
}

.history-item span,
.history-item small,
.account-copy span {
  color: var(--text-soft);
  line-height: 1.52;
  font-size: 0.74rem;
}

.history-item small {
  font-size: 0.66rem;
}

.history-item:hover,
.history-item--active {
  background: rgba(255, 255, 255, 0.78);
  border-color: rgba(148, 163, 184, 0.14);
}

.history-item span {
  display: -webkit-box;
  overflow: hidden;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.account-block {
  margin-top: auto;
  display: grid;
  gap: 10px;
  padding: 12px;
  border-top: 1px solid var(--line-soft);
}

.account-copy {
  display: grid;
  gap: 5px;
}

.account-label {
  margin: 0;
  color: var(--text-soft);
  font-size: 0.64rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.account-copy strong {
  color: var(--text-strong);
  font-size: 0.86rem;
}

.account-action--ghost {
  background: rgba(255, 255, 255, 0.9);
  color: var(--text-main);
  border: 1px solid var(--line-soft);
}
</style>
