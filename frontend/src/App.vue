<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import { fetchCurrentUser, loginUser, logoutUser, registerUser } from "./api/auth";

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
const loading = ref(false);
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

const projectSteps = [
  "注册账号并保存登录状态",
  "上传会议音频并执行转写",
  "生成会议纪要、关键词和待办事项",
  "后续接入关键词搜索与语音回放",
];

const isAuthenticated = computed(() => Boolean(session.token && session.user));

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

async function handleRegister() {
  clearMessage();

  if (registerForm.password !== registerForm.confirmPassword) {
    setMessage("两次输入的密码不一致", "error");
    return;
  }

  loading.value = true;
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
    loading.value = false;
  }
}

async function handleLogin() {
  clearMessage();
  loading.value = true;
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
    loading.value = false;
  }
}

async function handleLogout() {
  clearMessage();
  loading.value = true;
  try {
    await logoutUser(session.token);
  } catch {
    // Ignore logout failures and clear local state anyway.
  } finally {
    clearSession();
    loading.value = false;
    setMessage("已退出登录");
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
          先完成账号注册和登录，再逐步接入音频转写、会议纪要、关键词搜索与语音回放。
        </p>
      </div>

      <div class="hero-card">
        <p class="card-label">当前阶段</p>
        <h2>登录注册已纳入 Sprint 1</h2>
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

    <section class="card-grid">
      <article class="card auth-card">
        <template v-if="!isAuthenticated">
          <div class="card-header">
            <div>
              <p class="card-label">账号中心</p>
              <h2>登录 / 注册</h2>
            </div>
            <span class="pill">基础功能</span>
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
                <el-button type="primary" :loading="loading" class="submit-button" @click="handleLogin">
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
                <el-button type="primary" :loading="loading" class="submit-button" @click="handleRegister">
                  注册并登录
                </el-button>
              </el-form>
            </el-tab-pane>
          </el-tabs>
        </template>

        <template v-else>
          <div class="card-header">
            <div>
              <p class="card-label">欢迎回来</p>
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
            <el-button type="danger" plain :loading="loading" @click="handleLogout">退出登录</el-button>
          </div>
        </template>
      </article>

      <article class="card">
        <p class="card-label">交付说明</p>
        <h2>这次实现了什么</h2>
        <ul class="feature-list">
          <li>后端注册接口，支持用户名与邮箱唯一校验</li>
          <li>后端登录接口，支持用户名或邮箱登录</li>
          <li>本地 SQLite 持久化用户数据</li>
          <li>前端注册、登录、退出与登录态保持</li>
          <li>Vite 代理配置，开发时可直接调用后端接口</li>
        </ul>
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
  max-width: 1080px;
  margin: 0 auto 24px;
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) minmax(280px, 0.9fr);
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

h2 {
  margin: 0 0 16px;
  font-size: 1.45rem;
}

.intro {
  max-width: 720px;
  margin-top: 16px;
  font-size: 1.05rem;
  line-height: 1.8;
}

.hero-card,
.card {
  padding: 24px;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.82);
  box-shadow: 0 18px 60px rgba(48, 60, 80, 0.12);
  backdrop-filter: blur(10px);
}

.hero-card ol {
  margin: 0;
  padding-left: 20px;
  line-height: 1.9;
}

.status-alert {
  max-width: 1080px;
  margin: 0 auto 24px;
}

.card-grid {
  max-width: 1080px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(280px, 0.8fr);
  gap: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 8px;
}

.auth-card {
  min-height: 520px;
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

.feature-list {
  margin: 0;
  padding-left: 20px;
  line-height: 1.9;
}

@media (max-width: 860px) {
  .hero,
  .card-grid {
    grid-template-columns: 1fr;
  }
}
</style>
