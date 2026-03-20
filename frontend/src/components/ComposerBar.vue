<script setup>
defineProps({
  modelValue: {
    type: String,
    required: true,
  },
  authenticated: {
    type: Boolean,
    required: true,
  },
  workspace: {
    type: Object,
    required: true,
  },
  placeholder: {
    type: String,
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
  canStopTranscription: {
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

const emit = defineEmits(["update:modelValue", "submit", "upload", "transcribe", "stop-transcribe", "summary", "download"]);

function handleKeydown(event) {
  if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
    emit("submit");
  }
}
</script>

<template>
  <div class="composer-shell">
    <div class="composer-frame">
      <div class="composer-toolbar">
        <button class="toolbar-button" @click="emit('upload')">
          {{ workspace.fileName ? "更换音频" : "上传音频" }}
        </button>
        <button class="toolbar-button" :disabled="!workspace.fileName || workLoading.transcribe" @click="emit('transcribe')">
          {{ workspace.transcriptionStatus === "stopped" ? "重新转录" : workLoading.transcribe ? "正在转录..." : "开始转录" }}
        </button>
        <button
          v-if="canStopTranscription"
          class="toolbar-button toolbar-button--danger"
          :disabled="workspace.transcriptionStatus === 'stopping' || workLoading.stopTranscribe"
          @click="emit('stop-transcribe')"
        >
          {{ workspace.transcriptionStatus === "stopping" || workLoading.stopTranscribe ? "正在停止..." : "停止转录" }}
        </button>
        <button class="toolbar-button" :disabled="!canGenerateSummary || workLoading.summary" @click="emit('summary')">
          {{ workLoading.summary ? "正在生成..." : "生成摘要" }}
        </button>
        <button class="toolbar-button" :disabled="!canDownloadNotes" @click="emit('download')">下载纪要</button>
        <span class="toolbar-tip">{{ authenticated ? "Cmd/Ctrl + Enter 发送" : "关键动作会在使用时提示登录" }}</span>
      </div>

      <div class="composer-box">
        <textarea
          :value="modelValue"
          class="composer-input"
          :placeholder="placeholder"
          rows="1"
          @input="emit('update:modelValue', $event.target.value)"
          @keydown="handleKeydown"
        />
        <button class="send-button" @click="emit('submit')">发送</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.composer-shell {
  position: sticky;
  bottom: 0;
  z-index: 5;
  padding: 8px 18px 12px;
  border-top: 1px solid var(--line-soft);
  background: linear-gradient(180deg, rgba(253, 254, 255, 0.54), rgba(253, 254, 255, 0.94) 20%);
  backdrop-filter: blur(16px);
}

.composer-frame {
  max-width: 920px;
  margin: 0 auto;
}

.composer-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}

.toolbar-button {
  min-height: 30px;
  padding: 0 10px;
  border: 1px solid var(--line-soft);
  border-radius: 999px;
  background: var(--surface-base);
  color: var(--text-main);
  font-size: 0.78rem;
  font-weight: 700;
  cursor: pointer;
}

.toolbar-button:disabled {
  opacity: 0.48;
  cursor: not-allowed;
}

.toolbar-button--danger {
  border-color: rgba(185, 28, 28, 0.18);
  background: rgba(254, 242, 242, 0.9);
  color: #b91c1c;
}

.toolbar-tip {
  color: var(--text-soft);
  font-size: 0.74rem;
}

.composer-box {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px;
  align-items: end;
  padding: 9px;
  border: 1px solid var(--line-soft);
  border-radius: 16px;
  background: white;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.035);
}

.composer-input {
  width: 100%;
  min-height: 50px;
  resize: none;
  border: 0;
  outline: none;
  background: transparent;
  color: var(--text-main);
  font: inherit;
  line-height: 1.6;
}

.send-button {
  min-width: 74px;
  min-height: 36px;
  border: 0;
  border-radius: 12px;
  background: #0f172a;
  color: white;
  font-weight: 700;
  cursor: pointer;
}

@media (max-width: 980px) {
  .composer-shell {
    padding: 10px 12px 14px;
  }

  .composer-box {
    grid-template-columns: 1fr;
  }
}
</style>
