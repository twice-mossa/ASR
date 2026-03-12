<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import { fetchCurrentUser, loginUser, logoutUser, registerUser } from "./api/auth";
import { summarizeMeeting, transcribeMeeting } from "./api/meeting";
import AuthPanel from "./components/AuthPanel.vue";
import DeliverySummary from "./components/DeliverySummary.vue";
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
const message = reactive({
  type: "success",
  text: "",
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
  transcript: null,
  summary: null,
});

const projectSteps = [
  "登录后上传会议音频",
  "调用 faster-whisper 生成带时间戳的转写结果",
  "调用 MiniMax 或兜底逻辑生成纪要、关键词和待办事项",
  "把这条链路作为明天路演的主流程",
];

const deliveryItems = [
  "MySQL 用户注册、登录、退出与登录态保持",
  "前端音频上传并调用转写接口",
  "前端根据转写文本生成会议纪要",
  "默认支持 MiniMax 摘要，未配置时自动走兜底摘要",
  "后端修复了转写线程调用问题，主链路能真正执行",
];

const isAuthenticated = computed(() => Boolean(session.token && session.user));
const canGenerateSummary = computed(() => Boolean(workspace.transcript?.text));

function setMessage(text, type = "success") {
  message.text = text;
  message.type = type;
}

function clearMessage() {
  message.text = "";
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
  workspace.file = null;
  workspace.fileName = "";
  workspace.transcript = null;
  workspace.summary = null;
}

function handleFileSelect(event) {
  const [file] = event.target.files || [];
  workspace.file = file || null;
  workspace.fileName = file?.name || "";
  workspace.transcript = null;
  workspace.summary = null;
  clearMessage();
}

async function handleRegister() {
  clearMessage();

  if (registerForm.password !== registerForm.confirmPassword) {
    setMessage("两次输入的密码不一致", "error");
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
    setMessage("注册成功，已自动登录");
    registerForm.username = "";
    registerForm.email = "";
    registerForm.password = "";
    registerForm.confirmPassword = "";
  } catch (error) {
    setMessage(resolveError(error, "注册失败，请稍后再试"), "error");
  } finally {
    authLoading.value = false;
  }
}

async function handleLogin() {
  clearMessage();
  authLoading.value = true;
  try {
    const payload = await loginUser({
      identifier: loginForm.identifier.trim(),
      password: loginForm.password,
    });
    persistSession(payload);
    setMessage("登录成功");
    loginForm.identifier = "";
    loginForm.password = "";
  } catch (error) {
    setMessage(resolveError(error, "登录失败，请稍后再试"), "error");
  } finally {
    authLoading.value = false;
  }
}

async function handleLogout() {
  clearMessage();
  authLoading.value = true;
  try {
    await logoutUser(session.token);
  } catch {
    // Ignore logout failures and clear local state anyway.
  } finally {
    clearSession();
    resetWorkspace();
    authLoading.value = false;
    setMessage("已退出登录");
  }
}

async function handleTranscribe() {
  if (!workspace.file) {
    setMessage("请先选择音频文件", "warning");
    return;
  }

  clearMessage();
  workLoading.transcribe = true;
  workspace.transcript = null;
  workspace.summary = null;

  try {
    workspace.transcript = await transcribeMeeting(workspace.file);
    setMessage("音频转写完成");
  } catch (error) {
    setMessage(resolveError(error, "转写失败，请检查音频格式或模型环境"), "error");
  } finally {
    workLoading.transcribe = false;
  }
}

