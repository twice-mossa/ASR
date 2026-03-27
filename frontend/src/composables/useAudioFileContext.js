import { ref } from "vue";

import { createMeetingRecord } from "../api/meeting";
import { formatTime } from "../utils/workspace";

export function useAudioFileContext({
  workspace,
  withAuth,
  notify,
  revokeAudioUrl,
  onBeforeApplyFile,
  tokenRef,
  resolveError,
  applyMeetingDetail,
  hydrateMeetings,
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
    const token = tokenRef.value;
    if (!token) {
      notify("请先登录后再上传音频。", "warning", "需要登录");
      return;
    }

    onBeforeApplyFile?.();
    revokeAudioUrl();
    workspace.uploading = true;
    workspace.uploadProgress = 0;
    workspace.uploadChunkIndex = 0;
    workspace.uploadTotalChunks = 0;
    workspace.fileName = file?.name || workspace.fileName;
    workspace.meetingStatus = "uploading";

    const durationPromise = file ? getAudioDurationLabel(file) : Promise.resolve("--:--");
    const durationLabel = await Promise.race([
      durationPromise,
      new Promise((resolve) => window.setTimeout(() => resolve("--:--"), 1200)),
    ]);

    try {
      const meetingDetail = await createMeetingRecord({
        token,
        file,
        durationLabel,
        onUploadProgress: (event) => {
          const total = Number(event?.total) || 0;
          const loaded = Number(event?.loaded) || 0;
          workspace.uploadChunkIndex = Number(event?.chunkIndex) || workspace.uploadChunkIndex || 0;
          workspace.uploadTotalChunks = Number(event?.totalChunks) || workspace.uploadTotalChunks || 0;
          if (total > 0) {
            const percent = (loaded / total) * 100;
            workspace.uploadProgress = Math.max(0, Math.min(100, Number(percent.toFixed(percent < 10 ? 1 : 0))));
          }
        },
      });

      workspace.uploadProgress = 100;
      applyMeetingDetail(meetingDetail, file);
      await hydrateMeetings(token, meetingDetail.id);
    } finally {
      workspace.uploading = false;
      workspace.uploadChunkIndex = 0;
      workspace.uploadTotalChunks = 0;
    }
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

    try {
      await applySelectedFile(file);
      notify("音频已加入当前工作台，并保存为新的会议记录。", "success", "上传成功");
    } catch (error) {
      workspace.uploading = false;
      workspace.uploadProgress = 0;
      workspace.uploadChunkIndex = 0;
      workspace.uploadTotalChunks = 0;
      workspace.meetingStatus = "idle";
      notify(resolveError(error, "上传音频失败，请稍后再试。"), "error", "上传失败");
    }
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
