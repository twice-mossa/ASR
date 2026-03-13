<script setup>
defineProps({
  activeTab: {
    type: String,
    required: true,
  },
  loading: {
    type: Boolean,
    required: true,
  },
  isAuthenticated: {
    type: Boolean,
    required: true,
  },
  session: {
    type: Object,
    required: true,
  },
  loginForm: {
    type: Object,
    required: true,
  },
  registerForm: {
    type: Object,
    required: true,
  },
  guestLabel: {
    type: String,
    default: "账号中心",
  },
  guestTitle: {
    type: String,
    default: "进入工作区",
  },
  guestPill: {
    type: String,
    default: "Account",
  },
  authedLabel: {
    type: String,
    default: "当前账号",
  },
  authedPill: {
    type: String,
    default: "Ready",
  },
});

const emit = defineEmits(["update:activeTab", "login", "register", "logout"]);
</script>

<template>
  <article class="card auth-card">
    <template v-if="!isAuthenticated">
      <div class="card-header">
        <div>
          <p class="card-label">{{ guestLabel }}</p>
          <h2>{{ guestTitle }}</h2>
          <p class="card-copy">登录之后，上传音频、查看转写、生成纪要都在同一个工作区里完成。</p>
        </div>
        <span class="pill">{{ guestPill }}</span>
      </div>

      <el-tabs :model-value="activeTab" stretch @update:model-value="emit('update:activeTab', $event)">
        <el-tab-pane label="登录" name="login">
          <el-form label-position="top" @submit.prevent="emit('login')">
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
            <el-button type="primary" :loading="loading" class="submit-button" @click="emit('login')">
              进入工作区
            </el-button>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="注册" name="register">
          <el-form label-position="top" @submit.prevent="emit('register')">
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
            <el-button type="primary" :loading="loading" class="submit-button" @click="emit('register')">
              创建账号并开始
            </el-button>
          </el-form>
        </el-tab-pane>
      </el-tabs>
    </template>

    <template v-else>
      <div class="card-header">
        <div>
          <p class="card-label">{{ authedLabel }}</p>
          <h2>{{ session.user.username }}</h2>
          <p class="card-copy">你已经进入工作区，可以直接上传会议音频并开始整理内容。</p>
        </div>
        <span class="pill success">{{ authedPill }}</span>
      </div>

      <el-descriptions :column="1" border>
        <el-descriptions-item label="用户 ID">{{ session.user.id }}</el-descriptions-item>
        <el-descriptions-item label="用户名">{{ session.user.username }}</el-descriptions-item>
        <el-descriptions-item label="邮箱">{{ session.user.email }}</el-descriptions-item>
      </el-descriptions>

      <div class="auth-actions">
        <el-button type="danger" plain :loading="loading" @click="emit('logout')">退出登录</el-button>
      </div>
    </template>
  </article>
</template>

<style scoped>
.card {
  position: relative;
  overflow: hidden;
  padding: 34px;
  border: 1px solid rgba(15, 23, 42, 0.06);
  border-radius: 34px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.94), rgba(246, 248, 251, 0.82)),
    rgba(255, 255, 255, 0.84);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.84),
    0 28px 70px rgba(15, 23, 42, 0.08);
  backdrop-filter: blur(18px);
}

.card::before {
  content: "";
  position: absolute;
  right: -52px;
  bottom: -96px;
  width: 220px;
  height: 220px;
  border-radius: 999px;
  background: radial-gradient(circle, rgba(96, 165, 250, 0.18), rgba(96, 165, 250, 0));
  pointer-events: none;
}

.auth-card {
  min-height: 540px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 14px;
}

.card-label {
  margin: 0 0 10px;
  color: rgba(15, 23, 42, 0.44);
  font-size: 0.76rem;
  font-weight: 700;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}

h2 {
  margin: 0 0 14px;
  font-family: "Inter", "SF Pro Display", "PingFang SC", "Helvetica Neue", sans-serif;
  font-size: clamp(2.4rem, 3.8vw, 3.2rem);
  font-weight: 800;
  letter-spacing: -0.05em;
  color: #0f172a;
}

.card-copy {
  max-width: 34ch;
  margin: 0;
  color: rgba(15, 23, 42, 0.58);
  line-height: 1.9;
}

.pill {
  display: inline-flex;
  align-items: center;
  padding: 10px 14px;
  border-radius: 999px;
  border: 1px solid rgba(15, 23, 42, 0.06);
  background: rgba(255, 255, 255, 0.68);
  color: #1d4ed8;
  font-size: 0.8rem;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.pill.success {
  background: rgba(240, 253, 250, 0.82);
  color: #0f766e;
}

.submit-button {
  width: 100%;
  margin-top: 12px;
}

.auth-actions {
  margin-top: 22px;
  display: flex;
  justify-content: flex-end;
}

:deep(.el-tabs__nav-wrap::after) {
  background-color: rgba(15, 23, 42, 0.06);
}

:deep(.el-tabs__item) {
  font-weight: 700;
}

:deep(.el-tabs__item.is-active) {
  color: #0f172a;
}

:deep(.el-tabs__active-bar) {
  background: linear-gradient(90deg, #2563eb, #60a5fa);
}

:deep(.el-form-item__label) {
  font-weight: 700;
  color: rgba(15, 23, 42, 0.72);
}

:deep(.el-input__wrapper) {
  min-height: 50px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.72);
  box-shadow: 0 0 0 1px rgba(15, 23, 42, 0.06) inset;
  transition: box-shadow 220ms ease, transform 220ms ease, background 220ms ease;
}

:deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.14);
  transform: translateY(-1px);
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

:deep(.el-button--danger.is-plain) {
  background: rgba(255, 255, 255, 0.72);
  border-color: rgba(15, 23, 42, 0.08);
  color: #334155;
}

:deep(.el-descriptions__label) {
  width: 120px;
  font-weight: 700;
  color: rgba(15, 23, 42, 0.42);
}

:deep(.el-descriptions__body) {
  background: transparent;
}

:deep(.el-descriptions__table) {
  border-radius: 22px;
  overflow: hidden;
}

:deep(.el-descriptions__cell) {
  background: rgba(255, 255, 255, 0.72) !important;
  border-color: rgba(15, 23, 42, 0.06) !important;
}
</style>
