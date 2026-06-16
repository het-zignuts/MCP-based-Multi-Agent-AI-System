import { useEffect, useRef, useState } from "react";
import { buildConversationWebSocketUrl } from "../lib/socket";

function createTempMessage(content, userId) {
  return {
    id: `temp-${crypto.randomUUID()}`,
    content,
    created_at: new Date().toISOString(),
    pending: true,
    role: "user",
    user_id: userId,
  };
}

function mergeIncomingMessages(currentMessages, userMessage, aiMessage) {
  const nextMessages = [...currentMessages];
  const pendingIndex = nextMessages.findIndex(
    (message) =>
      message.pending &&
      message.role === "user" &&
      message.content === userMessage.content
  );

  if (pendingIndex >= 0) {
    nextMessages.splice(pendingIndex, 1, userMessage);
  } else if (!nextMessages.some((message) => message.id === userMessage.id)) {
    nextMessages.push(userMessage);
  }

  if (!nextMessages.some((message) => message.id === aiMessage.id)) {
    nextMessages.push(aiMessage);
  }

  return nextMessages;
}

export function useConversationSocket({
  activeUserId,
  selectedAgent,
  selectedConversationId,
  selectedConversation,
  setMessagesByConversation,
  setStatusMessage,
}) {
  const socketRef = useRef(null);
  const [sendingConversationId, setSendingConversationId] = useState("");
  const [connectionState, setConnectionState] = useState("idle");
  const [activeAgent, setActiveAgent] = useState("general");
  const [agentSwitched, setAgentSwitched] = useState(false);
  const lastInitializedIdRef = useRef(null);

  // Sync initial active agent state when conversation changes or loads
  useEffect(() => {
    if (selectedConversationId && selectedConversation) {
      if (lastInitializedIdRef.current !== selectedConversationId) {
        const metadata = selectedConversation.convo_metadata;
        const savedAgent = metadata?.agent_state?.active_agent || "general";
        setActiveAgent(savedAgent);
        setAgentSwitched(false);
        lastInitializedIdRef.current = selectedConversationId;
      }
    } else if (!selectedConversationId) {
      setActiveAgent("general");
      setAgentSwitched(false);
      lastInitializedIdRef.current = null;
    }
  }, [selectedConversationId, selectedConversation]);

  const isSending =
    !!selectedConversationId && sendingConversationId === selectedConversationId;

  const updateConversationMessages = (conversationId, updater) => {
    setMessagesByConversation((current) => {
      const previousMessages = current[conversationId] || [];
      const nextMessages =
        typeof updater === "function" ? updater(previousMessages) : updater;

      return {
        ...current,
        [conversationId]: nextMessages,
      };
    });
  };

  const clearPendingMessages = (conversationId) => {
    updateConversationMessages(conversationId, (currentMessages) =>
      currentMessages.filter((message) => !message.pending)
    );
  };

  useEffect(() => {
    if (!selectedConversationId) {
      if (socketRef.current) {
        socketRef.current.close();
        socketRef.current = null;
      }
      setConnectionState("idle");
      return;
    }

    const conversationId = selectedConversationId;
    const socket = new WebSocket(
      buildConversationWebSocketUrl(conversationId, activeUserId)
    );

    socketRef.current = socket;
    setConnectionState("connecting");

    socket.onopen = () => {
      if (socketRef.current !== socket) {
        return;
      }
      setConnectionState("connected");
    };

    socket.onmessage = (event) => {
      if (socketRef.current !== socket) {
        return;
      }

      const payload = JSON.parse(event.data);

      if (payload.type === "error") {
        clearPendingMessages(conversationId);
        setSendingConversationId((current) =>
          current === conversationId ? "" : current
        );
        setStatusMessage(payload.detail || "Failed to process the message.");
        return;
      }

      if (payload.type !== "chat") {
        return;
      }

      // Update active agent state from every WS message
      if (payload.data.active_agent) {
        setAgentSwitched(payload.data.agent_switched === true);
        setActiveAgent(payload.data.active_agent);
      }

      updateConversationMessages(conversationId, (currentMessages) =>
        mergeIncomingMessages(
          currentMessages,
          payload.data.user_message,
          payload.data.ai_message
        )
      );
      setSendingConversationId((current) =>
        current === conversationId ? "" : current
      );
      setStatusMessage("Message delivered.");
    };

    socket.onerror = () => {
      if (socketRef.current !== socket) {
        return;
      }

      setConnectionState("error");
      clearPendingMessages(conversationId);
      setSendingConversationId((current) =>
        current === conversationId ? "" : current
      );
      setStatusMessage("Websocket error while sending or receiving messages.");
    };

    socket.onclose = () => {
      if (socketRef.current !== socket) {
        return;
      }

      setConnectionState("closed");
      setSendingConversationId((current) =>
        current === conversationId ? "" : current
      );
    };

    return () => {
      socket.close();
      if (socketRef.current === socket) {
        socketRef.current = null;
      }
    };
  }, [
    activeUserId,
    selectedConversationId,
    setMessagesByConversation,
    setStatusMessage,
  ]);

  const sendMessage = (content, attachedFileIds = []) => {
    const socket = socketRef.current;

    if (!activeUserId) {
      setStatusMessage("Set VITE_USER_ID before using chat.");
      return;
    }

    if (
      !selectedConversationId ||
      !socket ||
      socket.readyState !== WebSocket.OPEN
    ) {
      setStatusMessage("Chat connection is not ready yet.");
      return;
    }

    updateConversationMessages(selectedConversationId, (currentMessages) => [
      ...currentMessages,
      createTempMessage(content, activeUserId),
    ]);

    setSendingConversationId(selectedConversationId);
    setStatusMessage("Sending message...");
    socket.send(
      JSON.stringify({
        content,
        file_ids: attachedFileIds,
        user_id: activeUserId,
        // Pass the explicitly selected agent so the backend bypasses LLM routing
        selected_agent: selectedAgent || null,
      })
    );
  };

  return {
    activeAgent,
    agentSwitched,
    connectionState,
    isSending,
    sendMessage,
  };
}
