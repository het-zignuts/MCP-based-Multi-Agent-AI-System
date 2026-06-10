import { useEffect, useMemo, useState } from "react";
import ChatWindow from "../components/ChatWindow";
import Sidebar from "../components/SideBar";
import {
  createConversation,
  fetchConversations,
  fetchConversationFiles,
  fetchMessages,
} from "../lib/api";
import { useConversationSocket } from "../hooks/useConversationSocket";
import { useConversationUploads } from "../hooks/useConversationUploads";

const ACTIVE_USER_ID = import.meta.env.VITE_USER_ID ?? "";

export default function ChatPage() {
  const [conversations, setConversations] = useState([]);
  const [selectedConversationId, setSelectedConversationId] = useState("");
  const [messagesByConversation, setMessagesByConversation] = useState({});
  const [isConversationListLoading, setIsConversationListLoading] =
    useState(true);
  const [messageLoadingConversationId, setMessageLoadingConversationId] =
    useState("");
  const [isCreatingConversation, setIsCreatingConversation] = useState(false);
  const [statusMessage, setStatusMessage] = useState("Loading conversations...");
  const [draftFilesByConversation, setDraftFilesByConversation] = useState({});

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

  const { connectionState, isSending, sendMessage } = useConversationSocket({
    activeUserId: ACTIVE_USER_ID,
    selectedConversationId,
    setMessagesByConversation,
    setStatusMessage,
  });

  useEffect(() => {
    let isMounted = true;

    async function loadConversations() {
      if (!ACTIVE_USER_ID) {
        setStatusMessage("Set VITE_USER_ID before loading chats.");
        setIsConversationListLoading(false);
        return;
      }

      setIsConversationListLoading(true);

      try {
        const data = await fetchConversations(ACTIVE_USER_ID);
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
            : "No conversations found for the configured user."
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

  const handleCreateConversation = async () => {
    setIsCreatingConversation(true);

    try {
      if (!ACTIVE_USER_ID) {
        setStatusMessage("Set VITE_USER_ID before creating chats.");
        return;
      }

      const conversation = await createConversation({
        title: `New Chat ${conversations.length + 1}`,
        user_id: ACTIVE_USER_ID,
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

  const mergeConversationFiles = (conversationId, uploadedFiles) => {
    setConversations((current) =>
      current.map((conversation) => {
        if (conversation.id !== conversationId) {
          return conversation;
        }

        const existingFiles = conversation.files || [];
        const nextFilesById = new Map(
          existingFiles.map((file) => [file.id, file])
        );

        uploadedFiles.forEach((file) => {
          nextFilesById.set(file.id, file);
        });

        return {
          ...conversation,
          files: Array.from(nextFilesById.values()),
        };
      })
    );
  };

  const { isUploadingFiles, uploadFiles } = useConversationUploads({
    mergeConversationFiles,
    setStatusMessage,
  });

  const refreshSelectedConversation = async (conversationId) => {
    const targetConversationId = conversationId || selectedConversationId;
    if (!targetConversationId) {
      return;
    }

    const [latestMessages, latestFiles] = await Promise.all([
      fetchMessages(targetConversationId),
      fetchConversationFiles(targetConversationId),
    ]);

    setConversationMessages(
      targetConversationId,
      [...latestMessages].sort(
        (left, right) =>
          new Date(left.created_at).getTime() -
          new Date(right.created_at).getTime()
      )
    );
    mergeConversationFiles(targetConversationId, latestFiles);
  };

  const hasPendingConversationFiles = useMemo(
    () =>
      (selectedConversation?.files || []).some(
        (file) => file.status !== "processed" && file.status !== "failed"
      ),
    [selectedConversation?.files]
  );

  const setDraftFiles = (conversationId, updater) => {
    setDraftFilesByConversation((current) => {
      const previousFiles = current[conversationId] || [];
      const nextFiles =
        typeof updater === "function" ? updater(previousFiles) : updater;

      return {
        ...current,
        [conversationId]: nextFiles,
      };
    });
  };

  useEffect(() => {
    if (!selectedConversationId) {
      return;
    }

    if (!hasPendingConversationFiles) {
      return;
    }

    let isActive = true;
    let timeoutId = null;
    let attempt = 0;

    const pollStatuses = async () => {
      try {
        const latestFiles = await fetchConversationFiles(selectedConversationId);
        if (!isActive) {
          return;
        }

        mergeConversationFiles(selectedConversationId, latestFiles);
        attempt = 0;
      } catch (error) {
        if (!isActive) {
          return;
        }

        attempt += 1;
        console.error("Failed to refresh file statuses", error);
      }

      if (!isActive) {
        return;
      }

      const nextDelay = Math.min(1000 * 2 ** attempt, 5000);
      timeoutId = window.setTimeout(() => {
        void pollStatuses();
      }, nextDelay);
    };

    void pollStatuses();

    return () => {
      isActive = false;
      if (timeoutId !== null) {
        window.clearTimeout(timeoutId);
      }
    };
  }, [hasPendingConversationFiles, selectedConversationId]);

  const handleAttachFiles = async (files) => {
    if (!selectedConversationId) {
      setStatusMessage("Select a conversation before uploading files.");
      return;
    }

    try {
      const uploadedFiles = await uploadFiles({
        conversationId: selectedConversationId,
        files,
      });
      setDraftFiles(selectedConversationId, (currentFiles) => [
        ...currentFiles,
        ...uploadedFiles.filter(
          (file) => !currentFiles.some((currentFile) => currentFile.id === file.id)
        ),
      ]);
      setStatusMessage("Files uploaded. Waiting for processing to finish...");
    } catch (error) {
      setStatusMessage(
        error.response?.data?.detail ||
          "Could not upload files for this conversation."
      );
    }
  };

  const handleRemoveAttachedFile = (fileId) => {
    if (!selectedConversationId) {
      return;
    }

    setDraftFiles(selectedConversationId, (currentFiles) =>
      currentFiles.filter((file) => file.id !== fileId)
    );
  };

  const handleClearAttachedFiles = () => {
    if (!selectedConversationId) {
      return;
    }

    setDraftFiles(selectedConversationId, []);
  };

  const handleSendMessage = async ({ content, fileIds }) => {
    if (!selectedConversationId) {
      setStatusMessage("Select a conversation before sending a message.");
      return false;
    }

    sendMessage(content, fileIds);
    return true;
  };


  const attachedFiles = useMemo(() => {
    if (!selectedConversationId) {
      return [];
    }

    const conversationFiles = selectedConversation?.files || [];
    const conversationFileMap = new Map(
      conversationFiles.map((file) => [file.id, file])
    );

    return (draftFilesByConversation[selectedConversationId] || []).map(
      (file) => conversationFileMap.get(file.id) || file
    );
  }, [draftFilesByConversation, selectedConversation, selectedConversationId]);

  const sendDisabledReason = useMemo(() => {
    if (attachedFiles.some((file) => file.status === "failed")) {
      return "Remove failed files before sending.";
    }

    if (
      attachedFiles.some(
        (file) => file.status !== "processed" && file.status !== "failed"
      )
    ) {
      return "Files are still being processed. Send will unlock automatically.";
    }

    return "";
  }, [attachedFiles]);

  useEffect(() => {
    if (attachedFiles.length === 0) {
      return;
    }

    if (attachedFiles.every((file) => file.status === "processed")) {
      setStatusMessage("Files processed. You can send your message now.");
      return;
    }

    if (attachedFiles.some((file) => file.status === "failed")) {
      setStatusMessage("One or more files failed processing. Remove them to continue.");
    }
  }, [attachedFiles]);

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
          attachedFiles={attachedFiles}
          conversation={selectedConversation}
          isLoading={isLoadingMessages}
          isSending={isSending}
          isUploading={isUploadingFiles}
          messages={messages}
          onAttachFiles={handleAttachFiles}
          onClearAttachedFiles={handleClearAttachedFiles}
          onRemoveAttachedFile={handleRemoveAttachedFile}
          onSend={handleSendMessage}
          sendDisabledReason={sendDisabledReason}
        />
      </main>
    </div>
  );
}
