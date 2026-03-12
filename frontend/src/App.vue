<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import { fetchCurrentUser, loginUser, logoutUser, registerUser } from "./api/auth";
import { summarizeMeeting, transcribeMeeting } from "./api/meeting";

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
    <section class="hero">
      <div>
        <p class="eyebrow">ASR Meeting Assistant</p>
        <h1>智能会议助手</h1>
        <p class="intro">
          今天的目标不是只把页面搭起来，而是让“登录 -> 上传音频 -> 转写 -> 纪要”这条主流程真正能跑通，明天可以直接用于路演。
        </p>
      </div>

      <div class="hero-card">
        <p class="card-label">明日路演主线</p>
        <h2>建议按这 4 步演示</h2>
        <ol>
          <li v-for="step in projectSteps" :key="step">{{ step }}</li>
        </ol>
      </div>
    </section>

    <el-alert
      v-if="message.text"
      :title="message.text"
      :type="message.type"
      show-icon
      class="status-alert"
      :closable="false"
    />

    <section class="card-grid top-grid">
      <article class="card auth-card">
        <template v-if="!isAuthenticated">
          <div class="card-header">
            <div>
              <p class="card-label">账号中心</p>
              <h2>登录 / 注册</h2>
            </div>
            <span class="pill">MySQL 用户体系</span>
          </div>

          <el-tabs v-model="activeTab" stretch>
            <el-tab-pane label="登录" name="login">
              <el-form label-position="top" @submit.prevent="handleLogin">
                <el-form-item label="用户名或邮箱">
                  <el-input v-model="loginForm.identifier" placeholder="请输入用户名或邮箱" />
                </el-form-item>
                <el-form-item label="密码">
                  <el-input
                    v-model="loginForm.password"
                    type="password"
                    show-password
                    placeholder="请输入密码"
                  />
                </el-form-item>
                <el-button type="primary" :loading="authLoading" class="submit-button" @click="handleLogin">
                  登录
                </el-button>
              </el-form>
            </el-tab-pane>

            <el-tab-pane label="注册" name="register">
              <el-form label-position="top" @submit.prevent="handleRegister">
                <el-form-item label="用户名">
                  <el-input v-model="registerForm.username" placeholder="至少 3 个字符" />
                </el-form-item>
                <el-form-item label="邮箱">
                  <el-input v-model="registerForm.email" placeholder="请输入邮箱" />
                </el-form-item>
                <el-form-item label="密码">
                  <el-input
                    v-model="registerForm.password"
                    type="password"
                    show-password
                    placeholder="至少 6 位密码"
                  />
                </el-form-item>
                <el-form-item label="确认密码">
                  <el-input
                    v-model="registerForm.confirmPassword"
                    type="password"
                    show-password
                    placeholder="请再次输入密码"
                  />
                </el-form-item>
                <el-button type="primary" :loading="authLoading" class="submit-button" @click="handleRegister">
                  注册并登录
                </el-button>
              </el-form>
            </el-tab-pane>
          </el-tabs>
        </template>

        <template v-else>
          <div class="card-header">
            <div>
              <p class="card-label">当前账号</p>
              <h2>{{ session.user.username }}</h2>
            </div>
            <span class="pill success">已登录</span>
          </div>

          <el-descriptions :column="1" border>
            <el-descriptions-item label="用户 ID">{{ session.user.id }}</el-descriptions-item>
            <el-descriptions-item label="用户名">{{ session.user.username }}</el-descriptions-item>
            <el-descriptions-item label="邮箱">{{ session.user.email }}</el-descriptions-item>
          </el-descriptions>

          <div class="auth-actions">
            <el-button type="danger" plain :loading="authLoading" @click="handleLogout">退出登录</el-button>
          </div>
        </template>
      </article>

      <article class="card">
        <p class="card-label">交付说明</p>
        <h2>今天补齐的关键能力</h2>
        <ul class="feature-list">
          <li>MySQL 用户注册、登录、退出与登录态保持</li>
          <li>前端音频上传并调用转写接口</li>
          <li>前端根据转写文本生成会议纪要</li>
          <li>默认支持 MiniMax 摘要，未配置时自动走兜底摘要</li>
          <li>后端修复了转写线程调用问题，主链路能真正执行</li>
        </ul>
      </article>
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

.hero {
  max-width: 1180px;
  margin: 0 auto 24px;
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(300px, 0.8fr);
  gap: 20px;
  align-items: stretch;
}

.eyebrow,
.card-label {
  margin: 0 0 10px;
  color: #915f00;
  font-size: 0.9rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

h1 {
  margin: 0;
  font-size: clamp(2.6rem, 5vw, 4.6rem);
}

h2,
h3 {
  margin: 0;
}

.intro {
  max-width: 760px;
  margin-top: 16px;
  font-size: 1.05rem;
  line-height: 1.8;
}

.hero-card,
.card {
  padding: 24px;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.84);
  box-shadow: 0 18px 60px rgba(48, 60, 80, 0.12);
  backdrop-filter: blur(10px);
}

.hero-card ol {
  margin: 14px 0 0;
  padding-left: 20px;
  line-height: 1.9;
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

.card-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 16px;
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

.submit-button {
  width: 100%;
  margin-top: 8px;
}

.auth-actions {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

.feature-list,
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
  .hero,
  .top-grid,
  .workspace-grid {
    grid-template-columns: 1fr;
  }
}
</style>
