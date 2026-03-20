import { getApiBaseUrl } from "./api";

export function buildConversationWebSocketUrl(conversationId) {
  const apiBaseUrl = new URL(getApiBaseUrl());
  const protocol = apiBaseUrl.protocol === "https:" ? "wss:" : "ws:";

  return `${protocol}//${apiBaseUrl.host}/ws/${conversationId}`;
}
