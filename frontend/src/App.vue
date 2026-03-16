<script setup>
import { Loading } from "@element-plus/icons-vue";
import { ElNotification } from "element-plus";
import { computed, onBeforeUnmount, onMounted, reactive, ref } from "vue";

import { fetchCurrentUser, loginUser, logoutUser, registerUser } from "./api/auth";
import { emailMeetingSummary, runMeetingAgent, summarizeMeeting } from "./api/meeting";
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
  email: false,
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
  transcriptionStatus: "idle",
  completedChunks: 0,
  totalChunks: 1,
  agentName: "",
  agentPrompt: "",
  summaryMode: "general",
  scene: "general",
  toolsUsed: [],
  trace: [],
  speakerTurns: [],
  inspection: null,
  presentationSections: [],
  activeSpeaker: "all",
});

const heroHighlights = [
  {
    title: "智能体调度工具链",
    description: "先检测音频，再按时长和大小决定直传或长音频策略，不再是单接口直调。",
  },
  {
    title: "说话人分段可讲可演示",
    description: "转写结果保留时间戳，并给出轻量说话人标签，便于老师看出处理链条。",
  },
  {
    title: "多模式会议智能体",
    description: "同一份转写可以按通用秘书、项目推进、领导汇报三种模式生成不同风格输出。",
  },
];

const heroNotes = [
  "先由 Agent 检查音频时长、声道与大小。",
  "长音频会走分段并发策略，短音频直接转写。",
  "再根据模式切换不同纪要智能体输出。",
];

const heroMetrics = [
  { value: "01", label: "Audio Inspect" },
  { value: "02", label: "ASR + Speaker" },
  { value: "03", label: "Multi-Agent Summary" },
];

const isAuthenticated = computed(() => Boolean(session.token && session.user));
const canGenerateSummary = computed(() => Boolean(workspace.transcript?.text) && !workLoading.transcribe);
const canPreviewAudio = computed(() => Boolean(workspace.audioUrl));
const hasAgentTrace = computed(() => workspace.trace.length > 0);
const hasSpeakerTurns = computed(() => workspace.speakerTurns.length > 0);
const hasPresentationSections = computed(() => workspace.presentationSections.length > 0);
const speakerOptions = computed(() => {
  const values = new Set(workspace.speakerTurns.map((item) => item.speaker));
  return ["all", ...values];
});
const filteredSpeakerTurns = computed(() => {
  if (workspace.activeSpeaker === "all") {
    return workspace.speakerTurns;
  }
  return workspace.speakerTurns.filter((item) => item.speaker === workspace.activeSpeaker);
});
const summaryModeLabel = computed(() => {
  const modeMap = {
    general: "通用会议秘书",
    project: "项目推进智能体",
    executive: "领导汇报智能体",
  };
  return modeMap[workspace.summaryMode] || "通用会议秘书";
});

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
  workspace.file = null;
  workspace.fileName = "";
  workspace.audioUrl = "";
  workspace.transcript = null;
  workspace.summary = null;
  workspace.isDragging = false;
  workspace.transcriptionStatus = "idle";
  workspace.completedChunks = 0;
  workspace.totalChunks = 1;
  workspace.agentName = "";
  workspace.agentPrompt = "";
  workspace.toolsUsed = [];
  workspace.trace = [];
  workspace.speakerTurns = [];
  workspace.inspection = null;
  workspace.presentationSections = [];
  workspace.activeSpeaker = "all";
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
  workspace.transcriptionStatus = "idle";
  workspace.completedChunks = 0;
  workspace.totalChunks = 1;
  workspace.agentName = "";
  workspace.agentPrompt = "";
  workspace.toolsUsed = [];
  workspace.trace = [];
  workspace.speakerTurns = [];
  workspace.inspection = null;
  workspace.presentationSections = [];
  workspace.activeSpeaker = "all";
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

