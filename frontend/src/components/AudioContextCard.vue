<script setup>
defineProps({
  workspace: {
    type: Object,
    required: true,
  },
  statusLabel: {
    type: String,
    required: true,
  },
});

const emit = defineEmits(["upload"]);
</script>

<template>
  <section class="context-card">
    <div class="context-header">
      <span>当前上下文</span>
      <small>{{ statusLabel }}</small>
    </div>

    <template v-if="workspace.fileName">
      <strong>{{ workspace.fileName }}</strong>
      <ul class="meta-list">
        <li>音频时长：{{ workspace.durationLabel }}</li>
        <li>语言：{{ workspace.language || "zh" }}</li>
        <li>分段数量：{{ workspace.transcript?.segments?.length || 0 }}</li>
      </ul>
    </template>

    <template v-else>
      <strong>还没有活跃音频</strong>
      <p>上传会议录音后，摘要、关键词、待办和后续问答都会围绕同一条上下文展开。</p>
    </template>

    <button class="upload-link" @click="emit('upload')">
      {{ workspace.fileName ? "更换当前音频" : "上传第一段音频" }}
    </button>
  </section>
</template>

<style scoped>
.context-card {
  padding: 16px;
  border: 1px solid var(--line-soft);
  border-radius: 18px;
  background: linear-gradient(180deg, rgba(248, 250, 252, 0.98), rgba(242, 246, 250, 0.98));
}

.context-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  margin-bottom: 12px;
  color: var(--text-soft);
  font-size: 0.76rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

strong {
  display: block;
  color: var(--text-strong);
  font-size: 1rem;
  line-height: 1.5;
}

p,
.meta-list {
  margin: 10px 0 0;
  color: var(--text-soft);
  line-height: 1.7;
}

.meta-list {
  padding-left: 18px;
}

.upload-link {
  width: 100%;
  min-height: 40px;
  margin-top: 14px;
  border: 1px dashed var(--line-strong);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.7);
  color: var(--accent-strong);
  font-weight: 700;
  cursor: pointer;
}
</style>
