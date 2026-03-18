<script setup>
import { Loading, Menu } from "@element-plus/icons-vue";
import { ElNotification } from "element-plus";
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";

import { fetchCurrentUser, loginUser, logoutUser, registerUser } from "./api/auth";
import { getTranscriptionJob, startTranscriptionJob, summarizeMeeting } from "./api/meeting";
import AudioTray from "./components/AudioTray.vue";
import ChatWorkspace from "./components/ChatWorkspace.vue";
import ComposerBar from "./components/ComposerBar.vue";
import LoginModal from "./components/LoginModal.vue";
import SidebarNav from "./components/SidebarNav.vue";
import WorkspaceHeader from "./components/WorkspaceHeader.vue";

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

function formatTime(seconds) {
  if (!Number.isFinite(seconds)) {
    return "--:--";
  }

  const totalSeconds = Math.max(0, Math.round(seconds));
  const minutes = String(Math.floor(totalSeconds / 60)).padStart(2, "0");
  const remainSeconds = String(totalSeconds % 60).padStart(2, "0");
  return `${minutes}:${remainSeconds}`;
}

function formatConversationTime(timestamp) {
  const date = new Date(timestamp);
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");
  return `${month}-${day} ${hours}:${minutes}`;
}

function formatExportDate(value) {
  const date = value ? new Date(value) : new Date();
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");
  return `${year}-${month}-${day} ${hours}:${minutes}`;
}

function slugifyFilename(value) {
  return (value || "meeting-notes")
    .replace(/\.[^/.]+$/, "")
    .replace(/[^\w\u4e00-\u9fa5-]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "")
    .toLowerCase();
}

