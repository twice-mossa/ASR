<script setup>
defineProps({
  summary: {
    type: String,
    default: "",
  },
  canDownloadNotes: {
    type: Boolean,
    required: true,
  },
});

const emit = defineEmits(["ask", "download"]);
</script>

<template>
  <section class="result-card">
    <div class="card-header">
      <div>
        <p class="label">Summary</p>
        <h4>会议摘要</h4>
      </div>
      <div class="card-actions">
        <button class="inline-action inline-action--ghost" @click="emit('ask')">追问风险与建议</button>
        <button class="inline-action" :disabled="!canDownloadNotes" @click="emit('download')">下载会议纪要</button>
      </div>
    </div>
    <p>{{ summary }}</p>
  </section>
</template>

<style scoped>
.result-card {
  margin-top: 12px;
  padding: 16px;
  border: 1px solid var(--line-soft);
  border-radius: 18px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 1), rgba(249, 251, 255, 1));
}

.card-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
  margin-bottom: 10px;
}

.card-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
}

.label {
  margin: 0 0 6px;
  color: var(--text-soft);
  font-size: 0.68rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

h4 {
  margin: 0;
  color: var(--text-strong);
  font-size: 0.98rem;
}

p {
  margin: 0;
  color: var(--text-main);
  line-height: 1.72;
}

.inline-action {
  min-height: 32px;
  padding: 0 11px;
  border: 0;
  border-radius: 999px;
  background: var(--accent);
  color: white;
  font-size: 0.8rem;
  font-weight: 700;
  cursor: pointer;
}

.inline-action:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.inline-action--ghost {
  border: 1px solid var(--line-soft);
  background: white;
  color: var(--text-main);
}
</style>
