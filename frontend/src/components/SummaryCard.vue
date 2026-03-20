<script setup>
import { computed } from "vue";

import { formatExportDate } from "../utils/workspace";

const props = defineProps({
  summary: {
    type: String,
    default: "",
  },
  canDownloadNotes: {
    type: Boolean,
    required: true,
  },
  summaryEmail: {
    type: Object,
    required: true,
  },
  emailSending: {
    type: Boolean,
    required: true,
  },
});

const emit = defineEmits(["ask", "download", "send-email"]);

const emailStatusText = computed(() => {
  if (!props.summaryEmail.enabled) {
    return "邮件发送未启用";
  }

  if (props.summaryEmail.last_status === "sent") {
    const sentAt = props.summaryEmail.last_sent_at ? formatExportDate(props.summaryEmail.last_sent_at) : "";
    return `已发送到 ${props.summaryEmail.recipient_email}${sentAt ? ` · ${sentAt}` : ""}`;
  }

  if (props.summaryEmail.last_status === "failed") {
    return props.summaryEmail.last_error ? `发送失败：${props.summaryEmail.last_error}` : "发送失败";
  }

  return "未发送到邮箱";
});
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
        <button
          class="inline-action inline-action--ghost"
          :disabled="!summaryEmail.enabled || emailSending"
          @click="emit('send-email')"
        >
          {{ emailSending ? "发送中..." : summaryEmail.last_status === "failed" ? "重新发送到邮箱" : "发送到邮箱" }}
        </button>
        <button class="inline-action" :disabled="!canDownloadNotes" @click="emit('download')">下载会议纪要</button>
      </div>
    </div>
    <p class="email-status" :class="`email-status--${summaryEmail.last_status || 'idle'}`">{{ emailStatusText }}</p>
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

.email-status {
  margin: 0 0 10px;
  color: var(--text-soft);
  font-size: 0.8rem;
}

.email-status--sent {
  color: #0f766e;
}

.email-status--failed {
  color: #b91c1c;
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