async function handleAgentRun() {
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
  workspace.trace = [];
  workspace.speakerTurns = [];
  workspace.toolsUsed = [];
  workspace.inspection = null;
  workspace.presentationSections = [];
  workspace.activeSpeaker = "all";
  notify("智能体已开始调度工具链。长音频可能需要几分钟，请等待返回。", "info", "Agent 启动");

  try {
    const result = await runMeetingAgent(workspace.file, workspace.summaryMode, workspace.scene);
    workspace.transcriptionStatus = "completed";
    workspace.agentName = result.agent_name || "";
    workspace.agentPrompt = result.agent_prompt || "";
    workspace.toolsUsed = result.tools_used || [];
    workspace.trace = result.trace || [];
    workspace.speakerTurns = result.speaker_turns || [];
    workspace.inspection = result.inspection || null;
    workspace.presentationSections = result.presentation_sections || [];
    workspace.activeSpeaker = "all";
    workspace.transcript = result.transcript || workspace.transcript;
    workspace.summary = result.summary || null;
    notify("Agent 执行完成，已返回转写、说话人分段和纪要。", "success", "处理完成");
  } catch (error) {
    notify(
      resolveError(error, "Agent 执行失败。请检查后端服务与模型配置。"),
      "error",
      "执行失败",
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

async function handleEmailSummary() {
  if (!workspace.summary || !workspace.transcript?.text || !session.token) {
    notify("请先完成 Agent 执行或摘要生成，再发送邮件。", "warning", "无法发送");
    return;
  }

  workLoading.email = true;
  try {
    const result = await emailMeetingSummary(session.token, {
      transcript_text: workspace.transcript.text,
      summary: workspace.summary.summary,
      keywords: workspace.summary.keywords || [],
      todos: workspace.summary.todos || [],
      summary_mode: workspace.summaryMode,
      agent_name: workspace.agentName,
      scene: workspace.scene,
    });
    notify(result.message || `已发送到 ${result.recipient}`, "success", "邮件发送成功");
  } catch (error) {
    notify(resolveError(error, "邮件发送失败，请检查 SMTP 配置"), "error", "发送失败");
  } finally {
    workLoading.email = false;
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

        <div class="agent-control-grid">
          <label class="field-group">
            <span>摘要模式</span>
            <el-select v-model="workspace.summaryMode" placeholder="选择智能体模式">
              <el-option label="通用会议秘书" value="general" />
              <el-option label="项目推进智能体" value="project" />
              <el-option label="领导汇报智能体" value="executive" />
            </el-select>
          </label>

          <label class="field-group">
            <span>业务场景</span>
            <el-select v-model="workspace.scene" placeholder="选择业务场景">
              <el-option label="通用场景" value="general" />
              <el-option label="校园会议" value="campus" />
              <el-option label="企业项目" value="enterprise" />
              <el-option label="产品评审" value="product" />
            </el-select>
          </label>
        </div>

        <div class="agent-banner">
          <strong>{{ summaryModeLabel }}</strong>
          <span>当前将通过 Agent 统一调度音频检测、转写、说话人分段和纪要生成。</span>
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
          <el-button type="primary" :loading="workLoading.transcribe" @click="handleAgentRun">
            1. Agent 执行
          </el-button>
          <el-button
            type="success"
            :disabled="!canGenerateSummary"
            :loading="workLoading.summary"
            @click="handleSummary"
          >
            2. 单独生成纪要
          </el-button>
          <el-button plain @click="resetWorkspace">重置</el-button>
        </div>

        <div v-if="workspace.inspection" class="inspection-panel">
          <div class="inspection-panel__header">
            <h3>音频检测</h3>
            <span>{{ workspace.inspection.processing_strategy }}</span>
          </div>
          <div class="inspection-grid">
            <div class="inspection-item">
              <span>时长</span>
              <strong>{{ workspace.inspection.duration_seconds }}s</strong>
            </div>
            <div class="inspection-item">
              <span>采样率</span>
              <strong>{{ workspace.inspection.sample_rate }} Hz</strong>
            </div>
            <div class="inspection-item">
              <span>声道</span>
              <strong>{{ workspace.inspection.channels }}</strong>
            </div>
            <div class="inspection-item">
              <span>建议分段</span>
              <strong>{{ workspace.inspection.suggested_chunk_seconds }}s</strong>
            </div>
          </div>
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

        <div v-if="hasSpeakerTurns" class="speaker-block">
          <div class="result-header">
            <h3>说话人分段</h3>
            <span>{{ filteredSpeakerTurns.length }} / {{ workspace.speakerTurns.length }} 段</span>
          </div>

          <div class="speaker-filter-row">
            <el-radio-group v-model="workspace.activeSpeaker" size="small">
              <el-radio-button v-for="speaker in speakerOptions" :key="speaker" :label="speaker">
                {{ speaker === "all" ? "全部" : speaker }}
              </el-radio-button>
            </el-radio-group>
          </div>

          <div class="speaker-list">
            <div
              v-for="turn in filteredSpeakerTurns"
              :key="`${turn.speaker}-${turn.start}-${turn.end}`"
              class="speaker-item"
            >
              <div class="speaker-meta">
                <strong>{{ turn.speaker }}</strong>
                <span>{{ turn.start.toFixed(1) }}s - {{ turn.end.toFixed(1) }}s</span>
              </div>
              <p>{{ turn.text }}</p>
            </div>
          </div>
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

        <div v-if="workspace.agentName" class="agent-meta-card">
          <strong>{{ workspace.agentName }}</strong>
          <p>工具链：{{ workspace.toolsUsed.join(" -> ") }}</p>
        </div>

        <div v-if="workspace.summary && session.user?.email" class="email-action-card">
          <div>
            <strong>发送纪要到邮箱</strong>
            <p>当前登录用户邮箱：{{ session.user.email }}</p>
          </div>
          <el-button type="primary" :loading="workLoading.email" @click="handleEmailSummary">
            发送到我的邮箱
          </el-button>
        </div>

        <div v-if="workspace.agentPrompt" class="agent-prompt-card">
          <div class="result-header">
            <h3>Agent Prompt</h3>
            <span>{{ summaryModeLabel }}</span>
          </div>
          <p>{{ workspace.agentPrompt }}</p>
        </div>

        <el-empty v-if="!workspace.summary" description="生成纪要后会在这里展示内容" />

        <template v-else>
          <template v-if="hasPresentationSections">
            <div v-for="section in workspace.presentationSections" :key="section.title" class="summary-section">
              <h3>{{ section.title }}</h3>
              <p v-if="section.summary">{{ section.summary }}</p>
              <ul v-if="section.bullets?.length" class="todo-list">
                <li v-for="item in section.bullets" :key="item">{{ item }}</li>
              </ul>
            </div>
          </template>

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
        </template>

        <div v-if="hasAgentTrace" class="trace-block">
          <div class="result-header">
            <h3>Agent 执行轨迹</h3>
            <span>{{ workspace.trace.length }} steps</span>
          </div>

          <div class="trace-list">
            <div v-for="item in workspace.trace" :key="`${item.step}-${item.tool_name}`" class="trace-item">
              <div class="trace-item__top">
                <strong>{{ item.step }}</strong>
                <span>{{ item.tool_name }}</span>
              </div>
              <p>{{ item.detail }}</p>
            </div>
          </div>
        </div>
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

.agent-control-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 18px;
}

.field-group {
  display: grid;
  gap: 8px;
}

.field-group span {
  color: rgba(15, 23, 42, 0.52);
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.agent-banner {
  display: grid;
  gap: 6px;
  margin-bottom: 18px;
  padding: 16px 18px;
  border: 1px solid rgba(15, 23, 42, 0.06);
  border-radius: 24px;
  background: linear-gradient(180deg, rgba(239, 246, 255, 0.76), rgba(255, 255, 255, 0.8));
}

.agent-banner strong {
  color: #0f172a;
}

.agent-banner span {
  color: rgba(15, 23, 42, 0.6);
  line-height: 1.7;
}

.todo-list {
  margin: 0;
  padding-left: 20px;
  line-height: 1.9;
  color: rgba(15, 23, 42, 0.72);
}

.inspection-panel,
.speaker-block,
.trace-block,
.agent-meta-card,
.agent-prompt-card,
.email-action-card {
  margin-top: 24px;
  padding: 20px;
  border: 1px solid rgba(15, 23, 42, 0.06);
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.7);
}

.inspection-panel__header,
.trace-item__top,
.speaker-meta {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: baseline;
}

.inspection-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 14px;
}

.inspection-item,
.trace-item,
.speaker-item {
  padding: 14px 16px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(15, 23, 42, 0.05);
}

.inspection-item span,
.trace-item span,
.speaker-meta span {
  color: rgba(15, 23, 42, 0.48);
  font-size: 0.8rem;
}

.inspection-item strong,
.trace-item strong,
.speaker-meta strong,
.agent-meta-card strong {
  color: #0f172a;
}

.trace-list,
.speaker-list {
  display: grid;
  gap: 12px;
  margin-top: 14px;
}

.speaker-filter-row {
  margin-top: 14px;
}

.trace-item p,
.speaker-item p,
.agent-meta-card p,
.agent-prompt-card p,
.email-action-card p {
  margin: 10px 0 0;
  color: rgba(15, 23, 42, 0.68);
  line-height: 1.8;
}

.email-action-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
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

:deep(.el-select__wrapper) {
  min-height: 48px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.72);
  box-shadow: 0 0 0 1px rgba(15, 23, 42, 0.05) inset;
}

:deep(.el-radio-group) {
  flex-wrap: wrap;
}

:deep(.el-radio-button__inner) {
  border-radius: 999px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  background: rgba(255, 255, 255, 0.72);
  color: #334155;
  box-shadow: none;
}

:deep(.el-radio-button:first-child .el-radio-button__inner),
:deep(.el-radio-button:last-child .el-radio-button__inner) {
  border-radius: 999px;
}

:deep(.el-radio-button__original-radio:checked + .el-radio-button__inner) {
  background: linear-gradient(180deg, #0f172a, #1e293b);
  border-color: transparent;
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

  .agent-control-grid,
  .inspection-grid {
    grid-template-columns: 1fr;
  }
}
</style>
