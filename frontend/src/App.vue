<script setup>
import { Loading } from "@element-plus/icons-vue";
import { ElNotification } from "element-plus";
import { computed, onBeforeUnmount, onMounted, reactive, ref } from "vue";

import { fetchCurrentUser, loginUser, logoutUser, registerUser } from "./api/auth";
import { analyzeWithAgent, getTranscriptionJob, startTranscriptionJob, summarizeMeeting } from "./api/meeting";
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
const activeTranscriptionJobId = ref("");
const workLoading = reactive({
  transcribe: false,
  summary: false,
  agent: false,
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
  agentReport: null,
  isDragging: false,
  transcriptionStatus: "idle",
  completedChunks: 0,
  totalChunks: 1,
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
const canGenerateSummary = computed(() => Boolean(workspace.transcript?.text) && !workLoading.transcribe);
const canRunAgent = computed(() => Boolean(workspace.transcript?.text) && !workLoading.transcribe && !workLoading.agent);
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
  return error?.response?.data?.detail || error?.message || fallback;
}

function resetWorkspace() {
  revokeAudioUrl();
  activeTranscriptionJobId.value = "";
  workspace.file = null;
  workspace.fileName = "";
  workspace.audioUrl = "";
  workspace.transcript = null;
  workspace.summary = null;
  workspace.agentReport = null;
  workspace.isDragging = false;
  workspace.transcriptionStatus = "idle";
  workspace.completedChunks = 0;
  workspace.totalChunks = 1;
}

function revokeAudioUrl() {
  if (workspace.audioUrl) {
    URL.revokeObjectURL(workspace.audioUrl);
  }
}

function applySelectedFile(file) {
  revokeAudioUrl();
  activeTranscriptionJobId.value = "";
  workspace.file = file || null;
  workspace.fileName = file?.name || "";
  workspace.audioUrl = file ? URL.createObjectURL(file) : "";
  workspace.transcript = null;
  workspace.summary = null;
  workspace.isDragging = false;
  workspace.transcriptionStatus = "idle";
  workspace.completedChunks = 0;
  workspace.totalChunks = 1;
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
  workspace.transcript = {
    filename: workspace.fileName,
    language: "zh",
    text: "",
    segments: [],
  };
  workspace.summary = null;
  workspace.transcriptionStatus = "queued";
  workspace.completedChunks = 0;
  workspace.totalChunks = 1;
  notify("已开始转写。长音频可能需要几分钟，请等待结果返回。", "info", "开始转写");

  try {
    const job = await startTranscriptionJob(workspace.file);
    activeTranscriptionJobId.value = job.job_id;
    await pollTranscriptionJob(job.job_id);
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

function applyTranscriptionStatus(status) {
  workspace.transcriptionStatus = status.status || "processing";
  workspace.completedChunks = status.completed_chunks || 0;
  workspace.totalChunks = status.total_chunks || 1;
  workspace.transcript = {
    filename: status.filename || workspace.fileName,
    language: status.language || "zh",
    text: status.text || "",
    segments: status.segments || [],
  };
}

async function pollTranscriptionJob(jobId) {
  while (activeTranscriptionJobId.value === jobId) {
    const status = await getTranscriptionJob(jobId);
    applyTranscriptionStatus(status);

    if (status.status === "completed") {
      return;
    }

    if (status.status === "failed") {
      throw new Error(status.error || "转写失败");
    }

    await new Promise((resolve) => window.setTimeout(resolve, 1500));
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

async function handleAgentAnalyze() {
  if (!workspace.transcript?.text) {
    notify("请先完成音频转写", "warning", "无法运行 Agent 分析");
    return;
  }

  workLoading.agent = true;
  workspace.agentReport = null;
  notify("Agent 正在多步分析会议内容，请稍候…", "info", "Agent 分析中");
  try {
    workspace.agentReport = await analyzeWithAgent(workspace.transcript.text);
    notify("Agent 深度分析完成", "success", "分析完成");
  } catch (error) {
    notify(resolveError(error, "Agent 分析失败，请检查 API 配置"), "error", "Agent 失败");
  } finally {
    workLoading.agent = false;
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

        <div v-if="workLoading.transcribe" class="processing-banner" aria-live="polite">
          <el-icon class="processing-icon is-loading"><Loading /></el-icon>
          <div class="processing-copy">
            <h3>正在转写音频</h3>
            <p v-if="workspace.totalChunks > 1">
              已完成 {{ workspace.completedChunks }} / {{ workspace.totalChunks }} 段，结果会按语音时间顺序持续追加到下方。
            </p>
            <p v-else>长音频可能需要几分钟。你可以继续播放或暂停当前音频，但不要重复提交同一个文件。</p>
          </div>
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
          <el-button
            type="warning"
            :disabled="!canRunAgent"
            :loading="workLoading.agent"
            @click="handleAgentAnalyze"
          >
            3. Agent 深度分析
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

      <article class="card agent-card" v-if="workspace.agentReport || workLoading.agent">
        <div class="card-header">
          <div>
            <p class="card-label">Agent Report</p>
            <h2>深度会议分析报告</h2>
          </div>
          <span class="pill agent">Agent</span>
        </div>

        <div v-if="workLoading.agent" class="processing-banner" aria-live="polite">
          <el-icon class="processing-icon is-loading"><Loading /></el-icon>
          <div class="processing-copy">
            <h3>Agent 正在多步分析</h3>
            <p>Agent 依次调用摘要、决策、行动项、关键词工具，完成后汇总报告。</p>
          </div>
        </div>

        <template v-else-if="workspace.agentReport">
          <div class="summary-section">
            <h3>会议摘要</h3>
            <p>{{ workspace.agentReport.summary }}</p>
          </div>

          <div class="summary-section" v-if="workspace.agentReport.key_decisions?.length">
            <h3>关键决策</h3>
            <ul class="todo-list">
              <li v-for="decision in workspace.agentReport.key_decisions" :key="decision">
                {{ decision }}
              </li>
            </ul>
          </div>

          <div class="summary-section" v-if="workspace.agentReport.action_items?.length">
            <h3>行动项</h3>
            <div class="action-item-list">
              <div
                v-for="item in workspace.agentReport.action_items"
                :key="item.task"
                class="action-item"
              >
                <span class="action-task">{{ item.task }}</span>
                <div class="action-meta">
                  <el-tag v-if="item.owner" size="small" type="info" effect="plain">
                    👤 {{ item.owner }}
                  </el-tag>
                  <el-tag v-if="item.deadline" size="small" type="danger" effect="plain">
                    📅 {{ item.deadline }}
                  </el-tag>
                </div>
              </div>
            </div>
          </div>

          <div class="summary-section" v-if="workspace.agentReport.keywords?.length">
            <h3>关键词</h3>
            <div class="tag-list">
              <el-tag
                v-for="keyword in workspace.agentReport.keywords"
                :key="keyword"
                type="warning"
                effect="light"
              >
                {{ keyword }}
              </el-tag>
            </div>
          </div>

          <div class="summary-section" v-if="workspace.agentReport.overall_assessment">
            <h3>整体评估</h3>
            <p class="assessment-text">{{ workspace.agentReport.overall_assessment }}</p>
          </div>
        </template>
      </article>
    </section>
  </main>
</template>

<style scoped>
@import url("https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap");

:global(body) {
  margin: 0;
  font-family: "Inter", "SF Pro Display", "Avenir Next", "PingFang SC", "Hiragino Sans GB", sans-serif;
  background:
    radial-gradient(circle at 14% 10%, rgba(191, 219, 254, 0.72), transparent 20%),
    radial-gradient(circle at 86% 4%, rgba(255, 255, 255, 0.96), transparent 24%),
    linear-gradient(180deg, #fbfbfd 0%, #f5f7fb 42%, #eef2f7 100%);
  color: #1f2b3a;
}

:global(*) {
  box-sizing: border-box;
}

.page-shell {
  min-height: 100vh;
  padding: 52px 22px 88px;
}

.page-shell::before {
  content: "";
  position: fixed;
  inset: 0;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.62), rgba(255, 255, 255, 0));
  mask-image: linear-gradient(180deg, rgba(0, 0, 0, 0.44), transparent 82%);
  pointer-events: none;
}

.auth-section {
  max-width: 920px;
  margin: 0 auto 40px;
}

.card-grid {
  max-width: 1200px;
  margin: 0 auto;
  display: grid;
  gap: 28px;
}

.workspace-grid {
  grid-template-columns: minmax(0, 1.16fr) minmax(320px, 0.84fr);
}

.agent-card {
  grid-column: 1 / -1;
}

.card,
.workspace-card,
.summary-card {
  padding: 32px;
  border: 1px solid rgba(15, 23, 42, 0.06);
  border-radius: 38px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.94), rgba(248, 250, 253, 0.82)),
    rgba(255, 255, 255, 0.84);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.84),
    0 24px 60px rgba(15, 23, 42, 0.08);
  backdrop-filter: blur(18px);
  transition: all 0.4s cubic-bezier(0.25, 0.8, 0.25, 1);
}

.card:hover,
.workspace-card:hover,
.summary-card:hover {
  transform: translateY(-4px);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.9),
    0 30px 72px rgba(15, 23, 42, 0.1);
}

.processing-banner {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 14px;
  align-items: start;
  margin-top: 18px;
  padding: 18px 20px;
  border: 1px solid rgba(15, 23, 42, 0.06);
  border-radius: 24px;
  background: linear-gradient(180deg, rgba(239, 246, 255, 0.78), rgba(255, 255, 255, 0.82));
}

.processing-icon {
  margin-top: 2px;
  font-size: 1.5rem;
  color: #2563eb;
}

.processing-copy h3 {
  margin-bottom: 6px;
}

.processing-copy p {
  margin: 0;
  color: rgba(15, 23, 42, 0.6);
  line-height: 1.7;
}

.card-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 18px;
}

.card-label {
  margin: 0 0 10px;
  color: rgba(15, 23, 42, 0.42);
  font-size: 0.76rem;
  font-weight: 700;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}

h2,
h3 {
  margin: 0;
  font-family: "Inter", "SF Pro Display", "PingFang SC", sans-serif;
  letter-spacing: -0.05em;
  color: #0f172a;
  font-weight: 800;
}

.pill {
  display: inline-flex;
  align-items: center;
  padding: 10px 14px;
  border-radius: 999px;
  border: 1px solid rgba(15, 23, 42, 0.06);
  background: rgba(255, 255, 255, 0.72);
  color: #2563eb;
  font-size: 0.8rem;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.pill.success {
  background: rgba(240, 253, 250, 0.78);
  color: #0f766e;
}

.pill.agent {
  background: rgba(255, 251, 235, 0.88);
  color: #b45309;
}

.todo-list {
  margin: 0;
  padding-left: 20px;
  line-height: 1.9;
  color: rgba(15, 23, 42, 0.72);
}

.file-picker {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 24px;
  border: 1px dashed rgba(15, 23, 42, 0.12);
  border-radius: 28px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.82), rgba(246, 248, 251, 0.78));
  color: #0f172a;
  font-weight: 700;
  transition: all 0.4s cubic-bezier(0.25, 0.8, 0.25, 1);
}

