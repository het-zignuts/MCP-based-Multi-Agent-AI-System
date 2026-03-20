import { useEffect, useMemo, useRef, useState } from "react";
import ChatWindow from "../components/ChatWindow";
import Sidebar from "../components/SideBar";
import {
  createConversation,
  fetchConversations,
  fetchMessages,
} from "../lib/api";
import { buildConversationWebSocketUrl } from "../lib/socket";

const HARDCODED_USER_ID = "0c921e1b-f98c-4261-8e3e-99438be83c57";

function createTempMessage(content) {
  return {
    id: `temp-${crypto.randomUUID()}`,
    content,
    created_at: new Date().toISOString(),
    pending: true,
    role: "user",
    user_id: HARDCODED_USER_ID,
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

export default function ChatPage() {
  const socketRef = useRef(null);
  const [conversations, setConversations] = useState([]);
  const [selectedConversationId, setSelectedConversationId] = useState("");
  const [messagesByConversation, setMessagesByConversation] = useState({});
  const [isConversationListLoading, setIsConversationListLoading] =
    useState(true);
  const [messageLoadingConversationId, setMessageLoadingConversationId] =
    useState("");
  const [isCreatingConversation, setIsCreatingConversation] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [connectionState, setConnectionState] = useState("idle");
  const [statusMessage, setStatusMessage] = useState("Loading conversations...");

  const selectedConversation = useMemo(
    () =>
      conversations.find((conversation) => conversation.id === selectedConversationId) ||
      null,
    [conversations, selectedConversationId]
  );

  const messages = selectedConversationId
    ? messagesByConversation[selectedConversationId] || []
    : [];

  const isLoadingMessages =
    !!selectedConversationId &&
    messageLoadingConversationId === selectedConversationId;

  const setConversationMessages = (conversationId, updater) => {
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

  useEffect(() => {
    let isMounted = true;

    async function loadConversations() {
      setIsConversationListLoading(true);

      try {
        const data = await fetchConversations(HARDCODED_USER_ID);
        if (!isMounted) {
          return;
        }

        const sorted = [...data].sort(
          (left, right) =>
            new Date(right.updated_at).getTime() -
            new Date(left.updated_at).getTime()
        );

        setConversations(sorted);
        setSelectedConversationId(sorted[0]?.id || "");
        setStatusMessage(
          sorted.length > 0
            ? "Conversations loaded."
            : "No conversations found for the hardcoded user."
        );
      } catch (error) {
        if (!isMounted) {
          return;
        }

        setStatusMessage(
          error.response?.data?.detail ||
            "Could not load conversations from the backend."
        );
      } finally {
        if (isMounted) {
          setIsConversationListLoading(false);
        }
      }
    }

    loadConversations();

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedConversationId) {
      return;
    }

    let isMounted = true;

    async function loadMessages() {
      setMessageLoadingConversationId(selectedConversationId);

      try {
        const data = await fetchMessages(selectedConversationId);
        if (!isMounted) {
          return;
        }

        const sorted = [...data].sort(
          (left, right) =>
            new Date(left.created_at).getTime() -
            new Date(right.created_at).getTime()
        );

        setConversationMessages(selectedConversationId, sorted);
      } catch (error) {
        if (!isMounted) {
          return;
        }

        setStatusMessage(
          error.response?.data?.detail ||
            "Could not load messages for the selected conversation."
        );
      } finally {
        if (isMounted) {
          setMessageLoadingConversationId("");
        }
      }
    }

    loadMessages();

    return () => {
      isMounted = false;
    };
  }, [selectedConversationId]);

  useEffect(() => {
    if (!selectedConversationId) {
      if (socketRef.current) {
        socketRef.current.close();
        socketRef.current = null;
      }
      setConnectionState("idle");
      return;
    }

    const socket = new WebSocket(
      buildConversationWebSocketUrl(selectedConversationId)
    );

    socketRef.current = socket;
    setConnectionState("connecting");

    socket.onopen = () => {
      setConnectionState("connected");
    };

    socket.onmessage = (event) => {
      const payload = JSON.parse(event.data);

      if (payload.type !== "chat") {
        return;
      }

      setConversationMessages(selectedConversationId, (currentMessages) =>
        mergeIncomingMessages(
          currentMessages,
          payload.data.user_message,
          payload.data.ai_message
        )
      );
      setIsSending(false);
    };

    socket.onerror = () => {
      setConnectionState("error");
      setIsSending(false);
      setStatusMessage("Websocket error while sending or receiving messages.");
    };

    socket.onclose = () => {
      setConnectionState("closed");
    };

    return () => {
      socket.close();
      if (socketRef.current === socket) {
        socketRef.current = null;
      }
    };
  }, [selectedConversationId]);

  const handleCreateConversation = async () => {
    setIsCreatingConversation(true);

    try {
      const conversation = await createConversation({
        title: `New Chat ${conversations.length + 1}`,
        user_id: HARDCODED_USER_ID,
        convo_metadata: null,
      });

      setConversations((current) => [conversation, ...current]);
      setSelectedConversationId(conversation.id);
      setStatusMessage("New conversation created.");
    } catch (error) {
      setStatusMessage(
        error.response?.data?.detail ||
          "Could not create a new conversation."
      );
    } finally {
      setIsCreatingConversation(false);
    }
  };

  const handleSendMessage = (content) => {
    const socket = socketRef.current;

    if (!selectedConversationId || !socket || socket.readyState !== WebSocket.OPEN) {
      setStatusMessage("Chat connection is not ready yet.");
      return;
    }

    setConversationMessages(selectedConversationId, (currentMessages) => [
      ...currentMessages,
      createTempMessage(content),
    ]);

    setIsSending(true);
    socket.send(
      JSON.stringify({
        content,
        user_id: HARDCODED_USER_ID,
      })
    );
  };

  return (
    <div className="app-shell">
      <Sidebar
        conversations={conversations}
        isConversationListLoading={isConversationListLoading}
        isCreatingConversation={isCreatingConversation}
        onCreateConversation={handleCreateConversation}
        onSelectConversation={setSelectedConversationId}
        selectedConversationId={selectedConversationId}
      />

      <main className="workspace">
        <header className="workspace-header">
          <div>
            <p className="workspace-header__label">Current Chat</p>
            <h2>{selectedConversation?.title || "No conversation selected"}</h2>
          </div>
          <span className={`status-pill status-pill--${connectionState}`}>
            {connectionState}
          </span>
        </header>

        <div className="status-banner">{statusMessage}</div>

        <ChatWindow
          conversation={selectedConversation}
          isLoading={isLoadingMessages}
          isSending={isSending}
          messages={messages}
          onSend={handleSendMessage}
        />
      </main>
    </div>
  );
}
