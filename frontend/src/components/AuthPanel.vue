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
    default: "登录 / 注册",
  },
  guestPill: {
    type: String,
    default: "基础功能",
  },
  authedLabel: {
    type: String,
    default: "欢迎回来",
  },
  authedPill: {
    type: String,
    default: "已登录",
  },
});

const emit = defineEmits([
  "update:activeTab",
  "login",
  "register",
  "logout",
]);
</script>

<template>
  <article class="card auth-card">
    <template v-if="!isAuthenticated">
      <div class="card-header">
        <div>
          <p class="card-label">{{ guestLabel }}</p>
          <h2>{{ guestTitle }}</h2>
        </div>
        <span class="pill">{{ guestPill }}</span>
      </div>

      <el-tabs
        :model-value="activeTab"
        stretch
        @update:model-value="emit('update:activeTab', $event)"
      >
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
              登录
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
              注册并登录
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
  padding: 24px;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.82);
  box-shadow: 0 18px 60px rgba(48, 60, 80, 0.12);
  backdrop-filter: blur(10px);
}

.auth-card {
  min-height: 520px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 8px;
}

.card-label {
  margin: 0 0 10px;
  color: #915f00;
  font-size: 0.9rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

h2 {
  margin: 0 0 16px;
  font-size: 1.45rem;
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
</style>
