import { computed, nextTick, reactive, ref } from "vue";

import {
  askMeetingQuestion,
  clearMeetings,
  deleteMeeting,
  getMeetingDetail,
  getTranscriptionJob,
  sendMeetingSummaryEmail,
  startMeetingTranscriptionJob,
  stopTranscriptionJob,
  summarizeMeeting,
  updateMeeting,
} from "../api/meeting";
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
  findMessageId,
  hydrateMeetings,
}) {
  const activeTranscriptionJobId = ref("");
  const processingMessageId = ref("");
  const summaryMessageId = ref("");
  const transcriptMessageId = ref("");
  const composerText = ref("");
  const workLoading = reactive({
    transcribe: false,
    stopTranscribe: false,
    summary: false,
    ask: false,
    email: false,
    deleteHistory: false,
  });

  let uploadRequestHandler = async () => {};
  const canUseTranscript = computed(() => ["transcribed", "summarized"].includes(workspace.meetingStatus));

  const isUploading = computed(() => ["preparing", "uploading"].includes(workspace.uploadStatus));
  const canGenerateSummary = computed(
    () => Boolean(workspace.meetingId && canUseTranscript.value) && !workLoading.transcribe && !isUploading.value,
  );
  const canAskQuestions = computed(
    () => Boolean(workspace.meetingId && canUseTranscript.value) && !workLoading.transcribe && !workLoading.ask && !isUploading.value,
  );
  const canDownloadNotes = computed(() => Boolean(workspace.summary?.summary));
  const canStopTranscription = computed(() =>
    Boolean(workspace.transcriptionJob?.job_id) &&
    ["queued", "processing", "stopping"].includes(workspace.transcriptionStatus) &&
    !isUploading.value,
  );
  const statusLabel = computed(() => {
    if (!isAuthenticated.value) {
      return "访客模式";
    }

    if (workspace.uploadStatus === "preparing") {
      return "准备上传";
    }

    if (workspace.uploadStatus === "uploading") {
      return `上传中 ${workspace.uploadPercent || 0}%`;
    }

    if (workspace.transcriptionStatus === "stopping" || workLoading.stopTranscribe) {
      return "正在停止";
    }

    if (workLoading.transcribe || ["transcribing", "processing", "queued"].includes(workspace.transcriptionStatus)) {
      return "正在转录";
    }

    if (workLoading.summary) {
      return "正在整理纪要";
    }

    if (workLoading.ask) {
      return "正在回答问题";
    }

    if (["processing", "pending"].includes(workspace.knowledgeStatus)) {
      return "整理知识包";
    }

    if (workLoading.email) {
      return "正在发送邮件";
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

    if (workspace.transcriptionStatus === "stopped" || workspace.meetingStatus === "stopped") {
      return "已停止";
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
      return isUploading.value
        ? "正在上传音频并创建会议记录，请稍候。"
        : "上传音频后，系统会先创建可持久化的会议记录。";
    }

    if (workspace.uploadStatus === "preparing") {
      return "正在读取音频信息并准备上传。";
    }

    if (workspace.uploadStatus === "uploading") {
      return `正在上传音频文件，当前进度 ${workspace.uploadPercent || 0}%。`;
    }

    if (["queued", "processing", "transcribing", "stopping"].includes(workspace.transcriptionStatus)) {
      return "转录进行中，系统会逐段刷新文本；完整结束后再开放摘要和问答。";
    }

    if (!canUseTranscript.value) {
      return "先开始转录，随后即可围绕当前会议继续提问。";
    }

    if (["processing", "pending"].includes(workspace.knowledgeStatus)) {
      return "正在整理会议主题和证据块，问答很快会更快更稳。";
    }

    return "围绕当前会议继续提问，我会结合转写片段给出回答和引用依据。";
  });
  const headerDescription = computed(() => {
    if (workspace.uploadStatus === "preparing") {
      return "正在读取音频时长并准备上传，会议记录会在上传完成后自动创建。";
    }

    if (workspace.uploadStatus === "uploading") {
      return `${workspace.fileName || "当前音频"} · 正在上传并创建会议记录，进度 ${workspace.uploadPercent || 0}%`;
    }

    if (!workspace.fileName) {
      return "历史会议保留在左侧，当前工作区展示真实持久化的音频、转录和纪要结果。";
    }

    const stateText =
      workspace.transcriptionStatus === "summarized"
        ? "摘要已生成，可继续追问会议细节"
        : workspace.transcriptionStatus === "transcribed"
          ? "转录已完成，可继续追问或生成摘要"
          : workspace.transcriptionStatus === "stopping"
            ? "正在停止转录，当前结果会保留"
            : ["transcribing", "processing", "queued"].includes(workspace.transcriptionStatus)
              ? "正在处理中，转录内容会逐段刷新"
              : ["processing", "pending"].includes(workspace.knowledgeStatus)
                ? "正在整理会议主题和证据块"
              : workspace.transcriptionStatus === "stopped"
                ? "转录已停止，可重新发起转录"
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
    transcriptMessageId.value = "";
    composerText.value = "";
    workLoading.transcribe = false;
    workLoading.stopTranscribe = false;
    workLoading.summary = false;
    workLoading.ask = false;
    workLoading.email = false;
    workLoading.deleteHistory = false;
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

    if (action.type === "stop-transcribe") {
      await handleStopTranscribe();
      return;
    }

    if (action.type === "send-summary-email") {
      await handleSendSummaryEmail();
      return;
    }

    if (action.type === "ask") {
      await submitPrompt();
      return;
    }

    if (action.type === "seek-audio") {
      workspace.audioSeekTo = Number(action.seconds) || 0;
      workspace.audioSeekNonce += 1;
      return;
    }

    if (action.type === "delete-meeting") {
      await handleDeleteMeeting(action.meetingId);
      return;
    }

    if (action.type === "clear-meetings") {
      await handleClearMeetings();
    }
  }

  function applyTranscriptionStatus(status) {
    workspace.transcriptionStatus = status.status || "transcribing";
    workspace.completedChunks = status.completed_chunks || 0;
    workspace.totalChunks = status.total_chunks || 1;
    workspace.language = status.language || workspace.language || "zh";
    workspace.transcriptionJob = {
      ...status,
      segments: status.segments || [],
    };
    workspace.transcript = {
      filename: status.filename || workspace.fileName,
      language: status.language || "zh",
      text: status.text || "",
      segments: status.segments || [],
    };
    if (status.status === "completed") {
      workspace.meetingStatus = "transcribed";
    } else if (status.status === "stopped") {
      workspace.meetingStatus = "stopped";
    } else if (status.status === "failed") {
      workspace.meetingStatus = "failed";
    } else {
      workspace.meetingStatus = "transcribing";
    }
    workspace.error = status.error || "";
  }

  function upsertTranscriptPreview(status) {
    if (!status.text && !(status.segments || []).length) {
      return;
    }

    const patch = {
      transcript: {
        filename: status.filename || workspace.fileName,
        language: status.language || "zh",
        text: status.text || "",
        segments: status.segments || [],
      },
    };

    if (!transcriptMessageId.value) {
      transcriptMessageId.value = pushMessage("assistant", "transcript_result", "", patch);
      return;
    }

    upsertMessage(transcriptMessageId.value, patch);
  }

  async function pollTranscriptionJob(jobId) {
    while (activeTranscriptionJobId.value === jobId) {
      const status = await getTranscriptionJob(jobId);
      applyTranscriptionStatus(status);
      upsertTranscriptPreview(status);

      if (processingMessageId.value) {
        const processingText =
          status.status === "completed"
            ? "转录完成，结果已经保存到当前会议。"
            : status.status === "stopped"
              ? "转录已停止，已保留当前识别出的内容。"
            : status.status === "stopping"
              ? "正在停止转录，当前已识别内容会保留。"
            : status.total_chunks > 1
              ? `正在按分段处理音频，已完成 ${status.completed_chunks || 0} / ${status.total_chunks || 1} 段，已识别内容会立即显示。`
              : "正在处理音频内容，已识别内容会立即显示。";
        upsertMessage(processingMessageId.value, {
          text: processingText,
          progress: {
            completed: status.completed_chunks || 0,
            total: status.total_chunks || 1,
          },
          progressMeta: {
            status: status.status || "processing",
          },
        });
      }

      if (status.status === "completed") {
        workspace.transcriptionStatus = "transcribed";
        workspace.meetingStatus = "transcribed";
        return;
      }

      if (status.status === "stopped") {
        workspace.transcriptionStatus = "stopped";
        workspace.meetingStatus = "stopped";
        return;
      }

      if (status.status === "failed") {
        workspace.transcriptionStatus = "failed";
        workspace.meetingStatus = "failed";
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
    workspace.meetingStatus = "transcribing";
    workspace.completedChunks = 0;
    workspace.totalChunks = 1;
    workspace.error = "";
    workspace.transcriptionJob = null;
    transcriptMessageId.value = "";
    processingMessageId.value = pushMessage(
      "system",
      "system_status",
      "已接收转录请求，结果会在当前会议记录里逐段刷新并保存。",
      {
        progress: { completed: 0, total: 1 },
        progressMeta: { status: "queued" },
      },
    );

    try {
      const job = await startMeetingTranscriptionJob(session.token, workspace.meetingId);
      activeTranscriptionJobId.value = job.job_id;
      await pollTranscriptionJob(job.job_id);
      await refreshCurrentMeeting();
      if (workspace.meetingStatus === "transcribed") {
        pushMessage("assistant", "assistant_answer", "转录已完成。你现在可以查看全文、浏览时间分段，或者直接生成会议摘要。");
        if (!transcriptMessageId.value) {
          transcriptMessageId.value = pushMessage("assistant", "transcript_result", "", {
            transcript: workspace.transcript,
          });
        }
        notify("音频转录完成", "success", "转录完成");
      } else if (workspace.meetingStatus === "stopped") {
        notify("转录已停止，已保留当前已识别内容", "warning", "已停止");
      }
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
      workLoading.stopTranscribe = false;
      activeTranscriptionJobId.value = "";
      processingMessageId.value = "";
      await hydrateMeetings(session.token, workspace.meetingId);
    }
  }

  async function handleStopTranscribe() {
    if (!withAuth({ type: "stop-transcribe" })) {
      return;
    }

    if (!workspace.transcriptionJob?.job_id || !canStopTranscription.value) {
      return;
    }

    workLoading.stopTranscribe = true;
    workspace.transcriptionStatus = "stopping";

    try {
      const status = await stopTranscriptionJob(session.token, workspace.transcriptionJob.job_id);
      applyTranscriptionStatus(status);
    } catch (error) {
      notify(resolveError(error, "停止转录失败，请稍后重试。"), "error", "停止失败");
      workLoading.stopTranscribe = false;
    }
  }

  async function handleDeleteMeeting(meetingId = workspace.meetingId) {
    if (!withAuth({ type: "delete-meeting" })) {
      return;
    }

    if (!meetingId) {
      return;
    }

    const confirmed = window.confirm("删除后，这场会议的音频、转录、摘要和问答记录都会移除，确认删除吗？");
    if (!confirmed) {
      return;
    }

    workLoading.deleteHistory = true;
    try {
      await deleteMeeting(session.token, meetingId);
      if (workspace.meetingId === meetingId) {
        resetTransientState();
      }
      await hydrateMeetings(session.token);
      notify("会议记录已删除", "success", "删除成功");
    } catch (error) {
      notify(resolveError(error, "删除会议失败，请稍后重试。"), "error", "删除失败");
    } finally {
      workLoading.deleteHistory = false;
    }
  }

  async function handleRenameMeeting(meetingId = workspace.meetingId, currentTitle = "") {
    if (!withAuth({ type: "rename-meeting", meetingId })) {
      return;
    }

    if (!meetingId) {
      return;
    }

    const nextTitle = window.prompt("输入新的会议标题", currentTitle || workspace.fileName || "");
    if (nextTitle === null) {
      return;
    }

    const normalizedTitle = nextTitle.trim();
    if (!normalizedTitle || normalizedTitle === currentTitle) {
      return;
    }

    try {
      const detail = await updateMeeting(session.token, meetingId, { title: normalizedTitle });
      if (workspace.meetingId === meetingId) {
        applyMeetingDetail(detail, workspace.file);
      }
      await hydrateMeetings(session.token, meetingId);
      notify("会议标题已更新", "success", "更新成功");
    } catch (error) {
      notify(resolveError(error, "更新会议标题失败，请稍后重试。"), "error", "更新失败");
    }
  }

  async function handleClearMeetings() {
    if (!withAuth({ type: "clear-meetings" })) {
      return;
    }

    const confirmed = window.confirm("这会清空当前账号的全部历史会议记录，确认继续吗？");
    if (!confirmed) {
      return;
    }

    workLoading.deleteHistory = true;
    try {
      await clearMeetings(session.token);
      resetTransientState();
      await hydrateMeetings(session.token);
      notify("历史会议已清空", "success", "清空成功");
    } catch (error) {
      notify(resolveError(error, "清空历史会议失败，请稍后重试。"), "error", "清空失败");
    } finally {
      workLoading.deleteHistory = false;
    }
  }

  async function resumeActiveTranscriptionIfNeeded() {
    const jobId = workspace.transcriptionJob?.job_id;
    if (!jobId || activeTranscriptionJobId.value === jobId) {
      return;
    }

    if (!["queued", "processing", "stopping"].includes(workspace.transcriptionStatus)) {
      return;
    }

    processingMessageId.value = findMessageId("system_status");
    transcriptMessageId.value = findMessageId("transcript_result");
    activeTranscriptionJobId.value = jobId;
    workLoading.transcribe = true;

    try {
      await pollTranscriptionJob(jobId);
      await refreshCurrentMeeting();
    } catch (error) {
      notify(resolveError(error, "转录状态同步失败，请稍后重试。"), "error", "转录同步失败");
    } finally {
      workLoading.transcribe = false;
      workLoading.stopTranscribe = false;
      activeTranscriptionJobId.value = "";
    }
  }

  async function handleSummary() {
    if (!withAuth({ type: "summary" })) {
      return;
    }

    if (!workspace.meetingId || !canUseTranscript.value) {
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
      workspace.meetingStatus = "summarized";
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
        reasoningTitle: "查看摘要依据",
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

  async function handleSendSummaryEmail() {
    if (!withAuth({ type: "send-summary-email" })) {
      return;
    }

    if (!workspace.meetingId || !workspace.summary?.summary) {
      notify("请先生成摘要，再发送会议纪要。", "warning", "暂无可发送内容");
      return;
    }

    if (!workspace.summaryEmail?.enabled) {
      notify("当前环境未启用邮件发送。", "warning", "无法发送");
      return;
    }

    workLoading.email = true;

    try {
      const result = await sendMeetingSummaryEmail(session.token, workspace.meetingId);
      await refreshCurrentMeeting();
      notify(`会议纪要已发送到 ${result.recipient_email}`, "success", "发送成功");
    } catch (error) {
      await refreshCurrentMeeting();
      notify(resolveError(error, "邮件发送失败，请稍后重试。"), "error", "发送失败");
    } finally {
      workLoading.email = false;
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

    if (!workspace.meetingId) {
      pushMessage("assistant", "assistant_answer", "可以先上传一段会议音频。系统会先把音频保存成持久化会议记录，再继续整理转录和纪要。");
      return;
    }

    if (!canUseTranscript.value) {
      pushMessage("assistant", "assistant_answer", "当前会议还没有可用转录。先开始转录，随后我就能围绕这段内容继续回答。");
      return;
    }

    workLoading.ask = true;
    const pendingId = pushMessage("system", "system_status", "正在结合当前会议转写内容整理回答。");

    try {
      const result = await askMeetingQuestion(session.token, workspace.meetingId, text);
      upsertMessage(pendingId, {
        text: "回答已生成，下面附上主题结论和证据块。",
      });
      pushMessage("assistant", "qa_answer", "", {
        answer: result.answer,
        citations: result.citations || [],
        answerType: result.answer_type || "fact",
        topicLabels: result.topic_labels || [],
        evidenceBlocks: result.evidence_blocks || [],
        reasoningTitle: result.reasoning_summary ? "查看回答依据" : "",
        reasoningItems: result.reasoning_summary ? [result.reasoning_summary] : [],
      });
      await hydrateMeetings(session.token, workspace.meetingId);
    } catch (error) {
      upsertMessage(pendingId, {
        text: resolveError(error, "提问失败，请稍后重试。"),
        tone: "error",
      });
      notify(resolveError(error, "提问失败，请稍后重试。"), "error", "问答失败");
    } finally {
      workLoading.ask = false;
    }
  }

  function handleSuggestion(action) {
    if (action && typeof action === "object") {
      handlePendingAction(action);
      return;
    }

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

    if (action === "stop-transcribe") {
      handleStopTranscribe();
      return;
    }

    if (action === "send-summary-email") {
      handleSendSummaryEmail();
      return;
    }

    if (action === "download-notes") {
      downloadNotes();
      return;
    }

    if (action === "prompt-todos") {
      composerText.value = "请根据这场会议内容，梳理待办事项的负责人和下一步动作。";
      submitPrompt();
      return;
    }

    if (action === "prompt-risk") {
      composerText.value = "请结合会议内容，概括当前最关键的风险和建议的下一步。";
      submitPrompt();
      return;
    }

    if (action === "delete-current-meeting") {
      handleDeleteMeeting();
      return;
    }

    if (action === "clear-meetings") {
      handleClearMeetings();
    }
  }

  return {
    canAskQuestions,
    canDownloadNotes,
    canGenerateSummary,
    canStopTranscription,
    composerPlaceholder,
    composerText,
    downloadNotes,
    handleClearMeetings,
    handleDeleteMeeting,
    handleRenameMeeting,
    handlePendingAction,
    handleSendSummaryEmail,
    handleSuggestion,
    handleSummary,
    handleStopTranscribe,
    handleTranscribe,
    headerDescription,
    resumeActiveTranscriptionIfNeeded,
    resetTransientState,
    setUploadRequestHandler,
    statusLabel,
    submitPrompt,
    workLoading,
  };
}
