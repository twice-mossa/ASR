<script setup>
import AnswerCard from "./AnswerCard.vue";
import KeywordCard from "./KeywordCard.vue";
import ReasoningCard from "./ReasoningCard.vue";
import SummaryCard from "./SummaryCard.vue";
import TodoCard from "./TodoCard.vue";
import TranscriptCard from "./TranscriptCard.vue";

defineProps({
  messages: {
    type: Array,
    default: () => [],
  },
  workspace: {
    type: Object,
    required: true,
  },
  canGenerateSummary: {
    type: Boolean,
    required: true,
  },
  canAskQuestions: {
    type: Boolean,
    required: true,
  },
  canDownloadNotes: {
    type: Boolean,
    required: true,
  },
  workLoading: {
    type: Object,
    required: true,
  },
});

const emit = defineEmits(["action"]);

const welcomeCards = [
  {
    key: "upload",
    title: "上传会议录音",
    description: "把音频拖进工作台，后续所有分析会沉淀在同一条对话里。",
  },
  {
    key: "transcribe",
    title: "开始转录",
    description: "先得到可追溯的全文和分段时间戳，再决定如何生成摘要。",
  },
  {
    key: "summary",
    title: "生成结构化纪要",
    description: "把摘要、关键词和待办拆成更易读的成果卡片。",
  },
  {
    key: "prompt-todos",
    title: "继续追问会议",
    description: "围绕当前会议内容继续提问，并查看回答引用的原始片段。",
  },
];
</script>

<template>
  <section class="chat-workspace">
    <div v-if="!messages.length" class="welcome-panel">
      <div class="welcome-copy">
        <p class="welcome-label">Chat-style Meeting Copilot</p>
        <h3>上传音频，然后像和模型协作一样持续整理会议内容。</h3>
        <p>
          这里不再是零散的表单和结果卡，而是一条完整的工作对话。你可以先转录、再生成摘要，并在后续围绕当前音频继续提问。
        </p>
      </div>

      <div class="welcome-grid">
        <button v-for="card in welcomeCards" :key="card.key" class="welcome-card" @click="emit('action', card.key)">
          <strong>{{ card.title }}</strong>
          <span>{{ card.description }}</span>
        </button>
      </div>
    </div>

    <div v-else class="message-list">
      <article
        v-for="message in messages"
        :key="message.id"
        class="message-item"
        :class="[`message-item--${message.role}`, `message-item--${message.kind}`, { 'message-item--error': message.tone === 'error' }]"
      >
        <div class="message-avatar">
          <span v-if="message.role === 'assistant'">AI</span>
          <span v-else-if="message.role === 'user'">你</span>
          <span v-else>系统</span>
        </div>

        <div class="message-body">
          <p v-if="message.text" class="message-text">{{ message.text }}</p>

          <div v-if="message.kind === 'system_status' && message.progress" class="progress-meta">
            <span>{{ message.progressMeta?.status === "stopping" ? "正在停止" : "进度" }}</span>
            <strong>{{ message.progress.completed }} / {{ message.progress.total }}</strong>
            <div class="progress-bar">
              <span
                :style="{
                  width: `${Math.min(100, Math.max(0, ((message.progress.completed || 0) / Math.max(1, message.progress.total || 1)) * 100))}%`,
                }"
              />
            </div>
          </div>

          <TranscriptCard v-if="message.kind === 'transcript_result'" :transcript="message.transcript" />
          <SummaryCard
            v-if="message.kind === 'summary_result'"
            :summary="message.summary"
            :can-download-notes="canDownloadNotes"
            :summary-email="workspace.summaryEmail"
            :email-sending="workLoading.email"
            @ask="emit('action', 'prompt-risk')"
            @send-email="emit('action', 'send-summary-email')"
            @download="emit('action', 'download-notes')"
          />
          <KeywordCard v-if="message.kind === 'keyword_result'" :keywords="message.keywords" />
          <TodoCard v-if="message.kind === 'todo_result'" :todos="message.todos" @ask="emit('action', 'prompt-todos')" />
          <AnswerCard
            v-if="message.kind === 'qa_answer'"
            :answer="message.answer"
            :citations="message.citations || []"
            :answer-type="message.answerType || 'fact'"
            :topic-labels="message.topicLabels || []"
            :evidence-blocks="message.evidenceBlocks || []"
            @seek="emit('action', { type: 'seek-audio', seconds: $event })"
          />
          <ReasoningCard
            v-if="message.kind === 'reasoning' || (message.kind === 'qa_answer' && message.reasoningItems?.length)"
            :title="message.reasoningTitle || '查看回答依据'"
            :items="message.reasoningItems"
          />

          <div v-if="message.sources?.length" class="source-list">
            <div v-for="source in message.sources" :key="source" class="source-item">{{ source }}</div>
          </div>

          <div v-if="message.kind === 'transcript_result'" class="follow-up-actions">
            <button
              class="follow-up-button"
              :disabled="!canGenerateSummary || workLoading.summary"
              @click="emit('action', 'summary')"
            >
              生成摘要
            </button>
            <button class="follow-up-button follow-up-button--ghost" @click="emit('action', 'prompt-todos')">追问待办与负责人</button>
          </div>
        </div>
      </article>
    </div>
  </section>
