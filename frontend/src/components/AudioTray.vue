<script setup>
defineProps({
  workspace: {
    type: Object,
    required: true,
  },
  canDownloadNotes: {
    type: Boolean,
    required: true,
  },
});

const emit = defineEmits(["upload", "download"]);
</script>

<template>
  <div v-if="workspace.audioUrl" class="audio-tray">
    <div class="audio-tray__meta">
      <p class="audio-tray__label">当前音频轨道</p>
      <strong>{{ workspace.fileName }}</strong>
      <span>{{ workspace.durationLabel }} · {{ workspace.language || "zh" }}</span>
    </div>

    <audio :src="workspace.audioUrl" class="audio-player" controls preload="metadata" />

    <div class="audio-tray__actions">
      <button class="tray-button tray-button--ghost" @click="emit('upload')">更换音频</button>
      <button class="tray-button" :disabled="!canDownloadNotes" @click="emit('download')">下载会议纪要</button>
    </div>
  </div>
</template>

<style scoped>
.audio-tray {
  display: grid;
  grid-template-columns: auto minmax(260px, 1fr) auto;
  gap: 14px;
  align-items: center;
  padding: 10px 22px 12px;
  border-top: 1px solid var(--line-soft);
  background: linear-gradient(180deg, rgba(252, 253, 255, 0.92), rgba(248, 251, 255, 0.98));
  backdrop-filter: blur(14px);
}

.audio-tray__meta {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.audio-tray__label {
  margin: 0;
  color: var(--text-soft);
  font-size: 0.7rem;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}

.audio-tray__meta strong {
  color: var(--text-strong);
  font-size: 0.92rem;
  line-height: 1.4;
}

.audio-tray__meta span {
  color: var(--text-soft);
  font-size: 0.82rem;
}

.audio-player {
  width: 100%;
  min-width: 0;
  height: 36px;
}

.audio-tray__actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

.tray-button {
  min-height: 34px;
  padding: 0 12px;
  border: 0;
  border-radius: 999px;
  background: var(--accent);
  color: white;
  font-size: 0.84rem;
  font-weight: 700;
  cursor: pointer;
}

.tray-button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.tray-button--ghost {
  border: 1px solid var(--line-soft);
  background: var(--surface-base);
  color: var(--text-main);
}

@media (max-width: 980px) {
  .audio-tray {
    grid-template-columns: 1fr;
    gap: 10px;
    padding: 10px 12px;
  }

  .audio-tray__actions {
    justify-content: flex-start;
    flex-wrap: wrap;
  }
}
</style>
