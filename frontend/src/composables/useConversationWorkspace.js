import { computed, reactive, ref } from "vue";

import { getMeetingDetail, listMeetings } from "../api/meeting";
import {
  buildMessage,
  cloneMessages,
  cloneSummary,
  cloneSummaryEmail,
  cloneTranscriptionJob,
  cloneTranscript,
  defaultWorkspaceState,
  formatConversationTime,
} from "../utils/workspace";

function normalizeAudioUrl(audioUrl) {
  if (!audioUrl) {
    return "";
  }
  if (audioUrl.startsWith("http://") || audioUrl.startsWith("https://") || audioUrl.startsWith("blob:")) {
    return audioUrl;
  }
  return audioUrl;
}

export function useConversationWorkspace({ notify, resolveError }) {
  const messages = ref([]);
  const conversations = ref([]);
  const currentConversationId = ref(null);
  const workspace = reactive(defaultWorkspaceState());

  const sidebarConversations = computed(() =>
    conversations.value.map((conversation) => ({
      ...conversation,
      updatedLabel: formatConversationTime(conversation.updated_at),
    })),
  );

  function revokeAudioUrl() {
    if (workspace.audioUrl?.startsWith("blob:")) {
      URL.revokeObjectURL(workspace.audioUrl);
    }
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

  function resetWorkspaceState() {
    revokeAudioUrl();
    Object.assign(workspace, defaultWorkspaceState());
    resetMessages();
    currentConversationId.value = null;
  }

  function mapConversation(meeting) {
    return {
      id: meeting.id,
      title: meeting.title || meeting.filename,
      preview: meeting.preview || "已上传音频，等待转录。",
      updated_at: meeting.updated_at,
      status: meeting.status,
    };
  }

  function upsertSidebarConversation(meetingDetail) {
    const preview =
      meetingDetail.summary?.summary ||
      ((meetingDetail.transcription_job?.status || meetingDetail.status) === "stopping"
        ? "正在停止转录，当前结果会保留。"
        : meetingDetail.status === "transcribing"
        ? "正在转录，已识别内容会持续刷新。"
        : meetingDetail.status === "stopped"
        ? "已停止转录，保留了当前已识别内容。"
        : meetingDetail.transcript?.text
        ? meetingDetail.status === "summarized"
          ? "已生成摘要，可继续追问会议细节。"
          : "已完成转录，可继续追问会议内容。"
        : meetingDetail.error || "已上传音频，等待转录。");

    const nextItem = {
      id: meetingDetail.id,
      title: meetingDetail.title || meetingDetail.filename,
      preview,
      updated_at: meetingDetail.updated_at,
      status: meetingDetail.status,
    };
    const index = conversations.value.findIndex((item) => item.id === meetingDetail.id);
    if (index === -1) {
      conversations.value.unshift(nextItem);
      return;
    }

    conversations.value[index] = nextItem;
    conversations.value = [...conversations.value].sort((left, right) => new Date(right.updated_at) - new Date(left.updated_at));
  }

  function rebuildMessages(meetingDetail) {
    const nextMessages = [];

    if (!meetingDetail) {
      messages.value = [];
      return;
    }

    if (meetingDetail.status === "draft") {
      nextMessages.push(
        buildMessage("system", "upload_event", "已接收新的音频上下文。你可以先开始转录，随后再生成摘要与待办。", {
          fileName: meetingDetail.filename,
        }),
      );
      nextMessages.push(
        buildMessage("assistant", "assistant_answer", "音频已保存到当前会议记录。等你点击“开始转录”后，我会把结果整理成对话里的结构化卡片。"),
      );
    }

    if (meetingDetail.status === "transcribing") {
      nextMessages.push(
        buildMessage(
          "system",
          "system_status",
          meetingDetail.transcription_job?.status === "stopping"
            ? "正在停止转录，当前已识别内容会保留。"
            : "正在处理音频内容，转录结果会逐段刷新并自动保存。",
          {
          progress: {
            completed: meetingDetail.transcription_job?.completed_chunks || 0,
            total: meetingDetail.transcription_job?.total_chunks || 1,
          },
          progressMeta: {
            status: meetingDetail.transcription_job?.status || "processing",
          },
          },
        ),
      );
    }

    if (meetingDetail.status === "stopped") {
      nextMessages.push(
        buildMessage("system", "system_status", "转录已停止，本次保留了当前已识别内容。"),
      );
    }

    if (meetingDetail.transcript?.text) {
      if (meetingDetail.status === "transcribed" || meetingDetail.status === "summarized") {
        nextMessages.push(
          buildMessage("assistant", "assistant_answer", "转录已完成。你现在可以查看全文、浏览时间分段，或者直接生成会议摘要。"),
        );
      }
      nextMessages.push(
        buildMessage("assistant", "transcript_result", "", {
          transcript: meetingDetail.transcript,
        }),
      );
    }

    if (meetingDetail.summary) {
      nextMessages.push(
        buildMessage("system", "system_status", "结构化纪要已经保存。刷新页面或切换回来时都可以继续查看。"),
      );
      nextMessages.push(buildMessage("assistant", "summary_result", "", { summary: meetingDetail.summary.summary }));
      nextMessages.push(buildMessage("assistant", "keyword_result", "", { keywords: meetingDetail.summary.keywords || [] }));
      nextMessages.push(buildMessage("assistant", "todo_result", "", { todos: meetingDetail.summary.todos || [] }));
      nextMessages.push(
        buildMessage("assistant", "reasoning", "", {
          reasoningTitle: "查看摘要依据",
          reasoningItems: [
            "先抽取会议主议题与关键决策。",
            "再识别反复出现的重点术语和风险点。",
            "最后把可执行事项整理成待办列表。",
          ],
        }),
      );
    }

    if (["processing", "pending"].includes(meetingDetail.knowledge_status || "")) {
      nextMessages.push(buildMessage("system", "system_status", "正在整理会议主题和证据块，后续追问会更快更稳。"));
    }

    if (meetingDetail.error) {
      nextMessages.push(buildMessage("system", "system_status", meetingDetail.error, { tone: "error" }));
    }

    for (const qaRecord of meetingDetail.qa_records || []) {
      nextMessages.push(buildMessage("user", "user_prompt", qaRecord.question, { createdAt: Date.parse(qaRecord.created_at) || Date.now() }));
      nextMessages.push(
        buildMessage("assistant", "qa_answer", "", {
          answer: qaRecord.answer,
          citations: qaRecord.citations || [],
          answerType: qaRecord.answer_type || "fact",
          topicLabels: qaRecord.topic_labels || [],
          evidenceBlocks: qaRecord.evidence_blocks || [],
          reasoningTitle: qaRecord.reasoning_summary ? "查看回答依据" : "",
          reasoningItems: qaRecord.reasoning_summary ? [qaRecord.reasoning_summary] : [],
          createdAt: Date.parse(qaRecord.created_at) || Date.now(),
        }),
      );
    }

    messages.value = cloneMessages(nextMessages);
  }

  function applyMeetingDetail(meetingDetail, localFile = null) {
    revokeAudioUrl();
    workspace.meetingId = meetingDetail.id;
    workspace.meetingStatus = meetingDetail.status || "draft";
    workspace.file = localFile;
    workspace.fileName = meetingDetail.filename || "";
    workspace.persistedAudioUrl = normalizeAudioUrl(meetingDetail.audio_url);
    workspace.audioUrl = localFile ? URL.createObjectURL(localFile) : normalizeAudioUrl(meetingDetail.audio_url);
    workspace.transcript = cloneTranscript(meetingDetail.transcript);
    workspace.transcriptionJob = cloneTranscriptionJob(meetingDetail.transcription_job);
    workspace.summary = cloneSummary(meetingDetail.summary);
    workspace.isDragging = false;
    workspace.transcriptionStatus = meetingDetail.transcription_job?.status || meetingDetail.status || "draft";
    workspace.completedChunks = meetingDetail.transcription_job?.completed_chunks || 0;
    workspace.totalChunks = meetingDetail.transcription_job?.total_chunks || 1;
    workspace.durationLabel = meetingDetail.duration_label || "--:--";
    workspace.language = meetingDetail.language || "zh";
    workspace.summaryGeneratedAt = meetingDetail.updated_at || "";
    workspace.summaryEmail = cloneSummaryEmail(meetingDetail.summary_email);
    workspace.knowledgeStatus = meetingDetail.knowledge_status || "idle";
    workspace.error = meetingDetail.error || "";
    workspace.audioSeekTo = null;
    workspace.audioSeekNonce = 0;
    currentConversationId.value = meetingDetail.id;
    upsertSidebarConversation(meetingDetail);
    rebuildMessages(meetingDetail);
  }

  async function hydrateMeetings(token, preferredMeetingId = null) {
    if (!token) {
      conversations.value = [];
      resetWorkspaceState();
      return;
    }

    try {
      const items = await listMeetings(token);
      conversations.value = items.map(mapConversation);

      const nextMeetingId = preferredMeetingId || currentConversationId.value || conversations.value[0]?.id || null;
      if (!nextMeetingId) {
        resetWorkspaceState();
        conversations.value = items.map(mapConversation);
        return;
      }

      await selectConversation(nextMeetingId, token, false);
    } catch (error) {
      notify(resolveError(error, "加载历史会议失败，请稍后重试。"), "error", "历史记录加载失败");
    }
  }

  async function selectConversation(conversationId, token, notifyOnError = true) {
    if (!token || !conversationId) {
      return false;
    }

    try {
      const detail = await getMeetingDetail(token, conversationId);
      applyMeetingDetail(detail);
      return true;
    } catch (error) {
      if (notifyOnError) {
        notify(resolveError(error, "读取会议详情失败，请稍后重试。"), "error", "会议加载失败");
      }
      return false;
    }
  }

  return {
    applyMeetingDetail,
    currentConversationId,
    conversations,
    findMessageId(kind) {
      return messages.value.find((message) => message.kind === kind)?.id || "";
    },
    hydrateMeetings,
    messages,
    pushMessage,
    resetMessages,
    resetWorkspaceState,
    revokeAudioUrl,
    selectConversation,
    sidebarConversations,
    upsertMessage,
    workspace,
  };
}
