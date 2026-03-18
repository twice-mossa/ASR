import { computed, nextTick, reactive, ref } from "vue";

import { getTranscriptionJob, startTranscriptionJob, summarizeMeeting } from "../api/meeting";
import { buildNotesMarkdown, slugifyFilename } from "../utils/workspace";

export function useMeetingWorkflow({
  workspace,
  isAuthenticated,
  withAuth,
  notify,
  resolveError,
  pushMessage,
  upsertMessage,
}) {
  const activeTranscriptionJobId = ref("");
  const processingMessageId = ref("");
  const summaryMessageId = ref("");
  const composerText = ref("");
  const workLoading = reactive({
    transcribe: false,
    summary: false,
  });

  let uploadRequestHandler = async () => {};

  const canGenerateSummary = computed(() => Boolean(workspace.transcript?.text) && !workLoading.transcribe);
  const canAskQuestions = computed(() => Boolean(workspace.transcript?.text) && !workLoading.transcribe);
  const canDownloadNotes = computed(() => Boolean(workspace.summary?.summary));
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

  function setUploadRequestHandler(handler) {
    uploadRequestHandler = handler;
  }

  function resetTransientState() {
    activeTranscriptionJobId.value = "";
    processingMessageId.value = "";
    summaryMessageId.value = "";
    composerText.value = "";
    workLoading.transcribe = false;
    workLoading.summary = false;
  }

  async function handlePendingAction(action) {
    if (!action) {
      return;
    }

    if (action.type === "upload") {
      await nextTick();
      await uploadRequestHandler();
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

  function createNotesMarkdown() {
    return buildNotesMarkdown({
      fileName: workspace.fileName,
      summary: workspace.summary?.summary || "",
      keywords: workspace.summary?.keywords || [],
      todos: workspace.summary?.todos || [],
      language: workspace.language,
      durationLabel: workspace.durationLabel,
      summaryGeneratedAt: workspace.summaryGeneratedAt,
    });
  }

  function downloadNotes() {
    if (!canDownloadNotes.value) {
      notify("请先生成摘要，再导出会议纪要。", "warning", "暂无可导出内容");
      return;
    }

    const blob = new Blob([createNotesMarkdown()], { type: "text/markdown;charset=utf-8" });
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
      uploadRequestHandler();
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
    }
  }

  return {
    canAskQuestions,
    canDownloadNotes,
    canGenerateSummary,
    composerPlaceholder,
    composerText,
    downloadNotes,
    handlePendingAction,
    handleSuggestion,
    handleSummary,
    handleTranscribe,
    headerDescription,
    resetTransientState,
    setUploadRequestHandler,
    statusLabel,
    submitPrompt,
    workLoading,
  };
}