.file-picker input {
  font-weight: 400;
}

.file-picker small {
  color: rgba(15, 23, 42, 0.48);
  font-weight: 500;
}

.file-picker--dragging {
  border-color: rgba(37, 99, 235, 0.28);
  box-shadow:
    0 0 0 4px rgba(37, 99, 235, 0.08),
    0 22px 44px rgba(15, 23, 42, 0.08);
  transform: translateY(-3px);
}

.file-name,
.helper-text {
  margin: 14px 0 0;
  color: rgba(15, 23, 42, 0.58);
  line-height: 1.8;
}

.audio-preview {
  margin-top: 18px;
  padding: 16px 18px;
  border: 1px solid rgba(15, 23, 42, 0.06);
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.68);
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
  color: rgba(15, 23, 42, 0.48);
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
  padding-top: 6px;
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
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.68);
  border: 1px solid rgba(15, 23, 42, 0.05);
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
  color: rgba(15, 23, 42, 0.72);
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 12px;
}

:deep(.el-empty__description p) {
  color: rgba(15, 23, 42, 0.42);
}

:deep(.el-tag) {
  padding: 0 14px;
  border-radius: 999px;
  background: rgba(239, 246, 255, 0.82);
  border-color: rgba(37, 99, 235, 0.08);
  color: #2563eb;
}

