import { useEffect, useRef } from "react";

function formatTime(value) {
  if (!value) {
    return "Pending";
  }

  return new Intl.DateTimeFormat([], {
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

export default function MessageList({
  conversation,
  isLoading,
  isSending,
  messages,
}) {
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, isSending]);

  if (!conversation) {
    return (
      <div className="message-list message-list--empty">
        <div className="empty-state-card">
          <h2>Select a conversation</h2>
          <p>Choose one from the sidebar or create a new chat.</p>
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="message-list message-list--empty">
        <div className="empty-state-card">
          <h2>Loading messages...</h2>
          <p>Only messages from the selected conversation are shown here.</p>
        </div>
      </div>
    );
  }

  if (messages.length === 0) {
    return (
      <div className="message-list message-list--empty">
        <div className="empty-state-card">
          <h2>{conversation.title}</h2>
          <p>This conversation is empty. Send the first message.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="message-list">
      {messages.map((message) => (
        <article
          className={`message message--${message.role} ${
            message.pending ? "message--pending" : ""
          }`}
          key={message.id}
        >
          <div className="message-meta">
            <span className="message-role">
              {message.role === "assistant" ? "Assistant" : "You"}
            </span>
            <span className="message-time">{formatTime(message.created_at)}</span>
          </div>
          <div className="message-body">{message.content}</div>
        </article>
      ))}

      {isSending ? (
        <div className="typing-indicator">Assistant is responding...</div>
      ) : null}

      <div ref={endRef} />
    </div>
  );
}
