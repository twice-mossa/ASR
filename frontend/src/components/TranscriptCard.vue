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

    <div class="segment-list" v-if="transcript.segments?.length">
      <article v-for="segment in transcript.segments" :key="`${segment.start}-${segment.end}`" class="segment-item">
        <strong>{{ segment.start.toFixed(1) }}s - {{ segment.end.toFixed(1) }}s</strong>
        <span>{{ segment.text }}</span>
      </article>
    </div>
  </section>
</template>

<style scoped>
.analysis-card {
  margin-top: 14px;
  padding: 18px;
  border: 1px solid var(--line-soft);
  border-radius: 20px;
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
  font-size: 0.74rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

h4 {
  margin: 0;
  color: var(--text-strong);
  font-size: 1.08rem;
}

.analysis-header span {
  color: var(--text-soft);
  font-size: 0.9rem;
}

.text-block {
  padding: 14px;
  border-radius: 16px;
  background: var(--surface-soft);
  color: var(--text-main);
  line-height: 1.8;
  white-space: pre-wrap;
}

.segment-list {
  display: grid;
  gap: 10px;
  margin-top: 12px;
  max-height: 300px;
  overflow: auto;
}

.segment-item {
  display: grid;
  gap: 6px;
  padding: 12px 14px;
  border-radius: 16px;
  background: #f8fafc;
}

.segment-item strong {
  color: var(--accent-strong);
  font-size: 0.86rem;
}

.segment-item span {
  color: var(--text-main);
  line-height: 1.7;
}
</style>