:deep(.el-input__wrapper) {
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.72);
  box-shadow: 0 0 0 1px rgba(15, 23, 42, 0.05) inset;
}

:deep(.el-textarea__inner) {
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.78);
  box-shadow: 0 0 0 1px rgba(15, 23, 42, 0.05) inset;
  color: #0f172a;
}

:deep(.el-button) {
  min-height: 48px;
  border-radius: 999px;
  font-weight: 700;
  transition: all 0.4s cubic-bezier(0.25, 0.8, 0.25, 1);
}

:deep(.el-button:not(.is-disabled):hover) {
  transform: translateY(-2px);
}

:deep(.el-button--primary) {
  background: linear-gradient(180deg, #0f172a, #1e293b);
  border-color: transparent;
}

:deep(.el-button--success) {
  background: linear-gradient(180deg, #2563eb, #1d4ed8);
  border-color: transparent;
}

:deep(.el-button.is-plain) {
  background: rgba(255, 255, 255, 0.72);
  border-color: rgba(15, 23, 42, 0.08);
  color: #334155;
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

.assessment-text {
  margin: 10px 0 0;
  line-height: 1.8;
  color: rgba(15, 23, 42, 0.72);
  padding: 14px 18px;
  border-radius: 18px;
  background: rgba(255, 251, 235, 0.72);
  border: 1px solid rgba(180, 83, 9, 0.08);
}

.action-item-list {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.action-item {
  padding: 14px 18px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.68);
  border: 1px solid rgba(15, 23, 42, 0.05);
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  justify-content: space-between;
}

.action-task {
  flex: 1;
  min-width: 180px;
  color: #0f172a;
  font-weight: 600;
  line-height: 1.6;
}

.action-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

@media (max-width: 980px) {
  .workspace-grid {
    grid-template-columns: 1fr;
  }
}
</style>
