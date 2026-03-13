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

export async function summarizeMeeting(text) {
  const { data } = await apiClient.post("/summary", {
    transcribed_text: text,
  });
  return data;
}
