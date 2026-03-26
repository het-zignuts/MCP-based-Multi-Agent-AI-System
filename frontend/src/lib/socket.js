import { getApiBaseUrl } from "./api";

export function buildConversationWebSocketUrl(conversationId, userId) {
  const apiBaseUrl = new URL(getApiBaseUrl());
  const protocol = apiBaseUrl.protocol === "https:" ? "wss:" : "ws:";
  const url = new URL(`${protocol}//${apiBaseUrl.host}/ws/${conversationId}`);

  if (userId) {
    url.searchParams.set("user_id", userId);
  }

  return url.toString();
}
