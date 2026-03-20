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
  canDownloadNotes: {
    type: Boolean,
    required: true,
  },
  workLoading: {
    type: Object,
    required: true,
  },
});

const emit = defineEmits(["update:modelValue", "submit", "upload", "transcribe", "summary", "download"]);

function handleKeydown(event) {
  if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
    emit("submit");
  }
}
</script>

<template>
  <div class="composer-shell">
    <div class="composer-toolbar">
      <button class="toolbar-button" @click="emit('upload')">
        {{ workspace.fileName ? "更换音频" : "上传音频" }}
      </button>
      <button class="toolbar-button" :disabled="!workspace.fileName || workLoading.transcribe" @click="emit('transcribe')">
        {{ workLoading.transcribe ? "正在转录..." : "开始转录" }}
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
</template>

<style scoped>
.composer-shell {
  position: sticky;
  bottom: 0;
  z-index: 5;
  padding: 10px 22px 16px;
  border-top: 1px solid var(--line-soft);
  background: linear-gradient(180deg, rgba(253, 254, 255, 0.64), rgba(253, 254, 255, 0.96) 22%);
  backdrop-filter: blur(18px);
}

.composer-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  margin-bottom: 10px;
}

.toolbar-button {
  min-height: 32px;
  padding: 0 11px;
  border: 1px solid var(--line-soft);
  border-radius: 999px;
  background: var(--surface-base);
  color: var(--text-main);
  font-size: 0.84rem;
  font-weight: 700;
  cursor: pointer;
}

.toolbar-button:disabled {
  opacity: 0.48;
  cursor: not-allowed;
}

.toolbar-tip {
  color: var(--text-soft);
  font-size: 0.8rem;
}

.composer-box {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
  align-items: end;
  padding: 10px;
  border: 1px solid var(--line-soft);
  border-radius: 18px;
  background: white;
  box-shadow: 0 10px 32px rgba(15, 23, 42, 0.04);
}

.composer-input {
  width: 100%;
  min-height: 58px;
  resize: none;
  border: 0;
  outline: none;
  background: transparent;
  color: var(--text-main);
  font: inherit;
  line-height: 1.7;
}

.send-button {
  min-width: 82px;
  min-height: 40px;
  border: 0;
  border-radius: 14px;
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
