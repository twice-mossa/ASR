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

    const durationLabel = file ? await getAudioDurationLabel(file) : "--:--";
    const meetingDetail = await createMeetingRecord({
      token,
      file,
      durationLabel,
    });

    applyMeetingDetail(meetingDetail, file);
    await hydrateMeetings(token, meetingDetail.id);
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
