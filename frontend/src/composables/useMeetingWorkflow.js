import { computed, nextTick, reactive, ref } from "vue";

import { getMeetingDetail, getTranscriptionJob, startMeetingTranscriptionJob, summarizeMeeting } from "../api/meeting";
import { buildNotesMarkdown, slugifyFilename } from "../utils/workspace";

export function useMeetingWorkflow({
  workspace,
  session,
  isAuthenticated,
  withAuth,
  notify,
  resolveError,
  pushMessage,
  upsertMessage,
  applyMeetingDetail,
  hydrateMeetings,
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

  const canGenerateSummary = computed(
    () => Boolean(workspace.meetingId && workspace.transcript?.text) && !workLoading.transcribe,
  );
  const canAskQuestions = computed(() => Boolean(workspace.meetingId && workspace.transcript?.text) && !workLoading.transcribe);
  const canDownloadNotes = computed(() => Boolean(workspace.summary?.summary));
  const statusLabel = computed(() => {
    if (!isAuthenticated.value) {
      return "访客模式";
    }

    if (workLoading.transcribe || workspace.transcriptionStatus === "transcribing") {
      return "正在转录";
    }

    if (workLoading.summary) {
      return "正在整理纪要";
    }

    if (workspace.transcriptionStatus === "summarized") {
      return "分析完成";
    }

    if (workspace.transcriptionStatus === "transcribed") {
      return "可生成摘要";
    }

    if (workspace.transcriptionStatus === "failed") {
      return "处理失败";
    }

    if (workspace.meetingId) {
      return "已保存会议";
    }

    return "等待上传";
  });
  const composerPlaceholder = computed(() => {
    if (!isAuthenticated.value) {
      return "先浏览工作台，真正开始分析时我们会提示你登录。";
    }

    if (!workspace.meetingId) {
      return "上传音频后，系统会先创建可持久化的会议记录。";
    }

    if (!workspace.transcript?.text) {
      return "先开始转录，随后即可围绕当前会议继续提问。";
    }

    return "问答入口已预留，真实检索问答能力将在下一阶段接入。";
  });
  const headerDescription = computed(() => {
    if (!workspace.fileName) {
      return "历史会议保留在左侧，当前工作区展示真实持久化的音频、转录和纪要结果。";
    }

    const stateText =
      workspace.transcriptionStatus === "summarized"
        ? "摘要已生成，可导出会议纪要"
        : workspace.transcriptionStatus === "transcribed"
          ? "转录已完成，可生成摘要"
          : workspace.transcriptionStatus === "transcribing"
            ? "正在处理中，刷新页面后仍可继续查看"
            : workspace.transcriptionStatus === "failed"
              ? "本次处理失败，可重新发起转录"
              : "会议记录已创建，等待开始转录";

    return `${workspace.fileName} · ${workspace.durationLabel} · ${stateText}`;
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

  async function refreshCurrentMeeting() {
    if (!session.token || !workspace.meetingId) {
      return;
    }

    const detail = await getMeetingDetail(session.token, workspace.meetingId);
    applyMeetingDetail(detail, workspace.file);
    await hydrateMeetings(session.token, detail.id);
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
    workspace.transcriptionStatus = status.status || "transcribing";
    workspace.completedChunks = status.completed_chunks || 0;
    workspace.totalChunks = status.total_chunks || 1;
    workspace.language = status.language || workspace.language || "zh";
    workspace.transcript = {
      filename: status.filename || workspace.fileName,
      language: status.language || "zh",
      text: status.text || "",
      segments: status.segments || [],
    };
    workspace.error = status.error || "";
  }

  async function pollTranscriptionJob(jobId) {
    while (activeTranscriptionJobId.value === jobId) {
      const status = await getTranscriptionJob(jobId);
      applyTranscriptionStatus(status);

      if (processingMessageId.value) {
        const processingText =
          status.status === "completed"
            ? "转录完成，结果已经保存到当前会议。"
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
        workspace.transcriptionStatus = "transcribed";
        return;
      }

      if (status.status === "failed") {
        workspace.transcriptionStatus = "failed";
        throw new Error(status.error || "转写失败");
      }

      await new Promise((resolve) => window.setTimeout(resolve, 1500));
    }
  }

  async function handleTranscribe() {
    if (!withAuth({ type: "transcribe" })) {
      return;
    }

    if (!workspace.meetingId) {
      notify("请先上传音频文件", "warning", "缺少音频");
      return;
    }

    workLoading.transcribe = true;
    workspace.summary = null;
    workspace.summaryGeneratedAt = "";
    workspace.transcriptionStatus = "transcribing";
    workspace.completedChunks = 0;
    workspace.totalChunks = 1;
    workspace.error = "";
    processingMessageId.value = pushMessage(
      "system",
      "system_status",
      "已接收转录请求，结果会在当前会议记录里持续刷新并保存。",
      {
        progress: { completed: 0, total: 1 },
      },
    );

    try {
      const job = await startMeetingTranscriptionJob(session.token, workspace.meetingId);
      activeTranscriptionJobId.value = job.job_id;
      await pollTranscriptionJob(job.job_id);
      await refreshCurrentMeeting();
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
      await hydrateMeetings(session.token, workspace.meetingId);
    }
  }

  async function handleSummary() {
    if (!withAuth({ type: "summary" })) {
      return;
    }

    if (!workspace.meetingId || !workspace.transcript?.text) {
      notify("请先完成音频转录", "warning", "无法生成摘要");
      return;
    }

    workLoading.summary = true;
    summaryMessageId.value = pushMessage("system", "system_status", "正在整理摘要、关键词和待办事项。");

    try {
      workspace.summary = await summarizeMeeting({
        token: session.token,
        meetingId: workspace.meetingId,
      });
      workspace.summaryGeneratedAt = new Date().toISOString();
      workspace.transcriptionStatus = "summarized";
      if (summaryMessageId.value) {
        upsertMessage(summaryMessageId.value, {
          text: "结构化分析已完成，并已保存到当前会议记录。",
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
        reasoningTitle: "查看整理思路",
        reasoningItems: [
          "先识别音频中的主题、决策和风险点。",
          "再提炼高频关键词和可执行事项。",
          "最后按摘要、关键词、待办三个层次组织输出。",
        ],
      });
      await hydrateMeetings(session.token, workspace.meetingId);
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

    if (!workspace.meetingId) {
      pushMessage("assistant", "assistant_answer", "可以先上传一段会议音频。系统会先把音频保存成持久化会议记录，再继续整理转录和纪要。");
      return;
    }

    if (!workspace.transcript?.text) {
      pushMessage("assistant", "assistant_answer", "当前会议还没有可用转录。先开始转录，随后我就能围绕这段内容继续回答。");
      return;
    }

    pushMessage(
      "assistant",
      "assistant_answer",
      "真实问答能力将在下一阶段接入。当前这一轮已经先把会议记录、转录结果和摘要结果持久化，后续会基于这些数据再接检索问答与引用定位。",
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
      composerText.value = "等真实问答接入后，我想先追问待办事项和负责人。";
      submitPrompt();
      return;
    }

    if (action === "prompt-risk") {
      composerText.value = "等真实问答接入后，我想先追问关键风险和下一步建议。";
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
