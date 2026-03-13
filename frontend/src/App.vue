<script setup>
import { Loading } from "@element-plus/icons-vue";
import { ElNotification } from "element-plus";
import { computed, onBeforeUnmount, onMounted, reactive, ref } from "vue";

import { fetchCurrentUser, loginUser, logoutUser, registerUser } from "./api/auth";
import { summarizeMeeting, transcribeMeeting } from "./api/meeting";
import AuthPanel from "./components/AuthPanel.vue";
import PageHero from "./components/PageHero.vue";

function safeParse(raw) {
  if (!raw) {
    return null;
  }

  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

const activeTab = ref("login");
const authLoading = ref(false);
const workLoading = reactive({
  transcribe: false,
  summary: false,
});
const session = reactive({
  token: localStorage.getItem("auth_token") || "",
  user: safeParse(localStorage.getItem("auth_user")),
});
const loginForm = reactive({
  identifier: "",
  password: "",
});
const registerForm = reactive({
  username: "",
  email: "",
  password: "",
  confirmPassword: "",
});
const workspace = reactive({
  file: null,
  fileName: "",
  audioUrl: "",
  transcript: null,
  summary: null,
  isDragging: false,
});

const heroHighlights = [
  {
    title: "上传后立即进入处理",
    description: "登录完成后就能直接把一段会议录音交给工作区，不需要额外切页。",
  },
  {
    title: "保留分段时间戳",
    description: "转写结果按时间组织，后面做检索、跳转和回放会更自然。",
  },
  {
    title: "把重点沉淀成纪要",
    description: "在原始转写之上提炼摘要、关键词和待办，不用再手动摘录第二遍。",
  },
];

const heroNotes = [
  "先登录，再进入会议工作台。",
  "上传一段音频后，先看转写，再生成纪要。",
  "整个界面只保留与会议整理直接相关的内容。",
];

const heroMetrics = [
  { value: "01", label: "登录后直接开始" },
  { value: "02", label: "转写与摘要同屏" },
  { value: "03", label: "围绕会议内容展开" },
];

const isAuthenticated = computed(() => Boolean(session.token && session.user));
const canGenerateSummary = computed(() => Boolean(workspace.transcript?.text));
const canPreviewAudio = computed(() => Boolean(workspace.audioUrl));

function notify(message, type = "success", title = "通知") {
  ElNotification({
    title,
    message,
    type,
    position: "top-right",
    duration: type === "error" ? 5000 : 3000,
  });
}

function persistSession(payload) {
  session.token = payload.token;
  session.user = payload.user;
  localStorage.setItem("auth_token", payload.token);
  localStorage.setItem("auth_user", JSON.stringify(payload.user));
}

function clearSession() {
  session.token = "";
  session.user = null;
  localStorage.removeItem("auth_token");
  localStorage.removeItem("auth_user");
}

function resolveError(error, fallback) {
  return error?.response?.data?.detail || fallback;
}

function resetWorkspace() {
  revokeAudioUrl();
  workspace.file = null;
  workspace.fileName = "";
  workspace.audioUrl = "";
  workspace.transcript = null;
  workspace.summary = null;
  workspace.isDragging = false;
}

function revokeAudioUrl() {
  if (workspace.audioUrl) {
    URL.revokeObjectURL(workspace.audioUrl);
  }
}

function applySelectedFile(file) {
  revokeAudioUrl();
  workspace.file = file || null;
  workspace.fileName = file?.name || "";
  workspace.audioUrl = file ? URL.createObjectURL(file) : "";
  workspace.transcript = null;
  workspace.summary = null;
  workspace.isDragging = false;
}

function isSupportedAudio(file) {
  if (!file) {
    return false;
  }

  const lowerName = file.name.toLowerCase();
  return [".wav", ".mp3", ".m4a", ".flac"].some((ext) => lowerName.endsWith(ext));
}

function handleFileSelect(event) {
  const [file] = event.target.files || [];
  if (file && !isSupportedAudio(file)) {
    notify("仅支持 wav、mp3、m4a、flac 音频文件", "warning", "文件类型不支持");
    return;
  }
  applySelectedFile(file || null);
}

function handleDragOver(event) {
  event.preventDefault();
  workspace.isDragging = true;
}

function handleDragLeave(event) {
  if (event.currentTarget.contains(event.relatedTarget)) {
    return;
  }
  workspace.isDragging = false;
}

function handleDrop(event) {
  event.preventDefault();
  workspace.isDragging = false;

  const [file] = event.dataTransfer?.files || [];
  if (!file) {
    return;
  }

  if (!isSupportedAudio(file)) {
    notify("仅支持 wav、mp3、m4a、flac 音频文件", "warning", "文件类型不支持");
    return;
  }

  applySelectedFile(file);
}

async function handleRegister() {
  if (registerForm.password !== registerForm.confirmPassword) {
    notify("两次输入的密码不一致", "error", "注册失败");
    return;
  }

  authLoading.value = true;
  try {
    const payload = await registerUser({
      username: registerForm.username.trim(),
      email: registerForm.email.trim(),
      password: registerForm.password,
    });
    persistSession(payload);
    notify("注册成功，已自动登录", "success", "注册成功");
    registerForm.username = "";
    registerForm.email = "";
    registerForm.password = "";
    registerForm.confirmPassword = "";
  } catch (error) {
    notify(resolveError(error, "注册失败，请稍后再试"), "error", "注册失败");
  } finally {
    authLoading.value = false;
  }
}

async function handleLogin() {
  authLoading.value = true;
  try {
    const payload = await loginUser({
      identifier: loginForm.identifier.trim(),
      password: loginForm.password,
    });
    persistSession(payload);
    notify("登录成功", "success", "登录成功");
    loginForm.identifier = "";
    loginForm.password = "";
  } catch (error) {
    notify(resolveError(error, "登录失败，请稍后再试"), "error", "登录失败");
  } finally {
    authLoading.value = false;
  }
}

async function handleLogout() {
  authLoading.value = true;
  try {
    await logoutUser(session.token);
  } catch {
    // Ignore logout failures and clear local state anyway.
  } finally {
    clearSession();
    resetWorkspace();
    authLoading.value = false;
    notify("已退出登录", "success", "退出成功");
  }
}

async function handleTranscribe() {
  if (!workspace.file) {
    notify("请先选择音频文件", "warning", "缺少文件");
    return;
  }

  workLoading.transcribe = true;
  workspace.transcript = null;
  workspace.summary = null;
  notify("已开始转写。长音频可能需要几分钟，请等待结果返回。", "info", "开始转写");

  try {
    workspace.transcript = await transcribeMeeting(workspace.file);
    notify("音频转写完成", "success", "转写完成");
  } catch (error) {
    notify(
      resolveError(error, "转写失败。若音频较长，请先确认后端仍在运行并等待更久。"),
      "error",
      "转写失败",
    );
  } finally {
    workLoading.transcribe = false;
  }
}

async function handleSummary() {
  if (!workspace.transcript?.text) {
    notify("请先完成音频转写", "warning", "无法生成纪要");
    return;
  }

  workLoading.summary = true;
  try {
    workspace.summary = await summarizeMeeting(workspace.transcript.text);
    notify("会议纪要生成完成", "success", "生成完成");
  } catch (error) {
    notify(resolveError(error, "摘要生成失败，请检查 API 配置"), "error", "摘要失败");
  } finally {
    workLoading.summary = false;
  }
}

onMounted(async () => {
  if (!session.token) {
    return;
  }

  try {
    session.user = await fetchCurrentUser(session.token);
    localStorage.setItem("auth_user", JSON.stringify(session.user));
  } catch {
    clearSession();
  }
});

onBeforeUnmount(() => {
  revokeAudioUrl();
});
</script>

<template>
  <main class="page-shell">
    <PageHero
      eyebrow="ASR Meeting Assistant"
      title="把会议录音整理成真正可用的内容"
      intro="这不是一个展示型页面，而是一个真正用于整理会议信息的工作入口。上传录音、生成转写，再把重点、关键词和待办沉淀下来，整个过程尽量保持清晰、顺手、不过度打扰。"
      :highlights="heroHighlights"
      :notes="heroNotes"
      :metrics="heroMetrics"
    />

    <section class="auth-section">
      <AuthPanel
        v-model:active-tab="activeTab"
        :loading="authLoading"
        :is-authenticated="isAuthenticated"
        :session="session"
        :login-form="loginForm"
        :register-form="registerForm"
        guest-label="账号中心"
        guest-title="进入会议工作区"
        guest-pill="Account"
        authed-label="当前账号"
        authed-pill="Ready"
        @login="handleLogin"
        @register="handleRegister"
        @logout="handleLogout"
      />
    </section>

    <section class="card-grid workspace-grid" v-if="isAuthenticated">
      <article class="card workspace-card">
        <div v-if="workLoading.transcribe" class="processing-overlay" aria-live="polite">
          <div class="processing-panel">
            <el-icon class="processing-icon is-loading"><Loading /></el-icon>
            <h3>正在转写音频</h3>
            <p>长音频可能需要几分钟。请不要刷新页面，也不要重复提交同一个文件。</p>
          </div>
        </div>

        <div class="card-header">
          <div>
            <p class="card-label">Transcript</p>
            <h2>上传音频并开始处理</h2>
          </div>
          <span class="pill">Core Flow</span>
        </div>

        <label
          class="file-picker"
          :class="{ 'file-picker--dragging': workspace.isDragging }"
          @dragover="handleDragOver"
          @dragleave="handleDragLeave"
          @drop="handleDrop"
        >
          <span>选择会议音频文件</span>
          <small>也可以直接把音频文件从文件夹拖到这里</small>
          <input type="file" accept=".wav,.mp3,.m4a,.flac" @change="handleFileSelect" />
        </label>

        <p class="file-name" v-if="workspace.fileName">当前文件：{{ workspace.fileName }}</p>
        <p class="helper-text" v-else>优先上传一段较短的会议片段，会更适合先验证转写和摘要体验。</p>

        <div v-if="canPreviewAudio" class="audio-preview">
          <div class="audio-preview__header">
            <span>音频预览</span>
            <small>先听一遍确认上传内容是否正确</small>
          </div>
          <audio :src="workspace.audioUrl" controls preload="metadata" class="audio-player" />
        </div>

        <div class="action-row">
          <el-button type="primary" :loading="workLoading.transcribe" @click="handleTranscribe">
            1. 开始转写
          </el-button>
          <el-button
            type="success"
            :disabled="!canGenerateSummary"
            :loading="workLoading.summary"
            @click="handleSummary"
          >
            2. 生成纪要
          </el-button>
          <el-button plain @click="resetWorkspace">重置</el-button>
        </div>

        <div class="result-block">
          <div class="result-header">
            <h3>转写结果</h3>
            <span v-if="workspace.transcript">语言：{{ workspace.transcript.language || "zh" }}</span>
          </div>

          <el-empty v-if="!workspace.transcript" description="完成转写后会在这里显示结果" />

          <template v-else>
            <el-input :model-value="workspace.transcript.text" type="textarea" :rows="8" readonly />

            <div class="segment-list">
              <div
                v-for="segment in workspace.transcript.segments"
                :key="`${segment.start}-${segment.end}`"
                class="segment-item"
              >
                <span class="segment-time">
                  {{ segment.start.toFixed(1) }}s - {{ segment.end.toFixed(1) }}s
                </span>
                <span>{{ segment.text }}</span>
              </div>
            </div>
          </template>
        </div>
      </article>

      <article class="card summary-card">
        <div class="card-header">
          <div>
            <p class="card-label">Summary</p>
            <h2>摘要、关键词与待办事项</h2>
          </div>
          <span class="pill success">AI Output</span>
        </div>

        <el-empty v-if="!workspace.summary" description="生成纪要后会在这里展示内容" />

        <template v-else>
          <div class="summary-section">
            <h3>会议摘要</h3>
            <p>{{ workspace.summary.summary }}</p>
          </div>

          <div class="summary-section">
            <h3>关键词</h3>
            <div class="tag-list">
              <el-tag v-for="keyword in workspace.summary.keywords" :key="keyword" type="warning" effect="light">
                {{ keyword }}
              </el-tag>
            </div>
          </div>

          <div class="summary-section">
            <h3>待办事项</h3>
            <ul class="todo-list">
              <li v-for="todo in workspace.summary.todos" :key="todo">{{ todo }}</li>
            </ul>
          </div>
        </template>
      </article>
    </section>
  </main>
</template>

<style scoped>
@import url("https://fonts.googleapis.com/css2?family=Calistoga&display=swap");

:global(body) {
  margin: 0;
  font-family: "Avenir Next", "PingFang SC", "Hiragino Sans GB", sans-serif;
  background-color: #f8fafc;
  background:
    radial-gradient(circle at top left, rgba(249, 115, 22, 0.16) 0%, transparent 24%),
    radial-gradient(circle at top right, rgba(37, 99, 235, 0.16) 0%, transparent 28%),
    linear-gradient(180deg, #fffdf9 0%, #f8fafc 45%, #f1f5f9 100%);
  color: #1f2b3a;
}

:global(*) {
  box-sizing: border-box;
}

.page-shell {
  min-height: 100vh;
  padding: 48px 20px 84px;
}

.page-shell::before {
  content: "";
  position: fixed;
  inset: 0;
  background:
    linear-gradient(rgba(15, 23, 42, 0.015) 1px, transparent 1px),
    linear-gradient(90deg, rgba(15, 23, 42, 0.015) 1px, transparent 1px);
  background-size: 32px 32px;
  mask-image: linear-gradient(180deg, rgba(0, 0, 0, 0.34), transparent 76%);
  pointer-events: none;
}

.auth-section {
  max-width: 920px;
  margin: 0 auto 34px;
}

.card-grid {
  max-width: 1200px;
  margin: 0 auto;
  display: grid;
  gap: 24px;
}

.workspace-grid {
  grid-template-columns: minmax(0, 1.16fr) minmax(320px, 0.84fr);
}

.card,
.workspace-card,
.summary-card {
  position: relative;
  padding: 30px;
  border: 1px solid rgba(37, 99, 235, 0.08);
  border-radius: 34px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.92), rgba(245, 248, 252, 0.8)),
    rgba(255, 255, 255, 0.84);
  box-shadow: 0 28px 64px rgba(15, 23, 42, 0.1);
  backdrop-filter: blur(16px);
}

