<script setup>
import { computed } from "vue";

import { formatTimestamp } from "../utils/workspace";

const props = defineProps({
  answer: {
    type: String,
    default: "",
  },
  citations: {
    type: Array,
    default: () => [],
  },
  answerType: {
    type: String,
    default: "fact",
  },
  topicLabels: {
    type: Array,
    default: () => [],
  },
  evidenceBlocks: {
    type: Array,
    default: () => [],
  },
});

const emit = defineEmits(["seek"]);

const answerTypeLabel = computed(() => {
  if (props.answerType === "compare") {
    return "对比回答";
  }
  if (props.answerType === "theme_summary") {
    return "主题归纳";
  }
  if (props.answerType === "stance_or_suggestion") {
    return "观点判断";
  }
  if (props.answerType === "follow_up") {
    return "追问回答";
  }
  return "直接回答";
});
</script>

<template>
  <section class="answer-card">
    <div class="answer-card__header">
      <div>
        <p class="label">Answer</p>
        <h4>{{ answerTypeLabel }}</h4>
      </div>
      <span>{{ evidenceBlocks.length ? `${evidenceBlocks.length} 个证据块` : citations.length ? `${citations.length} 条引用` : "无引用" }}</span>
    </div>

    <div v-if="topicLabels.length" class="topic-labels">
      <span v-for="label in topicLabels" :key="label" class="topic-chip">{{ label }}</span>
    </div>

    <p class="answer-card__text">{{ answer || "暂无回答内容。" }}</p>

    <div v-if="evidenceBlocks.length" class="evidence-block-list">
      <section
        v-for="block in evidenceBlocks"
        :key="`${block.title}-${block.start}-${block.end}`"
        class="evidence-block"
      >
        <div class="evidence-block__header">
          <div>
            <strong>{{ block.title || "相关证据" }}</strong>
            <span>{{ formatTimestamp(block.start) }} - {{ formatTimestamp(block.end) }}</span>
          </div>
          <button class="jump-button" @click="emit('seek', block.start)">跳到这里</button>
        </div>
        <p class="evidence-block__summary">{{ block.summary || "暂无证据摘要。" }}</p>
        <div v-if="block.citations?.length" class="citation-list">
          <button
            v-for="citation in block.citations"
            :key="`${citation.segment_id || 'segment'}-${citation.start}-${citation.end}`"
            class="citation-item"
            @click="emit('seek', citation.start)"
          >
            <strong>{{ formatTimestamp(citation.start) }} - {{ formatTimestamp(citation.end) }}</strong>
            <span>{{ citation.text }}</span>
          </button>
        </div>
      </section>
    </div>

    <div v-else-if="citations.length" class="citation-list">
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

.answer-card__header,
.evidence-block__header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.answer-card__header {
  margin-bottom: 12px;
}

.label {
  margin: 0 0 6px;
  color: var(--text-soft);
  font-size: 0.74rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

h4,
.evidence-block__header strong {
  margin: 0;
  color: var(--text-strong);
  font-size: 1.06rem;
}

.answer-card__header span,
.evidence-block__header span {
  color: var(--text-soft);
  font-size: 0.82rem;
}

.topic-labels {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.topic-chip {
  padding: 5px 10px;
  border-radius: 999px;
  background: rgba(29, 78, 216, 0.08);
  color: var(--accent-strong);
  font-size: 0.8rem;
}

.answer-card__text,
.evidence-block__summary {
  margin: 0;
  color: var(--text-main);
  line-height: 1.82;
  white-space: pre-wrap;
}

.evidence-block-list,
.citation-list {
  display: grid;
  gap: 12px;
  margin-top: 14px;
}

.evidence-block {
  padding: 14px;
  border: 1px solid rgba(37, 99, 235, 0.12);
  border-radius: 18px;
  background: white;
}

.evidence-block__summary {
  margin-top: 10px;
}

.citation-item,
.jump-button {
  transition: transform 180ms ease, border-color 180ms ease, background 180ms ease;
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
}

.citation-item:hover,
.jump-button:hover {
  transform: translateY(-1px);
}

.citation-item strong {
  color: var(--accent-strong);
  font-size: 0.84rem;
}

.citation-item span {
  color: var(--text-main);
  line-height: 1.7;
}

.jump-button {
  min-height: 34px;
  padding: 0 12px;
  border: 1px solid rgba(37, 99, 235, 0.18);
  border-radius: 11px;
  background: rgba(243, 247, 255, 0.9);
  color: var(--accent-strong);
  cursor: pointer;
}
</style>
