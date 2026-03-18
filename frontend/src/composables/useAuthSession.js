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

  function openLoginModal(action = null, tab = "login") {
    pendingAction.value = action;
    loginModalTab.value = tab;
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
      registerForm.username = "";
      registerForm.email = "";
      registerForm.password = "";
      registerForm.confirmPassword = "";
      loginModalVisible.value = false;
      notify("注册成功，已自动登录", "success", "欢迎回来");
      await runPendingAction();
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
      loginForm.identifier = "";
      loginForm.password = "";
      loginModalVisible.value = false;
      notify("登录成功", "success", "欢迎回来");
      await runPendingAction();
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
    clearSession,
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
