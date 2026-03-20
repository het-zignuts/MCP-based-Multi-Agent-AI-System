import MessageList from "./MessageList";
import MessageInput from "./MessageInput";

export default function ChatWindow({
  conversation,
  isLoading,
  isSending,
  messages,
  onSend,
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
        disabled={!conversation}
        isSending={isSending}
        onSend={onSend}
      />
    </section>
  );
}
