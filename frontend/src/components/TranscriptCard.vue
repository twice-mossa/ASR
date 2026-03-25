<script setup>
import { computed, ref } from "vue";

import { formatTimestamp } from "../utils/workspace";

const props = defineProps({
  transcript: {
    type: Object,
    required: true,
  },
});

const emit = defineEmits(["seek"]);
const keywordQuery = ref("");

const filteredSegments = computed(() => {
  const segments = props.transcript.segments || [];
  const normalizedQuery = keywordQuery.value.trim().toLowerCase();
  if (!normalizedQuery) {
    return segments;
  }
  return segments.filter((segment) => String(segment.text || "").toLowerCase().includes(normalizedQuery));
});

const diarizationMessage = computed(() => {
  const status = String(props.transcript.speaker_diarization_status || "not_requested");
  if (status === "pending") {
    return props.transcript.speaker_diarization_message || "转录完成后将补充分说话人结果。";
  }
  if (status === "failed") {
    return props.transcript.speaker_diarization_message || "已完成转录，但说话人区分未完成。";
  }
  return "";
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
    <p v-if="diarizationMessage" class="diarization-note">{{ diarizationMessage }}</p>

    <details v-if="transcript.segments?.length" class="segment-panel">
      <summary>查看时间分段（{{ transcript.segments.length }}）</summary>
      <div class="segment-search">
        <input v-model.trim="keywordQuery" type="search" placeholder="检索关键词并定位到对应片段" />
        <span>{{ keywordQuery ? `命中 ${filteredSegments.length} 段` : "点击片段可跳转回放" }}</span>
      </div>
      <div class="segment-list">
        <button
          v-for="segment in filteredSegments"
          :key="`${segment.start}-${segment.end}`"
          class="segment-item"
          type="button"
          @click="emit('seek', segment.start)"
        >
          <strong>
            <span v-if="segment.speaker_label" class="speaker-chip">{{ segment.speaker_label }}</span>
            {{ formatTimestamp(segment.start) }} - {{ formatTimestamp(segment.end) }}
          </strong>
          <span>{{ segment.text }}</span>
        </button>
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

.diarization-note {
  margin: 10px 0 0;
  color: var(--text-soft);
  font-size: 0.82rem;
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

.segment-search {
  display: grid;
  gap: 8px;
  margin-top: 12px;
}

.segment-search input {
  width: 100%;
  min-height: 36px;
  padding: 0 12px;
  border: 1px solid var(--line-soft);
  border-radius: 12px;
  outline: none;
}

.segment-search span {
  color: var(--text-soft);
  font-size: 0.78rem;
}

.segment-item {
  display: grid;
  gap: 5px;
  width: 100%;
  padding: 10px 12px;
  border: 0;
  border-radius: 14px;
  background: #f8fafc;
  cursor: pointer;
  text-align: left;
}

.segment-item strong {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  color: var(--accent-strong);
  font-size: 0.8rem;
}

.speaker-chip {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(37, 99, 235, 0.12);
  color: #1d4ed8;
  font-size: 0.72rem;
  font-weight: 600;
}

.segment-item span {
  color: var(--text-main);
  line-height: 1.62;
}

.segment-item:hover {
  background: #edf4ff;
}
</style>