function buildMessage(role, kind, text = "", extra = {}) {
  return {
    id: `${kind}-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
    role,
    kind,
    text,
    createdAt: Date.now(),
    ...extra,
  };
}

function defaultWorkspaceState() {
  return {
    file: null,
    fileName: "",
    audioUrl: "",
    transcript: null,
    summary: null,
    isDragging: false,
    transcriptionStatus: "idle",
    completedChunks: 0,
    totalChunks: 1,
    durationLabel: "--:--",
    language: "zh",
    summaryGeneratedAt: "",
  };
}

function cloneTranscript(transcript) {
  if (!transcript) {
    return null;
  }

  return {
    ...transcript,
    segments: (transcript.segments || []).map((segment) => ({ ...segment })),
  };
}

function cloneSummary(summary) {
  if (!summary) {
    return null;
  }

  return {
    ...summary,
    keywords: [...(summary.keywords || [])],
    todos: [...(summary.todos || [])],
  };
}

function cloneMessages(list) {
  return list.map((message) => ({
    ...message,
    progress: message.progress ? { ...message.progress } : undefined,
    transcript: message.transcript ? cloneTranscript(message.transcript) : undefined,
    keywords: message.keywords ? [...message.keywords] : undefined,
    todos: message.todos ? [...message.todos] : undefined,
    reasoningItems: message.reasoningItems ? [...message.reasoningItems] : undefined,
    sources: message.sources ? [...message.sources] : undefined,
  }));
}

function buildConversationTitle(workspaceSnapshot, messageList, fallback = "新的分析") {
  if (workspaceSnapshot.fileName) {
    return workspaceSnapshot.fileName;
  }

  const firstUserMessage = messageList.find((message) => message.role === "user" && message.text);
  if (firstUserMessage?.text) {
    return firstUserMessage.text.slice(0, 18);
  }

  return fallback;
}

function buildConversationPreview(workspaceSnapshot, messageList) {
  const lastMessage = [...messageList].reverse().find((message) => message.text);
  if (lastMessage?.text) {
    return lastMessage.text.slice(0, 34);
  }

  if (workspaceSnapshot.summary?.summary) {
    return workspaceSnapshot.summary.summary.slice(0, 34);
  }

  if (workspaceSnapshot.fileName) {
    return "已上传音频，继续整理这段内容。";
  }

  return "上传音频后开始分析。";
}

function createConversation() {
  const id = `conversation-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;
  return {
    id,
    title: "新的分析",
    preview: "上传音频后开始分析。",
    updatedAt: Date.now(),
    workspace: defaultWorkspaceState(),
    messages: [],
  };
}

const authLoading = ref(false);
const sidebarOpen = ref(false);
const activeTranscriptionJobId = ref("");
const processingMessageId = ref("");
const summaryMessageId = ref("");
const composerText = ref("");
const loginModalVisible = ref(false);
const loginModalTab = ref("login");
const pendingAction = ref(null);
const fileInputRef = ref(null);
const messages = ref([]);
const initialConversation = createConversation();
const conversations = ref([initialConversation]);
const currentConversationId = ref(initialConversation.id);
const workLoading = reactive({
  transcribe: false,
  summary: false,
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
const workspace = reactive(defaultWorkspaceState());

const isAuthenticated = computed(() => Boolean(session.token && session.user));
const canGenerateSummary = computed(() => Boolean(workspace.transcript?.text) && !workLoading.transcribe);
const canAskQuestions = computed(() => Boolean(workspace.transcript?.text) && !workLoading.transcribe);
const canDownloadNotes = computed(
  () => Boolean(workspace.summary?.summary && ((workspace.summary?.keywords || []).length || (workspace.summary?.todos || []).length)),
);
const statusLabel = computed(() => {
  if (!isAuthenticated.value) {
    return "访客模式";
  }

  if (workLoading.transcribe) {
    return "正在转录";
  }

  if (workLoading.summary) {
    return "正在整理纪要";
  }

  if (workspace.summary) {
    return "分析完成";
  }

  if (workspace.transcript) {
    return "可继续提问";
  }

  if (workspace.file) {
    return "已上传音频";
  }

  return "等待上传";
});
const sidebarConversations = computed(() =>
  conversations.value.map((conversation) => ({
    ...conversation,
    updatedLabel: formatConversationTime(conversation.updatedAt),
  })),
);
const composerPlaceholder = computed(() => {
  if (!isAuthenticated.value) {
    return "先浏览工作台，真正开始分析时我们会提示你登录。";
  }

  if (!workspace.file) {
    return "上传音频后，你可以继续追问会议内容。";
  }

  if (workspace.summary) {
    return "继续提问这段音频，例如：这次会议有哪些明确待办？";
  }

  if (workspace.transcript) {
    return "可以追问当前音频，例如：谁负责下周跟进？";
  }

  return "先开始转录，随后即可围绕音频继续对话。";
});
const headerDescription = computed(() => {
  if (!workspace.fileName) {
    return "更紧凑的工作台会把历史会话留在左侧，把当前音频和对话操作收在右侧主区。";
  }

  return `${workspace.fileName} · ${workspace.durationLabel} · ${
    workspace.summary ? "摘要已生成，可导出会议纪要" : workspace.transcript ? "转录已完成，可生成摘要" : "等待开始处理"
  }`;
});

function notify(message, type = "success", title = "通知") {
  ElNotification({
    title,
    message,
    type,
    position: "top-right",
    duration: type === "error" ? 5000 : 2600,
  });
}

function resolveError(error, fallback) {
  return error?.response?.data?.detail || error?.message || fallback;
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

function revokeAudioUrl() {
  if (workspace.audioUrl) {
    URL.revokeObjectURL(workspace.audioUrl);
  }
}

function snapshotWorkspace() {
  return {
    file: workspace.file,
    fileName: workspace.fileName,
    audioUrl: workspace.audioUrl,
    transcript: cloneTranscript(workspace.transcript),
    summary: cloneSummary(workspace.summary),
    isDragging: false,
    transcriptionStatus: workspace.transcriptionStatus,
    completedChunks: workspace.completedChunks,
    totalChunks: workspace.totalChunks,
    durationLabel: workspace.durationLabel,
    language: workspace.language,
    summaryGeneratedAt: workspace.summaryGeneratedAt,
  };
}

function restoreWorkspace(snapshot) {
  const nextState = snapshot || defaultWorkspaceState();
  workspace.file = nextState.file || null;
  workspace.fileName = nextState.fileName || "";
  workspace.audioUrl = nextState.audioUrl || "";
  workspace.transcript = cloneTranscript(nextState.transcript);
  workspace.summary = cloneSummary(nextState.summary);
  workspace.isDragging = false;
  workspace.transcriptionStatus = nextState.transcriptionStatus || "idle";
  workspace.completedChunks = nextState.completedChunks || 0;
  workspace.totalChunks = nextState.totalChunks || 1;
  workspace.durationLabel = nextState.durationLabel || "--:--";
  workspace.language = nextState.language || "zh";
  workspace.summaryGeneratedAt = nextState.summaryGeneratedAt || "";
}

function pushMessage(role, kind, text = "", extra = {}) {
  const message = buildMessage(role, kind, text, extra);
  messages.value.push(message);
  return message.id;
}

function upsertMessage(id, patch) {
  const index = messages.value.findIndex((message) => message.id === id);
  if (index === -1) {
    return;
  }

  messages.value[index] = {
    ...messages.value[index],
    ...patch,
  };
}

function resetMessages() {
  messages.value = [];
}

function saveCurrentConversation() {
  const conversation = conversations.value.find((item) => item.id === currentConversationId.value);
  if (!conversation) {
    return;
  }

  const workspaceSnapshot = snapshotWorkspace();
  const messageSnapshot = cloneMessages(messages.value);
  conversation.workspace = workspaceSnapshot;
  conversation.messages = messageSnapshot;
  conversation.title = buildConversationTitle(workspaceSnapshot, messageSnapshot, conversation.title);
  conversation.preview = buildConversationPreview(workspaceSnapshot, messageSnapshot);
  conversation.updatedAt = Date.now();
}

function resetWorkspace() {
  revokeAudioUrl();
  activeTranscriptionJobId.value = "";
  processingMessageId.value = "";
  summaryMessageId.value = "";
  restoreWorkspace(defaultWorkspaceState());
  composerText.value = "";
  resetMessages();
}

function buildNotesMarkdown() {
  const summary = workspace.summary?.summary || "";
  const keywords = workspace.summary?.keywords || [];
  const todos = workspace.summary?.todos || [];
  const title = workspace.fileName || "meeting-notes";
  const generatedAt = formatExportDate(workspace.summaryGeneratedAt);

  return [
    `# ${title}`,
    "",
    "## 基本信息",
    `- 生成时间：${generatedAt}`,
    `- 语言：${workspace.language || "zh"}`,
    `- 音频时长：${workspace.durationLabel || "--:--"}`,
    "",
    "## 会议摘要",
    "",
    summary || "暂无摘要内容。",
    "",
    "## 关键词",
    "",
    ...(keywords.length ? keywords.map((keyword) => `- ${keyword}`) : ["- 暂无关键词"]),
    "",
    "## 待办事项",
    "",
    ...(todos.length ? todos.map((todo) => `- ${todo}`) : ["- 暂无待办事项"]),
    "",
    "_此文档由 Audio Memo 工作台自动整理导出。_",
    "",
  ].join("\n");
}

function downloadNotes() {
  if (!canDownloadNotes.value) {
    notify("请先生成摘要、关键词和待办事项，再导出会议纪要。", "warning", "暂无可导出内容");
    return;
  }

  const blob = new Blob([buildNotesMarkdown()], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${slugifyFilename(workspace.fileName || "meeting-notes")}-meeting-notes.md`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
  notify("会议纪要已导出为 Markdown 文档", "success", "导出成功");
}

function startNewAnalysis() {
  saveCurrentConversation();
  const conversation = createConversation();
  conversations.value.unshift(conversation);
  currentConversationId.value = conversation.id;
  resetWorkspace();
  sidebarOpen.value = false;
}

function selectConversation(conversationId) {
  if (conversationId === currentConversationId.value) {
    sidebarOpen.value = false;
    return;
  }

  saveCurrentConversation();
  const conversation = conversations.value.find((item) => item.id === conversationId);
  if (!conversation) {
    return;
  }

  currentConversationId.value = conversation.id;
  restoreWorkspace(conversation.workspace);
  messages.value = cloneMessages(conversation.messages);
  composerText.value = "";
  sidebarOpen.value = false;
}

function openLoginModal(action = null, tab = "login") {
  pendingAction.value = action;
  loginModalTab.value = tab;
  loginModalVisible.value = true;
}

function openFilePicker() {
  const input = fileInputRef.value;
  if (!input) {
    notify("上传控件尚未初始化，请刷新页面后重试。", "error", "无法打开文件选择器");
    return;
  }

  try {
    if (typeof input.showPicker === "function") {
      input.showPicker();
      return;
    }
  } catch {
    // Fallback to click below for browsers that expose showPicker but reject the call.
  }

  input.click();
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

  if (action.type === "upload") {
    await nextTick();
    openFilePicker();
    return;
  }

  if (action.type === "transcribe") {
    await handleTranscribe();
    return;
  }

  if (action.type === "summary") {
    await handleSummary();
    return;
  }

  if (action.type === "ask") {
    await submitPrompt();
  }
}

function isSupportedAudio(file) {
  if (!file) {
    return false;
  }

  const lowerName = file.name.toLowerCase();
  return [".wav", ".mp3", ".m4a", ".flac"].some((ext) => lowerName.endsWith(ext));
}

function getAudioDurationLabel(file) {
  return new Promise((resolve) => {
    const tempUrl = URL.createObjectURL(file);
    const audio = document.createElement("audio");
    audio.preload = "metadata";
    audio.src = tempUrl;

    const cleanup = () => {
      URL.revokeObjectURL(tempUrl);
      audio.remove();
    };

    audio.onloadedmetadata = () => {
      const duration = Number.isFinite(audio.duration) ? formatTime(audio.duration) : "--:--";
      cleanup();
      resolve(duration);
    };

    audio.onerror = () => {
      cleanup();
      resolve("--:--");
    };
  });
}

async function applySelectedFile(file) {
  revokeAudioUrl();
  activeTranscriptionJobId.value = "";
  processingMessageId.value = "";
  summaryMessageId.value = "";
  workspace.file = file || null;
  workspace.fileName = file?.name || "";
  workspace.audioUrl = file ? URL.createObjectURL(file) : "";
  workspace.transcript = null;
  workspace.summary = null;
  workspace.transcriptionStatus = "idle";
  workspace.completedChunks = 0;
  workspace.totalChunks = 1;
  workspace.durationLabel = file ? await getAudioDurationLabel(file) : "--:--";
  workspace.language = "zh";
  workspace.summaryGeneratedAt = "";
  composerText.value = "";
  resetMessages();

  if (!file) {
    return;
  }

  pushMessage("system", "upload_event", "已接收新的音频上下文。你可以先开始转录，随后再生成摘要与待办。", {
    fileName: file.name,
  });
  pushMessage("assistant", "assistant_answer", "音频已就绪。等你点击“开始转录”后，我会把结果整理成对话里的结构化卡片。");
}

async function handleFileSelect(event) {
  const [file] = event.target.files || [];
  event.target.value = "";

  if (!file) {
    return;
  }

  if (!withAuth({ type: "upload" })) {
    return;
  }

  if (!isSupportedAudio(file)) {
    notify("仅支持 wav、mp3、m4a、flac 音频文件", "warning", "文件类型不支持");
    return;
  }

  await applySelectedFile(file);
  notify("音频已加入当前工作台", "success", "上传成功");
}

async function handleUploadRequest() {
  if (!withAuth({ type: "upload" })) {
    return;
  }

  openFilePicker();
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
    notify("已退出登录", "success", "退出成功");
  }
}

function applyTranscriptionStatus(status) {
  workspace.transcriptionStatus = status.status || "processing";
  workspace.completedChunks = status.completed_chunks || 0;
  workspace.totalChunks = status.total_chunks || 1;
  workspace.language = status.language || workspace.language || "zh";
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

    if (processingMessageId.value) {
      const processingText =
        status.status === "completed"
          ? "转录完成，结果已经整理到下方。"
          : status.total_chunks > 1
            ? `正在按分段处理音频，已完成 ${status.completed_chunks || 0} / ${status.total_chunks || 1} 段。`
            : "正在处理音频内容，长音频可能需要几分钟。";
      upsertMessage(processingMessageId.value, {
        text: processingText,
        progress: {
          completed: status.completed_chunks || 0,
          total: status.total_chunks || 1,
        },
      });
    }

    if (status.status === "completed") {
      return;
    }

    if (status.status === "failed") {
      throw new Error(status.error || "转写失败");
    }

    await new Promise((resolve) => window.setTimeout(resolve, 1500));
  }
}

async function handleTranscribe() {
  if (!withAuth({ type: "transcribe" })) {
    return;
  }

  if (!workspace.file) {
    notify("请先上传音频文件", "warning", "缺少音频");
    return;
  }

  workLoading.transcribe = true;
  workspace.transcript = {
    filename: workspace.fileName,
    language: workspace.language,
    text: "",
    segments: [],
  };
  workspace.summary = null;
  workspace.summaryGeneratedAt = "";
  workspace.transcriptionStatus = "queued";
  workspace.completedChunks = 0;
  workspace.totalChunks = 1;
  processingMessageId.value = pushMessage(
    "system",
    "system_status",
    "已接收音频，开始转录。结果会按处理进度持续刷新。",
    {
      progress: { completed: 0, total: 1 },
    },
  );

  try {
    const job = await startTranscriptionJob(workspace.file);
    activeTranscriptionJobId.value = job.job_id;
    await pollTranscriptionJob(job.job_id);
    pushMessage("assistant", "assistant_answer", "转录已完成。你现在可以查看全文、浏览时间分段，或者直接生成会议摘要。");
    pushMessage("assistant", "transcript_result", "", {
      transcript: workspace.transcript,
    });
    notify("音频转录完成", "success", "转录完成");
  } catch (error) {
    if (processingMessageId.value) {
      upsertMessage(processingMessageId.value, {
        text: resolveError(error, "转录失败。请稍后重试。"),
        tone: "error",
      });
    }
    notify(resolveError(error, "转录失败。请稍后再试。"), "error", "转录失败");
  } finally {
    workLoading.transcribe = false;
    processingMessageId.value = "";
  }
}

async function handleSummary() {
  if (!withAuth({ type: "summary" })) {
    return;
  }

  if (!workspace.transcript?.text) {
    notify("请先完成音频转录", "warning", "无法生成摘要");
    return;
  }

  workLoading.summary = true;
  summaryMessageId.value = pushMessage("system", "system_status", "正在整理摘要、关键词和待办事项。");

  try {
    workspace.summary = await summarizeMeeting(workspace.transcript.text);
    workspace.summaryGeneratedAt = new Date().toISOString();
    if (summaryMessageId.value) {
      upsertMessage(summaryMessageId.value, {
        text: "结构化分析已完成，你可以继续围绕结果追问，或直接导出会议纪要。",
      });
    }
    pushMessage("assistant", "summary_result", "", {
      summary: workspace.summary.summary,
    });
    pushMessage("assistant", "keyword_result", "", {
      keywords: workspace.summary.keywords || [],
    });
    pushMessage("assistant", "todo_result", "", {
      todos: workspace.summary.todos || [],
    });
    pushMessage("assistant", "reasoning", "", {
      reasoningTitle: "查看思考过程",
      reasoningItems: [
        "识别音频中的高置信主题与反复出现的议题。",
        "优先提炼决策、风险、截止时间与责任归属。",
        "将零散表述整理成摘要、关键词和待办三个层次。",
      ],
    });
    notify("会议纪要生成完成", "success", "生成完成");
  } catch (error) {
    if (summaryMessageId.value) {
      upsertMessage(summaryMessageId.value, {
        text: resolveError(error, "摘要生成失败，请检查 API 配置。"),
        tone: "error",
      });
    }
    notify(resolveError(error, "摘要生成失败，请检查 API 配置"), "error", "摘要失败");
  } finally {
    workLoading.summary = false;
    summaryMessageId.value = "";
  }
}

async function submitPrompt() {
  const text = composerText.value.trim();
  if (!text) {
    return;
  }

  if (!withAuth({ type: "ask" })) {
    return;
  }

  pushMessage("user", "user_prompt", text);
  composerText.value = "";

  if (!workspace.file) {
    pushMessage("assistant", "assistant_answer", "可以先上传一段会议音频。我会在同一条对话里继续整理转录、摘要和后续追问。");
    return;
  }

  if (!workspace.transcript?.text) {
    pushMessage("assistant", "assistant_answer", "当前音频还没有可用转录。先开始转录，随后我就能围绕这段内容继续回答。");
    return;
  }

  pushMessage(
    "assistant",
    "assistant_answer",
    "问答界面已经就绪。当前环境还没有接入真正的 RAG 检索接口，因此这里先保留对话壳子与思考过程位置。接入后，我会基于当前音频内容直接回答你的问题，并给出引用片段。",
    {
      sources: [
        "后续可在这里展示引用到的音频片段或转录段落。",
        "也可以关联对应时间戳，支持跳回原始音频。",
      ],
    },
  );
}

function handleSuggestion(action) {
  if (action === "upload") {
    handleUploadRequest();
    return;
  }

  if (action === "transcribe") {
    handleTranscribe();
    return;
  }

  if (action === "summary") {
    handleSummary();
    return;
  }

  if (action === "download-notes") {
    downloadNotes();
    return;
  }

  if (action === "prompt-todos") {
    composerText.value = "这次会议里有哪些明确的待办事项和负责人？";
    submitPrompt();
    return;
  }

  if (action === "prompt-risk") {
    composerText.value = "请总结这段音频里的关键风险和下一步建议。";
    submitPrompt();
    return;
  }

  if (action === "reset") {
    startNewAnalysis();
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

watch(
  () => [
    messages.value,
    workspace.fileName,
    workspace.audioUrl,
    workspace.durationLabel,
    workspace.language,
    workspace.transcript,
    workspace.summary,
    workspace.transcriptionStatus,
    workspace.completedChunks,
    workspace.totalChunks,
    workspace.summaryGeneratedAt,
  ],
  () => {
    saveCurrentConversation();
  },
  { deep: true },
);

onBeforeUnmount(() => {
  revokeAudioUrl();
});
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar-shell" :class="{ 'sidebar-shell--open': sidebarOpen }">
      <SidebarNav
        :authenticated="isAuthenticated"
        :session="session"
        :conversations="sidebarConversations"
        :active-conversation-id="currentConversationId"
        @select-conversation="selectConversation"
        @new-analysis="startNewAnalysis"
        @request-login="openLoginModal()"
        @logout="handleLogout"
      />
    </aside>

    <button v-if="sidebarOpen" class="sidebar-backdrop" @click="sidebarOpen = false" />

    <main class="workspace-shell">
      <WorkspaceHeader
        :authenticated="isAuthenticated"
        :session="session"
        :status-label="statusLabel"
        :description="headerDescription"
        :file-name="workspace.fileName"
        @toggle-sidebar="sidebarOpen = true"
        @request-login="openLoginModal()"
      >
        <template #left-icon>
          <el-icon><Menu /></el-icon>
        </template>
      </WorkspaceHeader>

      <div class="workspace-body">
        <ChatWorkspace
          :messages="messages"
          :workspace="workspace"
          :can-generate-summary="canGenerateSummary"
          :can-ask-questions="canAskQuestions"
          :can-download-notes="canDownloadNotes"
          :work-loading="workLoading"
          @action="handleSuggestion"
        />
      </div>

      <AudioTray
        :workspace="workspace"
        :can-download-notes="canDownloadNotes"
        @upload="handleUploadRequest"
        @download="downloadNotes"
      />

      <ComposerBar
        v-model="composerText"
        :authenticated="isAuthenticated"
        :workspace="workspace"
        :placeholder="composerPlaceholder"
        :can-generate-summary="canGenerateSummary"
        :can-ask-questions="canAskQuestions"
        :can-download-notes="canDownloadNotes"
        :work-loading="workLoading"
        @upload="handleUploadRequest"
        @transcribe="handleTranscribe"
        @summary="handleSummary"
        @download="downloadNotes"
        @submit="submitPrompt"
      />
    </main>

    <input ref="fileInputRef" class="visually-hidden" type="file" accept=".wav,.mp3,.m4a,.flac" @change="handleFileSelect" />

    <LoginModal
      v-model:visible="loginModalVisible"
      v-model:active-tab="loginModalTab"
      :loading="authLoading"
      :login-form="loginForm"
      :register-form="registerForm"
      @login="handleLogin"
      @register="handleRegister"
    />
  </div>
</template>

<style scoped>
.app-shell {
  height: 100vh;
  display: grid;
  grid-template-columns: 272px minmax(0, 1fr);
  background: var(--app-bg);
  overflow: hidden;
}

.sidebar-shell {
  position: relative;
  z-index: 20;
  height: 100vh;
  border-right: 1px solid var(--line-soft);
  background: var(--sidebar-bg);
  overflow: hidden;
}

.workspace-shell {
  min-width: 0;
  height: 100vh;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto auto;
  background: var(--panel-bg);
  overflow: hidden;
}

.workspace-body {
  min-height: 0;
  padding: 0 22px;
  overflow: hidden;
}

.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.sidebar-backdrop {
  display: none;
}

@media (max-width: 980px) {
  .app-shell {
    grid-template-columns: 1fr;
  }

  .sidebar-shell {
    position: fixed;
    inset: 0 auto 0 0;
    height: 100vh;
    width: min(82vw, 296px);
    transform: translateX(-100%);
    transition: transform 220ms ease;
    box-shadow: var(--shadow-floating);
  }

  .sidebar-shell--open {
    transform: translateX(0);
  }

  .sidebar-backdrop {
    display: block;
    position: fixed;
    inset: 0;
    z-index: 10;
    border: 0;
    background: rgba(15, 23, 42, 0.38);
  }

  .workspace-body {
    padding: 0 12px;
  }
}
</style>
