<script setup>
import { formatTimestamp } from "../utils/workspace";

defineProps({
  answer: {
    type: String,
    default: "",
  },
  citations: {
    type: Array,
    default: () => [],
  },
});

const emit = defineEmits(["seek"]);
</script>

<template>
  <section class="answer-card">
    <div class="answer-card__header">
      <div>
        <p class="label">Answer</p>
        <h4>会议问答</h4>
      </div>
      <span>{{ citations.length ? `${citations.length} 条引用` : "无引用" }}</span>
    </div>

    <p class="answer-card__text">{{ answer || "暂无回答内容。" }}</p>

    <div v-if="citations.length" class="citation-list">
      <button
        v-for="citation in citations"
        :key="`${citation.segment_id || 'segment'}-${citation.start}-${citation.end}`"
        class="citation-item"
        @click="emit('seek', citation.start)"
      >
        <strong>{{ formatTimestamp(citation.start) }} - {{ formatTimestamp(citation.end) }}</strong>
        <span>{{ citation.text }}</span>
      </button>
    </div>
  </section>
</template>

<style scoped>
.answer-card {
  margin-top: 14px;
  padding: 18px;
  border: 1px solid rgba(29, 78, 216, 0.16);
  border-radius: 20px;
  background: linear-gradient(180deg, #ffffff, #f6f9ff);
}

.answer-card__header {
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
  font-size: 1.06rem;
}

.answer-card__header span {
  color: var(--text-soft);
  font-size: 0.82rem;
}

.answer-card__text {
  margin: 0;
  color: var(--text-main);
  line-height: 1.82;
  white-space: pre-wrap;
}

.citation-list {
  display: grid;
  gap: 10px;
  margin-top: 14px;
}

.citation-item {
  display: grid;
  gap: 5px;
  padding: 12px 14px;
  border: 1px solid rgba(37, 99, 235, 0.12);
  border-radius: 16px;
  background: white;
  cursor: pointer;
  text-align: left;
  transition: transform 180ms ease, border-color 180ms ease, background 180ms ease;
}

.citation-item:hover {
  transform: translateY(-1px);
  border-color: rgba(37, 99, 235, 0.28);
  background: #fbfdff;
}

.citation-item strong {
  color: var(--accent-strong);
  font-size: 0.84rem;
}

.citation-item span {
  color: var(--text-main);
  line-height: 1.7;
}
</style>
