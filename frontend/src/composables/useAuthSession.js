import { computed, reactive, ref } from "vue";

import { fetchCurrentUser, loginUser, logoutUser, registerUser } from "../api/auth";
import { safeParse } from "../utils/workspace";

export function useAuthSession({ notify, resolveError, onAfterLogout }) {
  const authLoading = ref(false);
  const loginModalVisible = ref(false);
  const loginModalTab = ref("login");
  const pendingAction = ref(null);
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
  const authFeedback = reactive({
    login: {
      form: "",
      fields: {
        identifier: "",
        password: "",
      },
    },
    register: {
      form: "",
      fields: {
        username: "",
        email: "",
        password: "",
        confirmPassword: "",
      },
    },
  });

  let pendingActionHandler = async () => {};

  const isAuthenticated = computed(() => Boolean(session.token && session.user));

  function setPendingActionHandler(handler) {
    pendingActionHandler = handler;
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

  function clearAuthFeedback(mode = "all") {
    if (mode === "all" || mode === "login") {
      authFeedback.login.form = "";
      authFeedback.login.fields.identifier = "";
      authFeedback.login.fields.password = "";
    }

    if (mode === "all" || mode === "register") {
      authFeedback.register.form = "";
      authFeedback.register.fields.username = "";
      authFeedback.register.fields.email = "";
      authFeedback.register.fields.password = "";
      authFeedback.register.fields.confirmPassword = "";
    }
  }

  function applyRequestValidation(mode, detail) {
    if (!Array.isArray(detail)) {
      return false;
    }

    let hasFieldError = false;
    const fields = authFeedback[mode].fields;
    for (const item of detail) {
      const field = item?.loc?.[item.loc.length - 1];
      if (field && Object.prototype.hasOwnProperty.call(fields, field)) {
        fields[field] = item?.msg || "输入格式不正确";
        hasFieldError = true;
      }
    }
    return hasFieldError;
  }

  function validateLoginForm() {
    clearAuthFeedback("login");
    let valid = true;

    if (!loginForm.identifier.trim()) {
      authFeedback.login.fields.identifier = "请输入用户名或邮箱";
      valid = false;
    }
    if (!loginForm.password) {
      authFeedback.login.fields.password = "请输入密码";
      valid = false;
    }

    return valid;
  }

  function validateRegisterForm() {
    clearAuthFeedback("register");
    let valid = true;

    if (registerForm.username.trim().length < 3) {
      authFeedback.register.fields.username = "用户名至少 3 个字符";
      valid = false;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(registerForm.email.trim())) {
      authFeedback.register.fields.email = "请输入有效邮箱";
      valid = false;
    }
    if (registerForm.password.length < 6) {
      authFeedback.register.fields.password = "密码至少 6 位";
      valid = false;
    }
    if (registerForm.password !== registerForm.confirmPassword) {
      authFeedback.register.fields.confirmPassword = "两次输入的密码不一致";
      valid = false;
    }

    return valid;
  }

  function openLoginModal(action = null, tab = "login") {
    pendingAction.value = action;
    loginModalTab.value = tab;
    clearAuthFeedback(tab);
    loginModalVisible.value = true;
  }

  function withAuth(action, tab = "login") {
    if (isAuthenticated.value) {
      return true;
    }

    openLoginModal(action, tab);
    return false;
  }

  async function runPendingAction() {
    const action = pendingAction.value;
    pendingAction.value = null;

    if (!action) {
      return;
    }

    await pendingActionHandler(action);
  }

  async function handleRegister() {
    if (!validateRegisterForm()) {
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
      registerForm.username = "";
      registerForm.email = "";
      registerForm.password = "";
      registerForm.confirmPassword = "";
      clearAuthFeedback("register");
      loginModalVisible.value = false;
      notify("注册成功，已自动登录", "success", "欢迎回来");
      await runPendingAction();
    } catch (error) {
      const detail = error?.response?.data?.detail;
      if (error?.response?.status === 409) {
        authFeedback.register.form = "用户名或邮箱已存在，请更换后重试。";
        authFeedback.register.fields.username = "可能已被占用";
        authFeedback.register.fields.email = "可能已被占用";
      } else if (!applyRequestValidation("register", detail)) {
        authFeedback.register.form = resolveError(error, "注册失败，请稍后再试");
      }
      notify(resolveError(error, "注册失败，请稍后再试"), "error", "注册失败");
    } finally {
      authLoading.value = false;
    }
  }

  async function handleLogin() {
    if (!validateLoginForm()) {
      return;
    }

    authLoading.value = true;
    try {
      const payload = await loginUser({
        identifier: loginForm.identifier.trim(),
        password: loginForm.password,
      });
      persistSession(payload);
      loginForm.identifier = "";
      loginForm.password = "";
      clearAuthFeedback("login");
      loginModalVisible.value = false;
      notify("登录成功", "success", "欢迎回来");
      await runPendingAction();
    } catch (error) {
      const detail = error?.response?.data?.detail;
      if (error?.response?.status === 401) {
        authFeedback.login.form = "用户名/邮箱或密码错误，请重新输入。";
        authFeedback.login.fields.identifier = "请检查账号";
        authFeedback.login.fields.password = "请检查密码";
      } else if (!applyRequestValidation("login", detail)) {
        authFeedback.login.form = resolveError(error, "登录失败，请稍后再试");
      }
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
      loginModalVisible.value = false;
      pendingAction.value = null;
      authLoading.value = false;
      onAfterLogout?.();
      notify("已退出登录", "success", "退出成功");
    }
  }

  async function hydrateSession() {
    if (!session.token) {
      return;
    }

    try {
      session.user = await fetchCurrentUser(session.token);
      localStorage.setItem("auth_user", JSON.stringify(session.user));
    } catch {
      clearSession();
    }
  }

  return {
    authLoading,
    authFeedback,
    clearSession,
    clearAuthFeedback,
    handleLogin,
    handleLogout,
    handleRegister,
    hydrateSession,
    isAuthenticated,
    loginForm,
    loginModalTab,
    loginModalVisible,
    openLoginModal,
    registerForm,
    session,
    setPendingActionHandler,
    withAuth,
  };
}
