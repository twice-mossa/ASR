import axios from "axios";

const apiClient = axios.create({
  baseURL: "/api",
  timeout: 120000,
});

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

export async function getTranscriptionJob(jobId) {
  const { data } = await apiClient.get(`/transcribe/jobs/${jobId}`, {
    timeout: 0,
  });
  return data;
}

export async function summarizeMeeting(text) {
  const { data } = await apiClient.post("/summary", {
    transcribed_text: text,
  });
  return data;
}

export async function analyzeWithAgent(text) {
  const { data } = await apiClient.post(
    "/agent/analyze",
    { transcribed_text: text },
    { timeout: 300000 },
  );
  return data;
}