</template>

<style scoped>
.chat-workspace {
  height: 100%;
  padding: 16px 0 10px;
  overflow-y: auto;
  overscroll-behavior: contain;
}

.welcome-panel {
  max-width: 920px;
  margin: 0 auto;
  min-height: 100%;
  display: grid;
  align-content: center;
  gap: 18px;
}

.welcome-copy {
  max-width: 760px;
}

.welcome-label {
  margin: 0 0 8px;
  color: var(--text-soft);
  font-size: 0.64rem;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}

h3 {
  max-width: 16ch;
  margin: 0;
  color: var(--text-strong);
  font-size: clamp(1.66rem, 3.6vw, 3rem);
  line-height: 0.96;
  letter-spacing: -0.06em;
}

.welcome-copy p:last-child {
  max-width: 64ch;
  margin: 8px 0 0;
  color: var(--text-soft);
  line-height: 1.65;
}

.welcome-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.welcome-card {
  padding: 12px 14px 14px;
  border: 1px solid var(--line-soft);
  border-radius: 14px;
  background: var(--surface-base);
  text-align: left;
  cursor: pointer;
  transition: transform 180ms ease, border-color 180ms ease, background 180ms ease;
}

.welcome-card:hover {
  transform: translateY(-1px);
  border-color: var(--line-strong);
  background: white;
}

.welcome-card strong {
  display: block;
  color: var(--text-strong);
  font-size: 0.9rem;
}

.welcome-card span {
  display: block;
  margin-top: 7px;
  color: var(--text-soft);
  line-height: 1.6;
}

.message-list {
  max-width: 920px;
  margin: 0 auto;
  display: grid;
  gap: 14px;
  padding-bottom: 8px;
}

.message-item {
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr);
  gap: 10px;
}

.message-avatar {
  width: 32px;
  height: 32px;
  display: grid;
  place-items: center;
  border-radius: 10px;
  background: var(--surface-raised);
  color: var(--text-main);
  font-size: 0.68rem;
  font-weight: 700;
}

.message-item--assistant .message-avatar {
  background: linear-gradient(145deg, #163885, #0d2458);
  color: white;
}

.message-item--user .message-avatar {
  background: #0f172a;
  color: white;
}

.message-item--system .message-avatar {
  background: #e9f0ff;
  color: #2449b8;
}

.message-body {
  min-width: 0;
  padding-top: 1px;
}

.message-text {
  margin: 0;
  color: var(--text-main);
  line-height: 1.72;
}

.message-item--user .message-body {
  padding: 11px 13px;
  border-radius: 16px;
  background: #111827;
}

.message-item--user .message-text {
  color: rgba(255, 255, 255, 0.94);
}

.message-item--system .message-body,
.message-item--error .message-body {
  padding: 11px 13px;
  border: 1px solid var(--line-soft);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.7);
}

.message-item--error .message-body {
  border-color: rgba(185, 28, 28, 0.16);
  background: rgba(254, 242, 242, 0.86);
}

.progress-meta,
.follow-up-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-top: 10px;
}

.progress-meta span {
  color: var(--text-soft);
  font-size: 0.86rem;
}

.progress-meta strong {
  color: var(--text-strong);
}

.progress-bar {
  width: min(220px, 100%);
  height: 6px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.16);
}

.progress-bar span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #1f4fd1, #60a5fa);
}

.follow-up-button {
  min-height: 34px;
  padding: 0 12px;
  border: 0;
  border-radius: 11px;
  background: var(--accent);
  color: white;
  font-weight: 700;
  cursor: pointer;
}

.follow-up-button--ghost {
  border: 1px solid var(--line-soft);
  background: rgba(255, 255, 255, 0.82);
  color: var(--text-main);
}

.follow-up-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.source-list {
  display: grid;
  gap: 8px;
  margin-top: 14px;
}

.source-item {
  padding: 11px 12px;
  border-left: 3px solid rgba(37, 99, 235, 0.3);
  border-radius: 0 12px 12px 0;
  background: rgba(243, 247, 255, 0.9);
  color: var(--text-soft);
  line-height: 1.7;
}

@media (max-width: 900px) {
  .welcome-panel {
    min-height: 100%;
    align-content: start;
    padding-top: 12px;
  }

  .welcome-grid {
    grid-template-columns: 1fr;
  }
}
</style>
