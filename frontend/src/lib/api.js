import axios from "axios";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

export const api = axios.create({
  baseURL: API_BASE_URL,
});

export function getApiBaseUrl() {
  return API_BASE_URL;
}

export async function fetchConversations(userId) {
  const response = await api.get("/conversations/", {
    params: { user_id: userId },
  });

  return response.data;
}

export async function createConversation(payload) {
  const response = await api.post("/conversations/", payload);
  return response.data;
}

export async function fetchMessages(conversationId) {
  const response = await api.get("/messages/", {
    params: { conversation_id: conversationId },
  });

  return response.data;
}
