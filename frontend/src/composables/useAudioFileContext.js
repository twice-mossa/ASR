import { ref } from "vue";

import { formatTime } from "../utils/workspace";

export function useAudioFileContext({
  workspace,
  withAuth,
  notify,
  resetMessages,
  pushMessage,
  revokeAudioUrl,
  onBeforeApplyFile,
}) {
  const fileInputRef = ref(null);

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
    onBeforeApplyFile?.();
    revokeAudioUrl();
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

  function handleUploadRequest() {
    if (!withAuth({ type: "upload" })) {
      return;
    }

    openFilePicker();
  }

  return {
    fileInputRef,
    handleFileSelect,
    handleUploadRequest,
    openFilePicker,
  };
}
