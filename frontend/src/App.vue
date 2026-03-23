<script setup>
import { Menu } from "@element-plus/icons-vue";
import { ElNotification } from "element-plus";
import { onBeforeUnmount, onMounted, ref, watch } from "vue";

import AudioTray from "./components/AudioTray.vue";
import ChatWorkspace from "./components/ChatWorkspace.vue";
import ComposerBar from "./components/ComposerBar.vue";
import LoginModal from "./components/LoginModal.vue";
import SidebarNav from "./components/SidebarNav.vue";
import WorkspaceHeader from "./components/WorkspaceHeader.vue";
import { useAudioFileContext } from "./composables/useAudioFileContext";
import { useAuthSession } from "./composables/useAuthSession";
import { useConversationWorkspace } from "./composables/useConversationWorkspace";
import { useMeetingWorkflow } from "./composables/useMeetingWorkflow";

const sidebarOpen = ref(false);

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

const auth = useAuthSession({
  notify,
  resolveError,
});

const {
  authLoading,
  authFeedback,
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
} = auth;

const conversationWorkspace = useConversationWorkspace({
  notify,
  resolveError,
});

const {
  currentConversationId,
  findMessageId,
  messages,
  sidebarConversations,
  workspace,
  applyMeetingDetail,
  hydrateMeetings,
  resetWorkspaceState,
  revokeAudioUrl,
  selectConversation: restoreConversation,
} = conversationWorkspace;

const meetingWorkflow = useMeetingWorkflow({
  workspace,
  session,
  isAuthenticated,
  withAuth,
  notify,
  resolveError,
  pushMessage: conversationWorkspace.pushMessage,
  upsertMessage: conversationWorkspace.upsertMessage,
  applyMeetingDetail,
  findMessageId,
  hydrateMeetings,
});

const {
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
} = meetingWorkflow;

const audioFileContext = useAudioFileContext({
  workspace,
  withAuth,
  notify,
  revokeAudioUrl,
  onBeforeApplyFile: resetTransientState,
  tokenRef: {
    get value() {
      return session.token;
    },
  },
  resolveError,
  applyMeetingDetail,
  hydrateMeetings,
});

const { fileInputRef, handleFileSelect, handleUploadRequest } = audioFileContext;

setPendingActionHandler(handlePendingAction);
setUploadRequestHandler(handleUploadRequest);

function startNewAnalysis() {
  resetTransientState();
  resetWorkspaceState();
  sidebarOpen.value = false;
}

async function selectConversation(conversationId) {
  if (conversationId === currentConversationId.value) {
    sidebarOpen.value = false;
    return;
  }

  resetTransientState();
  if (await restoreConversation(conversationId, session.token)) {
    await resumeActiveTranscriptionIfNeeded();
    sidebarOpen.value = false;
  }
}

onMounted(async () => {
  await hydrateSession();
  if (session.token) {
    await hydrateMeetings(session.token);
    await resumeActiveTranscriptionIfNeeded();
  }
});

watch(
  () => session.token,
  async (token, previousToken) => {
    if (token === previousToken) {
      return;
    }

    if (!token) {
      resetTransientState();
      resetWorkspaceState();
      return;
    }

    await hydrateMeetings(token);
    await resumeActiveTranscriptionIfNeeded();
  },
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
        @delete-conversation="handleDeleteMeeting"
        @rename-conversation="handleRenameMeeting($event.id, $event.title)"
        @clear-conversations="handleClearMeetings"
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
        :progress-completed="workspace.completedChunks"
        :progress-total="workspace.totalChunks"
        :progress-status="workspace.transcriptionStatus"
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
        :can-stop-transcription="canStopTranscription"
        :can-download-notes="canDownloadNotes"
        :work-loading="workLoading"
        @upload="handleUploadRequest"
        @stop-transcribe="handleStopTranscribe"
        @transcribe="handleTranscribe"
        @summary="handleSummary"
        @download="downloadNotes"
        @submit="submitPrompt"
      />
    </main>

    <input
      ref="fileInputRef"
      class="visually-hidden"
      type="file"
      accept=".wav,.mp3,.m4a,.flac"
      @change="handleFileSelect"
    />

    <LoginModal
      v-model:visible="loginModalVisible"
      v-model:active-tab="loginModalTab"
      :loading="authLoading"
      :login-form="loginForm"
      :register-form="registerForm"
      :auth-feedback="authFeedback"
      @clear-error="clearAuthFeedback"
      @login="handleLogin"
      @register="handleRegister"
    />
  </div>
</template>

<style scoped>
.app-shell {
  height: 100vh;
  display: grid;
  grid-template-columns: 236px minmax(0, 1fr);
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
  padding: 0 18px;
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
