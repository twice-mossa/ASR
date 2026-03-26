import { ref } from "vue";

import { completeChunkedUpload, initChunkedUpload, uploadChunkPart } from "../api/meeting";
import { formatTime } from "../utils/workspace";

const DEFAULT_CHUNK_SIZE = 5 * 1024 * 1024;

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

  function resetUploadState() {
    workspace.uploadStatus = "idle";
    workspace.uploadLoadedBytes = 0;
    workspace.uploadTotalBytes = 0;
    workspace.uploadPercent = 0;
  }

  function updateUploadState(event) {
    const loaded = Number(event?.loaded) || 0;
    const total = Number(event?.total) || 0;
    workspace.uploadStatus = "uploading";
    workspace.uploadLoadedBytes = loaded;
    workspace.uploadTotalBytes = total;
    workspace.uploadPercent = total > 0 ? Math.min(100, Math.round((loaded / total) * 100)) : 0;
  }

  function updateUploadProgressByBytes(loaded, total) {
    updateUploadState({ loaded, total });
  }

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
    workspace.fileName = file?.name || "";
    workspace.uploadStatus = "preparing";
    workspace.uploadLoadedBytes = 0;
    workspace.uploadTotalBytes = file?.size || 0;
    workspace.uploadPercent = 0;

    const durationLabel = file ? await getAudioDurationLabel(file) : "--:--";
    try {
      const chunkSize = Math.min(DEFAULT_CHUNK_SIZE, Math.max(1024 * 1024, file.size || DEFAULT_CHUNK_SIZE));
      const totalChunks = Math.max(1, Math.ceil(file.size / chunkSize));
      const session = await initChunkedUpload({
        token,
        payload: {
          filename: file.name,
          duration_label: durationLabel,
          file_size: file.size,
          chunk_size: chunkSize,
          total_chunks: totalChunks,
          content_type: file.type || "application/octet-stream",
        },
      });
      let uploadedBytes = 0;

      for (let index = 0; index < totalChunks; index += 1) {
        const start = index * chunkSize;
        const end = Math.min(file.size, start + chunkSize);
        const chunk = file.slice(start, end);

        await uploadChunkPart({
          token,
          uploadId: session.upload_id,
          partNumber: index + 1,
          chunk,
          onUploadProgress(event) {
            const chunkLoaded = Number(event?.loaded) || 0;
            updateUploadProgressByBytes(uploadedBytes + chunkLoaded, file.size || 0);
          },
        });
        uploadedBytes = end;
        updateUploadProgressByBytes(uploadedBytes, file.size || 0);
      }

      const meetingDetail = await completeChunkedUpload({
        token,
        uploadId: session.upload_id,
      });

      applyMeetingDetail(meetingDetail, file);
      await hydrateMeetings(token, meetingDetail.id);
    } catch (error) {
      resetUploadState();
      throw error;
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
