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

export async function createMeetingRecord({ token, file, durationLabel }) {
  const formData = new FormData();
  formData.append("filename", file.name);
  formData.append("duration_label", durationLabel || "--:--");
  formData.append("file", file);

  const { data } = await apiClient.post("/meetings", formData, {
    timeout: 0,
    headers: {
      ...authHeaders(token),
      "Content-Type": "multipart/form-data",
    },
  });
  return data;
}

export async function listMeetings(token) {
  const { data } = await apiClient.get("/meetings", {
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

export async function transcribeMeeting(file) {
  const formData = new FormData();
  formData.append("file", file);

  const { data } = await apiClient.post("/transcribe", formData, {
    timeout: 0,
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });
  return data;
}

export async function startTranscriptionJob(file) {
  const formData = new FormData();
  formData.append("file", file);

  const { data } = await apiClient.post("/transcribe/jobs", formData, {
    timeout: 0,
    headers: {
      "Content-Type": "multipart/form-data",
    },
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
