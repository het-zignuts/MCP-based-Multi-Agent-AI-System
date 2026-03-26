import MessageList from "./MessageList";
import MessageInput from "./MessageInput";

export default function ChatWindow({
  attachedFiles,
  conversation,
  isLoading,
  isSending,
  isUploading,
  messages,
  onAttachFiles,
  onClearAttachedFiles,
  onRemoveAttachedFile,
  onSend,
  sendDisabledReason,
}) {
  return (
    <section className="chat-window">
      <MessageList
        conversation={conversation}
        isLoading={isLoading}
        isSending={isSending}
        messages={messages}
      />
      <MessageInput
        attachedFiles={attachedFiles}
        disabled={!conversation}
        isSending={isSending}
        isUploading={isUploading}
        onAttachFiles={onAttachFiles}
        onClearAttachedFiles={onClearAttachedFiles}
        onRemoveAttachedFile={onRemoveAttachedFile}
        onSend={onSend}
        sendDisabledReason={sendDisabledReason}
      />
    </section>
  );
}
