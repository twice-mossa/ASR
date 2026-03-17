<script setup>
defineProps({
  visible: {
    type: Boolean,
    required: true,
  },
  activeTab: {
    type: String,
    required: true,
  },
  loading: {
    type: Boolean,
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
});

const emit = defineEmits(["update:visible", "update:activeTab", "login", "register"]);
</script>

<template>
  <el-dialog
    :model-value="visible"
    width="520px"
    align-center
    :show-close="true"
    class="login-modal"
    @close="emit('update:visible', false)"
  >
    <div class="modal-copy">
      <p class="modal-label">Sign in to continue</p>
      <h2>登录后继续分析这段音频</h2>
      <p>页面不会提前拦住你，但在上传、生成摘要、继续问答这些关键动作发生时，我们会在这里完成登录。</p>
    </div>

    <el-tabs :model-value="activeTab" stretch @update:model-value="emit('update:activeTab', $event)">
      <el-tab-pane label="登录" name="login">
        <el-form label-position="top" @submit.prevent="emit('login')">
          <el-form-item label="用户名或邮箱">
            <el-input v-model="loginForm.identifier" placeholder="请输入用户名或邮箱" />
          </el-form-item>
          <el-form-item label="密码">
            <el-input v-model="loginForm.password" type="password" show-password placeholder="请输入密码" />
          </el-form-item>
          <el-button type="primary" class="submit-button" :loading="loading" @click="emit('login')">继续进入工作台</el-button>
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
            <el-input v-model="registerForm.password" type="password" show-password placeholder="至少 6 位密码" />
          </el-form-item>
          <el-form-item label="确认密码">
            <el-input
              v-model="registerForm.confirmPassword"
              type="password"
              show-password
              placeholder="请再次输入密码"
            />
          </el-form-item>
          <el-button type="primary" class="submit-button" :loading="loading" @click="emit('register')">创建账号并继续</el-button>
        </el-form>
      </el-tab-pane>
    </el-tabs>
  </el-dialog>
</template>

<style scoped>
.modal-copy {
  margin-bottom: 12px;
}

.modal-label {
  margin: 0 0 8px;
  color: var(--text-soft);
  font-size: 0.74rem;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}

h2 {
  margin: 0;
  color: var(--text-strong);
  font-size: 1.7rem;
  letter-spacing: -0.04em;
}

.modal-copy p:last-child {
  margin: 10px 0 0;
  color: var(--text-soft);
  line-height: 1.7;
}

.submit-button {
  width: 100%;
  margin-top: 8px;
}
</style>
