import axios from "axios";

const apiClient = axios.create({
  baseURL: "/api",
  timeout: 120000,
});

function authHeaders(token) {
  return token
    ? {
        Authorization: `Bearer ${token}`,
      }
    : {};
}

export async function createMeetingRecord({ token, file, durationLabel, onUploadProgress }) {
  const chunkSize = 2 * 1024 * 1024;
  const totalChunks = Math.max(1, Math.ceil(file.size / chunkSize));

  const sessionForm = new FormData();
  sessionForm.append("filename", file.name);
  sessionForm.append("duration_label", durationLabel || "--:--");
  sessionForm.append("content_type", file.type || "application/octet-stream");
  const sessionResponse = await apiClient.post("/meetings/upload-sessions", sessionForm, {
    timeout: 0,
    headers: {
      ...authHeaders(token),
    },
  });

  const uploadId = sessionResponse.data.upload_id;
  for (let chunkIndex = 0; chunkIndex < totalChunks; chunkIndex += 1) {
    const start = chunkIndex * chunkSize;
    const end = Math.min(file.size, start + chunkSize);
    const chunk = file.slice(start, end);
    const chunkForm = new FormData();
    chunkForm.append("chunk_index", String(chunkIndex));
    chunkForm.append("total_chunks", String(totalChunks));
    chunkForm.append("file", chunk, `${file.name}.part-${chunkIndex}`);

    await apiClient.post(`/meetings/upload-sessions/${uploadId}/chunks`, chunkForm, {
      timeout: 0,
      headers: {
        ...authHeaders(token),
      },
      onUploadProgress: (event) => {
        if (!onUploadProgress) {
          return;
        }
        const chunkLoaded = Number(event?.loaded) || 0;
        onUploadProgress({
          loaded: Math.min(file.size, start + chunkLoaded),
          total: file.size,
          chunkIndex: chunkIndex + 1,
          totalChunks,
        });
      },
    });

    if (onUploadProgress) {
      onUploadProgress({
        loaded: end,
        total: file.size,
        chunkIndex: chunkIndex + 1,
        totalChunks,
      });
    }
  }

  const { data } = await apiClient.post(`/meetings/upload-sessions/${uploadId}/complete`, null, {
    timeout: 0,
    headers: {
      ...authHeaders(token),
    },
  });
  return data;
}

export async function listMeetings(token, query = "") {
  const { data } = await apiClient.get("/meetings", {
    params: query ? { query } : undefined,
    headers: authHeaders(token),
  });
  return data;
}

export async function getMeetingDetail(token, meetingId) {
  const { data } = await apiClient.get(`/meetings/${meetingId}`, {
    headers: authHeaders(token),
  });
  return data;
}

export async function updateMeeting(token, meetingId, payload) {
  const { data } = await apiClient.patch(`/meetings/${meetingId}`, payload, {
    headers: authHeaders(token),
  });
  return data;
}

export async function transcribeMeeting(file) {
  const formData = new FormData();
  formData.append("file", file);

  const { data } = await apiClient.post("/transcribe", formData, {
    timeout: 0,
  });
  return data;
}

export async function startTranscriptionJob(file) {
  const formData = new FormData();
  formData.append("file", file);

  const { data } = await apiClient.post("/transcribe/jobs", formData, {
    timeout: 0,
  });
  return data;
}

export async function startMeetingTranscriptionJob(token, meetingId) {
  const { data } = await apiClient.post(
    `/meetings/${meetingId}/transcribe`,
    {},
    {
      timeout: 0,
      headers: authHeaders(token),
    },
  );
  return data;
}

export async function getTranscriptionJob(jobId) {
  const { data } = await apiClient.get(`/transcribe/jobs/${jobId}`, {
    timeout: 0,
  });
  return data;
}

export async function stopTranscriptionJob(token, jobId) {
  const { data } = await apiClient.post(
    `/transcribe/jobs/${jobId}/stop`,
    {},
    {
      timeout: 0,
      headers: authHeaders(token),
    },
  );
  return data;
}

export async function summarizeMeeting({ token, meetingId, text }) {
  const payload = meetingId ? { meeting_id: meetingId } : { transcribed_text: text };
  const { data } = await apiClient.post("/summary", payload, {
    headers: authHeaders(token),
  });
  return data;
}

export async function askMeetingQuestion(token, meetingId, question) {
  const { data } = await apiClient.post(
    `/meetings/${meetingId}/ask`,
    { question },
    {
      headers: authHeaders(token),
    },
  );
  return data;
}

export async function sendMeetingSummaryEmail(token, meetingId) {
  const { data } = await apiClient.post(
    `/meetings/${meetingId}/send-summary-email`,
    {},
    {
      headers: authHeaders(token),
    },
  );
  return data;
}

export async function deleteMeeting(token, meetingId) {
  const { data } = await apiClient.delete(`/meetings/${meetingId}`, {
    headers: authHeaders(token),
  });
  return data;
}

export async function clearMeetings(token) {
  const { data } = await apiClient.delete("/meetings", {
    headers: authHeaders(token),
  });
  return data;
}
