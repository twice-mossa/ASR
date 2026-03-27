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
  progressCompleted: {
    type: Number,
    default: 0,
  },
  progressTotal: {
    type: Number,
    default: 1,
  },
  progressStatus: {
    type: String,
    default: "idle",
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
      <div class="title-block">
        <p class="eyebrow">Audio Workspace</p>
        <div class="title-row">
          <h2>{{ fileName || "围绕会议音频持续工作" }}</h2>
          <p class="description">{{ description }}</p>
        </div>
        <div
          v-if="['queued', 'processing', 'transcribing', 'stopping', 'uploading'].includes(progressStatus) && progressTotal > 0"
          class="progress-strip"
        >
          <div class="progress-strip__meta">
            <span>{{ progressStatus === "stopping" ? "正在停止" : progressStatus === "uploading" ? "上传进度" : "转录进度" }}</span>
            <strong>{{ progressStatus === "uploading" ? `${progressCompleted}%` : `${progressCompleted} / ${progressTotal}` }}</strong>
          </div>
          <div class="progress-strip__bar">
            <span :style="{ width: `${progressStatus === 'uploading' ? Math.min(100, Math.max(0, progressCompleted)) : Math.min(100, Math.max(0, (progressCompleted / progressTotal) * 100))}%` }" />
          </div>
        </div>
      </div>
    </div>

    <div class="workspace-header__right">
      <div class="status-pill">{{ statusLabel }}</div>
      <button v-if="!authenticated" class="auth-button" @click="emit('request-login')">登录</button>
      <div v-else class="account-pill">
        <strong>{{ session.user.username }}</strong>
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
  gap: 12px;
  align-items: center;
  padding: 11px 18px 10px;
  border-bottom: 1px solid var(--line-soft);
  background: rgba(248, 250, 252, 0.88);
  backdrop-filter: blur(12px);
}

.workspace-header__left,
.workspace-header__right {
  display: flex;
  gap: 10px;
  align-items: center;
}

.mobile-menu {
  display: none;
  width: 32px;
  height: 32px;
  border: 1px solid var(--line-soft);
  border-radius: 10px;
  background: var(--surface-base);
  color: var(--text-main);
}

.title-block {
  min-width: 0;
}

.title-row {
  display: flex;
  align-items: baseline;
  gap: 12px;
  min-width: 0;
}

.eyebrow {
  margin: 0 0 3px;
  color: var(--text-soft);
  font-size: 0.62rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

h2 {
  margin: 0;
  color: var(--text-strong);
  font-size: clamp(1rem, 1.4vw, 1.16rem);
  letter-spacing: -0.03em;
  white-space: nowrap;
}

.description {
  max-width: 56ch;
  min-width: 0;
  margin: 0;
  color: var(--text-soft);
  font-size: 0.8rem;
  line-height: 1.4;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.progress-strip {
  margin-top: 8px;
  display: grid;
  gap: 5px;
}

.progress-strip__meta {
  display: flex;
  gap: 8px;
  align-items: center;
  color: var(--text-soft);
  font-size: 0.72rem;
}

.progress-strip__meta strong {
  color: var(--text-strong);
}

.progress-strip__bar {
  width: min(280px, 100%);
  height: 6px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.18);
}

.progress-strip__bar span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #1f4fd1, #60a5fa);
}

.status-pill,
.auth-button,
.account-pill {
  min-height: 30px;
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 0 11px;
  border: 1px solid var(--line-soft);
  background: var(--surface-base);
}

.status-pill {
  color: var(--accent-strong);
  font-size: 0.74rem;
  font-weight: 700;
}

.auth-button {
  color: var(--text-strong);
  cursor: pointer;
  font-weight: 700;
}

.account-pill {
  min-height: 30px;
  padding: 0 11px;
}

.account-pill strong {
  color: var(--text-strong);
  font-size: 0.8rem;
}

@media (max-width: 980px) {
  .workspace-header {
    padding: 12px;
    flex-direction: column;
    align-items: stretch;
  }

  .workspace-header__right {
    width: 100%;
    justify-content: space-between;
  }

  .title-row {
    display: block;
  }

  h2,
  .description {
    white-space: normal;
  }

  .mobile-menu {
    display: inline-grid;
    place-items: center;
  }
}
</style>
