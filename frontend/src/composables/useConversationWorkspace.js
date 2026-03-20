import { computed, reactive, ref } from "vue";

import {
  buildConversationPreview,
  buildConversationTitle,
  buildMessage,
  cloneMessages,
  cloneSummary,
  cloneTranscript,
  createConversation,
  defaultWorkspaceState,
  formatConversationTime,
} from "../utils/workspace";

export function useConversationWorkspace() {
  const messages = ref([]);
  const initialConversation = createConversation();
  const conversations = ref([initialConversation]);
  const currentConversationId = ref(initialConversation.id);
  const workspace = reactive(defaultWorkspaceState());

  const sidebarConversations = computed(() =>
    conversations.value.map((conversation) => ({
      ...conversation,
      updatedLabel: formatConversationTime(conversation.updatedAt),
    })),
  );

  function revokeAudioUrl() {
    if (workspace.audioUrl) {
      URL.revokeObjectURL(workspace.audioUrl);
    }
  }

  function snapshotWorkspace() {
    return {
      file: workspace.file,
      fileName: workspace.fileName,
      audioUrl: "",
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
    revokeAudioUrl();
    workspace.file = nextState.file || null;
    workspace.fileName = nextState.fileName || "";
    workspace.audioUrl = nextState.file ? URL.createObjectURL(nextState.file) : "";
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

  function resetWorkspaceState() {
    restoreWorkspace(defaultWorkspaceState());
    resetMessages();
  }

  function createNewConversation() {
    const conversation = createConversation();
    conversations.value.unshift(conversation);
    currentConversationId.value = conversation.id;
  }

  function selectConversation(conversationId) {
    if (conversationId === currentConversationId.value) {
      return false;
    }

    const conversation = conversations.value.find((item) => item.id === conversationId);
    if (!conversation) {
      return false;
    }

    currentConversationId.value = conversation.id;
    restoreWorkspace(conversation.workspace);
    messages.value = cloneMessages(conversation.messages);
    return true;
  }

  return {
    conversations,
    createNewConversation,
    currentConversationId,
    messages,
    pushMessage,
    resetMessages,
    resetWorkspaceState,
    restoreWorkspace,
    revokeAudioUrl,
    saveCurrentConversation,
    selectConversation,
    sidebarConversations,
    snapshotWorkspace,
    upsertMessage,
    workspace,
  };
}
