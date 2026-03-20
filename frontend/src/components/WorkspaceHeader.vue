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
  statusLabel: {
    type: String,
    required: true,
  },
  description: {
    type: String,
    required: true,
  },
  fileName: {
    type: String,
    default: "",
  },
});

const emit = defineEmits(["toggle-sidebar", "request-login"]);
</script>

<template>
  <header class="workspace-header">
    <div class="workspace-header__left">
      <button class="mobile-menu" @click="emit('toggle-sidebar')">
        <slot name="left-icon" />
      </button>
      <div>
        <p class="eyebrow">Audio Analysis Workspace</p>
        <h2>{{ fileName || "围绕会议音频持续工作" }}</h2>
        <p class="description">{{ description }}</p>
      </div>
    </div>

    <div class="workspace-header__right">
      <div class="status-pill">{{ statusLabel }}</div>
      <button v-if="!authenticated" class="auth-button" @click="emit('request-login')">登录</button>
      <div v-else class="account-pill">
        <strong>{{ session.user.username }}</strong>
        <span>{{ session.user.email }}</span>
      </div>
    </div>
  </header>
</template>

<style scoped>
.workspace-header {
  position: sticky;
  top: 0;
  z-index: 6;
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  padding: 14px 22px 12px;
  border-bottom: 1px solid var(--line-soft);
  background: rgba(253, 254, 255, 0.92);
  backdrop-filter: blur(14px);
}

.workspace-header__left,
.workspace-header__right {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}

.mobile-menu {
  display: none;
  width: 34px;
  height: 34px;
  border: 1px solid var(--line-soft);
  border-radius: 10px;
  background: var(--surface-base);
  color: var(--text-main);
}

.eyebrow {
  margin: 0 0 4px;
  color: var(--text-soft);
  font-size: 0.68rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

h2 {
  margin: 0;
  color: var(--text-strong);
  font-size: clamp(1.08rem, 1.8vw, 1.34rem);
  letter-spacing: -0.03em;
}

.description {
  max-width: 58ch;
  margin: 6px 0 0;
  color: var(--text-soft);
  font-size: 0.88rem;
  line-height: 1.55;
}

.status-pill,
.auth-button,
.account-pill {
  min-height: 32px;
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 0 12px;
  border: 1px solid var(--line-soft);
  background: var(--surface-base);
}

.status-pill {
  color: var(--accent-strong);
  font-size: 0.78rem;
  font-weight: 700;
}

.auth-button {
  color: var(--text-strong);
  cursor: pointer;
  font-weight: 700;
}

.account-pill {
  display: grid;
  gap: 2px;
  min-height: auto;
  padding: 7px 12px;
}

.account-pill strong {
  color: var(--text-strong);
  font-size: 0.86rem;
}

.account-pill span {
  color: var(--text-soft);
  font-size: 0.72rem;
}

@media (max-width: 980px) {
  .workspace-header {
    padding: 12px;
    flex-direction: column;
  }

  .workspace-header__right {
    width: 100%;
    justify-content: space-between;
  }

  .mobile-menu {
    display: inline-grid;
    place-items: center;
  }
}
</style>
