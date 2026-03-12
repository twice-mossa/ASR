import axios from "axios";

const apiClient = axios.create({
  baseURL: "/api",
  timeout: 15000,
});

export async function registerUser(payload) {
  const { data } = await apiClient.post("/auth/register", payload);
  return data;
}

export async function loginUser(payload) {
  const { data } = await apiClient.post("/auth/login", payload);
  return data;
}

export async function fetchCurrentUser(token) {
  const { data } = await apiClient.get("/auth/me", {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  return data;
}

export async function logoutUser(token) {
  const { data } = await apiClient.post(
    "/auth/logout",
    {},
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    },
  );
  return data;
}