async function handleSummary() {
  if (!workspace.transcript?.text) {
    setMessage("请先完成音频转写", "warning");
    return;
  }

  clearMessage();
  workLoading.summary = true;
  try {
    workspace.summary = await summarizeMeeting(workspace.transcript.text);
    setMessage("会议纪要生成完成");
  } catch (error) {
    setMessage(resolveError(error, "摘要生成失败，请检查 API 配置"), "error");
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
</script>

<template>
  <main class="page-shell">
    <PageHero
      eyebrow="ASR Meeting Assistant"
      title="智能会议助手"
      intro="今天的目标不是只把页面搭起来，而是让“登录 -> 上传音频 -> 转写 -> 纪要”这条主流程真正能跑通，明天可以直接用于路演。"
      card-label="明日路演主线"
      card-title="建议按这 4 步演示"
      :project-steps="projectSteps"
    />

    <el-alert
      v-if="message.text"
      :title="message.text"
      :type="message.type"
      show-icon
      class="status-alert"
      :closable="false"
    />

    <section class="card-grid top-grid">
      <AuthPanel
        v-model:active-tab="activeTab"
        :loading="authLoading"
        :is-authenticated="isAuthenticated"
        :session="session"
        :login-form="loginForm"
        :register-form="registerForm"
        guest-label="账号中心"
        guest-title="登录 / 注册"
        guest-pill="MySQL 用户体系"
        authed-label="当前账号"
        authed-pill="已登录"
        @login="handleLogin"
        @register="handleRegister"
        @logout="handleLogout"
      />

      <DeliverySummary label="交付说明" title="今天补齐的关键能力" :items="deliveryItems" />
    </section>

    <section class="card-grid workspace-grid" v-if="isAuthenticated">
      <article class="card workspace-card">
        <div class="card-header">
          <div>
            <p class="card-label">会议工作台</p>
            <h2>上传音频并开始处理</h2>
          </div>
          <span class="pill">可演示流程</span>
        </div>

        <label class="file-picker">
          <span>选择会议音频文件</span>
          <input type="file" accept=".wav,.mp3,.m4a,.flac" @change="handleFileSelect" />
        </label>

        <p class="file-name" v-if="workspace.fileName">当前文件：{{ workspace.fileName }}</p>
        <p class="helper-text" v-else>建议优先使用 `sample-data/audio` 里的短样本做明天的路演。</p>

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
            <p class="card-label">智能纪要</p>
            <h2>摘要、关键词与待办事项</h2>
          </div>
          <span class="pill success">AI 输出</span>
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
:global(body) {
  margin: 0;
  font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
  background:
    radial-gradient(circle at top left, #ffd6a5 0%, transparent 28%),
    radial-gradient(circle at top right, #d2f4ea 0%, transparent 24%),
    linear-gradient(135deg, #f8efe3 0%, #edf6ff 100%);
  color: #1d2a36;
}

:global(*) {
  box-sizing: border-box;
}

.page-shell {
  min-height: 100vh;
  padding: 48px 20px 56px;
}

.status-alert {
  max-width: 1180px;
  margin: 0 auto 24px;
}

.card-grid {
  max-width: 1180px;
  margin: 0 auto 20px;
  display: grid;
  gap: 20px;
}

.top-grid {
  grid-template-columns: minmax(320px, 0.9fr) minmax(280px, 0.7fr);
}

.workspace-grid {
  grid-template-columns: minmax(0, 1.2fr) minmax(320px, 0.8fr);
}

.card,
.workspace-card,
.summary-card {
  padding: 24px;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.84);
  box-shadow: 0 18px 60px rgba(48, 60, 80, 0.12);
  backdrop-filter: blur(10px);
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
  color: #915f00;
  font-size: 0.9rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

h2,
h3 {
  margin: 0;
}

.pill {
  display: inline-flex;
  align-items: center;
  padding: 8px 12px;
  border-radius: 999px;
  background: #fff3d2;
  color: #8a5b00;
  font-size: 0.88rem;
  font-weight: 700;
}

.pill.success {
  background: #dff5ea;
  color: #0a6c47;
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
  padding: 18px;
  border: 1px dashed #cda861;
  border-radius: 18px;
  background: #fff9ed;
  color: #7f5200;
  font-weight: 700;
}

.file-picker input {
  font-weight: 400;
}

.file-name,
.helper-text {
  margin: 14px 0 0;
  color: #546173;
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
  padding: 12px;
  border-radius: 14px;
  background: #f7f8fb;
}

.segment-time {
  color: #915f00;
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

@media (max-width: 980px) {
  .top-grid,
  .workspace-grid {
    grid-template-columns: 1fr;
  }
}
</style>
