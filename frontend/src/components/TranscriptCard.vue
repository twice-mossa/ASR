<script setup>
defineProps({
  transcript: {
    type: Object,
    required: true,
  },
});
</script>

<template>
  <section class="analysis-card">
    <div class="analysis-header">
      <div>
        <p class="label">Transcript</p>
        <h4>{{ transcript.filename || "当前转录" }}</h4>
      </div>
      <span>{{ transcript.language || "zh" }}</span>
    </div>

    <div class="text-block">{{ transcript.text || "正在等待转录内容返回。" }}</div>

    <details v-if="transcript.segments?.length" class="segment-panel">
      <summary>查看时间分段（{{ transcript.segments.length }}）</summary>
      <div class="segment-list">
        <article v-for="segment in transcript.segments" :key="`${segment.start}-${segment.end}`" class="segment-item">
          <strong>{{ segment.start.toFixed(1) }}s - {{ segment.end.toFixed(1) }}s</strong>
          <span>{{ segment.text }}</span>
        </article>
      </div>
    </details>
  </section>
</template>

<style scoped>
.analysis-card {
  margin-top: 12px;
  padding: 16px;
  border: 1px solid var(--line-soft);
  border-radius: 18px;
  background: white;
}

.analysis-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 12px;
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

.analysis-header span {
  color: var(--text-soft);
  font-size: 0.82rem;
}

.text-block {
  padding: 12px 13px;
  border-radius: 14px;
  background: var(--surface-soft);
  color: var(--text-main);
  line-height: 1.72;
  white-space: pre-wrap;
}

.segment-panel {
  margin-top: 12px;
}

.segment-panel summary {
  color: var(--text-soft);
  font-size: 0.82rem;
  cursor: pointer;
  user-select: none;
}

.segment-list {
  display: grid;
  gap: 8px;
  margin-top: 10px;
  max-height: 260px;
  overflow: auto;
}

.segment-item {
  display: grid;
  gap: 5px;
  padding: 10px 12px;
  border-radius: 14px;
  background: #f8fafc;
}

.segment-item strong {
  color: var(--accent-strong);
  font-size: 0.8rem;
}

.segment-item span {
  color: var(--text-main);
  line-height: 1.62;
}
</style>