.processing-overlay {
  position: absolute;
  inset: 0;
  z-index: 4;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  border-radius: 34px;
  background: rgba(248, 250, 252, 0.86);
  backdrop-filter: blur(8px);
}

.processing-panel {
  width: min(420px, 100%);
  padding: 28px 24px;
  border: 1px solid rgba(37, 99, 235, 0.14);
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 22px 50px rgba(15, 23, 42, 0.14);
  text-align: center;
}

.processing-icon {
  margin-bottom: 14px;
  font-size: 2rem;
  color: #2563eb;
}

.processing-panel h3 {
  margin-bottom: 10px;
}

.processing-panel p {
  margin: 0;
  color: #64748b;
  line-height: 1.8;
}

.card-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 16px;
}

.card-label {
  margin: 0 0 10px;
  color: #64748b;
  font-size: 0.82rem;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}

h2,
h3 {
  margin: 0;
  font-family: "Calistoga", "Iowan Old Style", "Palatino Linotype", serif;
  letter-spacing: -0.03em;
}

.pill {
  display: inline-flex;
  align-items: center;
  padding: 10px 14px;
  border-radius: 999px;
  background: rgba(37, 99, 235, 0.12);
  color: #2563eb;
  font-size: 0.8rem;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.pill.success {
  background: rgba(249, 115, 22, 0.14);
  color: #c2410c;
}

.todo-list {
  margin: 0;
  padding-left: 20px;
  line-height: 1.9;
}

.file-picker {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 20px;
  border: 1px dashed rgba(37, 99, 235, 0.26);
  border-radius: 24px;
  background: linear-gradient(180deg, rgba(239, 246, 255, 0.95), rgba(255, 255, 255, 0.88));
  color: #1d4ed8;
  font-weight: 700;
  transition: border-color 180ms ease, transform 180ms ease, box-shadow 180ms ease;
}

.file-picker input {
  font-weight: 400;
}

.file-picker small {
  color: #64748b;
  font-weight: 500;
}

.file-picker--dragging {
  border-color: rgba(14, 165, 233, 0.8);
  box-shadow: 0 0 0 4px rgba(14, 165, 233, 0.12);
  transform: translateY(-1px);
}

.file-name,
.helper-text {
  margin: 14px 0 0;
  color: #5b6d7f;
  line-height: 1.8;
}

.audio-preview {
  margin-top: 18px;
  padding: 16px 18px;
  border: 1px solid rgba(37, 99, 235, 0.08);
  border-radius: 20px;
  background: rgba(248, 250, 252, 0.92);
}

.audio-preview__header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: baseline;
  margin-bottom: 10px;
  color: #334155;
  font-weight: 700;
}

.audio-preview__header small {
  color: #64748b;
  font-weight: 500;
}

.audio-player {
  width: 100%;
}

.action-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 18px;
}

.result-block {
  margin-top: 24px;
}

.result-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  margin-bottom: 12px;
}

.segment-list {
  margin-top: 14px;
  max-height: 280px;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.segment-item {
  display: grid;
  gap: 6px;
  padding: 14px;
  border-radius: 18px;
  background: rgba(248, 250, 252, 0.9);
  border: 1px solid rgba(37, 99, 235, 0.06);
}

.segment-time {
  color: #2563eb;
  font-size: 0.88rem;
  font-weight: 700;
}

.summary-section + .summary-section {
  margin-top: 22px;
}

.summary-section p {
  margin: 10px 0 0;
  line-height: 1.8;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 12px;
}

:deep(.el-tag) {
  padding: 0 14px;
  border-radius: 999px;
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation: none !important;
    transition: none !important;
    scroll-behavior: auto !important;
  }
}

@media (max-width: 980px) {
  .workspace-grid {
    grid-template-columns: 1fr;
  }
}
</style>
