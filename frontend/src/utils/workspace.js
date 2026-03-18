export function safeParse(raw) {
  if (!raw) {
    return null;
  }

  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function formatTime(seconds) {
  if (!Number.isFinite(seconds)) {
    return "--:--";
  }

  const totalSeconds = Math.max(0, Math.round(seconds));
  const minutes = String(Math.floor(totalSeconds / 60)).padStart(2, "0");
  const remainSeconds = String(totalSeconds % 60).padStart(2, "0");
  return `${minutes}:${remainSeconds}`;
}

export function formatConversationTime(timestamp) {
  const date = timestamp ? new Date(timestamp) : new Date();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");
  return `${month}-${day} ${hours}:${minutes}`;
}

export function formatExportDate(value) {
  const date = value ? new Date(value) : new Date();
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");
  return `${year}-${month}-${day} ${hours}:${minutes}`;
}

export function slugifyFilename(value) {
  return (value || "meeting-notes")
    .replace(/\.[^/.]+$/, "")
    .replace(/[^\w\u4e00-\u9fa5-]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "")
    .toLowerCase();
}

export function buildMessage(role, kind, text = "", extra = {}) {
  return {
    id: `${kind}-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
    role,
    kind,
    text,
    createdAt: Date.now(),
    ...extra,
  };
}

export function defaultWorkspaceState() {
  return {
    meetingId: null,
    file: null,
    fileName: "",
    audioUrl: "",
    persistedAudioUrl: "",
    transcript: null,
    summary: null,
    isDragging: false,
    transcriptionStatus: "idle",
    completedChunks: 0,
    totalChunks: 1,
    durationLabel: "--:--",
    language: "zh",
    summaryGeneratedAt: "",
    error: "",
  };
}

export function cloneTranscript(transcript) {
  if (!transcript) {
    return null;
  }

  return {
    ...transcript,
    segments: (transcript.segments || []).map((segment) => ({ ...segment })),
  };
}

export function cloneSummary(summary) {
  if (!summary) {
    return null;
  }

  return {
    ...summary,
    keywords: [...(summary.keywords || [])],
    todos: [...(summary.todos || [])],
  };
}

export function cloneMessages(list) {
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

export function buildNotesMarkdown({ fileName, summary, keywords, todos, language, durationLabel, summaryGeneratedAt }) {
  const title = fileName || "meeting-notes";
  const generatedAt = formatExportDate(summaryGeneratedAt);

  return [
    `# ${title}`,
    "",
    "## 基本信息",
    `- 生成时间：${generatedAt}`,
    `- 语言：${language || "zh"}`,
    `- 音频时长：${durationLabel || "--:--"}`,
    "",
    "## 会议摘要",
    "",
    summary || "暂无摘要内容。",
    "",
    "## 关键词",
    "",
    ...((keywords || []).length ? keywords.map((keyword) => `- ${keyword}`) : ["- 暂无关键词"]),
    "",
    "## 待办事项",
    "",
    ...((todos || []).length ? todos.map((todo) => `- ${todo}`) : ["- 暂无待办事项"]),
    "",
    "_此文档由 Audio Memo 工作台自动整理导出。_",
    "",
  ].join("\n");
}
