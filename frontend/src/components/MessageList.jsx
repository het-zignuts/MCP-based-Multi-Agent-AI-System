import { useEffect, useRef } from "react";
import { getGeneratedFileRawUrl, getGeneratedFilePreviewUrl } from "../lib/api";

const AGENT_ICONS = {
  general:  "🤖",
  code:     "💻",
  data:     "📊",
  research: "🔍",
  document: "📄",
  image:    "🖼️",
};

function formatTime(value) {
  if (!value) return "Pending";
  return new Intl.DateTimeFormat([], {
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function renderContentWithLinks(content) {
  if (!content) return content;

  const urlRegex = /(https?:\/\/[^\s]+|\/files\/generated\/[0-9a-fA-F-]+\/preview)/g;
  const parts = [];
  let lastIndex = 0;
  let match;

  while ((match = urlRegex.exec(content)) !== null) {
    const url = match[0];
    const index = match.index;
    if (index > lastIndex) parts.push(content.slice(lastIndex, index));
    parts.push(
      <a key={`${url}-${index}`} href={url} target="_blank" rel="noreferrer">{url}</a>
    );
    lastIndex = index + url.length;
  }

  if (lastIndex < content.length) parts.push(content.slice(lastIndex));
  return parts.length > 0 ? parts : content;
}

export default function MessageList({
  activeAgent,
  agentSwitched,
  agents,
  conversation,
  isLoading,
  isSending,
  messages,
}) {
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, isSending]);

  const getAgentLabel = (name) =>
    agents?.find((a) => a.name === name)?.label || name;

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
      {messages.map((message, idx) => {
        // Show a "switched" banner before the last AI message if the agent just changed
        const isLastAI =
          message.role === "assistant" && idx === messages.length - 1;
        const showSwitchBanner = isLastAI && agentSwitched && activeAgent;

        return (
          <div key={message.id}>
            {showSwitchBanner && (
              <div className="agent-switch-banner" aria-live="polite">
                <span>
                  ↪ Switched to{" "}
                  <strong>
                    {AGENT_ICONS[activeAgent]} {getAgentLabel(activeAgent)}
                  </strong>
                </span>
              </div>
            )}
            <article
              className={`message message--${message.role} ${
                message.pending ? "message--pending" : ""
              }`}
            >
              <div className="message-meta">
                <span className="message-role">
                  {message.role === "assistant"
                    ? (AGENT_ICONS[activeAgent] || "🤖") + " Assistant"
                    : "You"}
                </span>
                <span className="message-time">{formatTime(message.created_at)}</span>
              </div>
              <div className="message-body">{renderContentWithLinks(message.content)}</div>
              {message.files?.length ? (
                <div className="message-files">
                  {message.files.map((file) => (
                    <div className="message-file" key={file.id}>
                      <a
                        className="message-file__name"
                        href={
                          file.file_type === "application/pdf"
                            ? getGeneratedFileRawUrl(file.id)
                            : getGeneratedFilePreviewUrl(file.id)
                        }
                        rel="noreferrer"
                        target="_blank"
                      >
                        {file.filename}
                      </a>
                      <span className={`message-file__status message-file__status--${file.status}`}>
                        {file.status}
                      </span>
                    </div>
                  ))}
                </div>
              ) : null}
            </article>
          </div>
        );
      })}

      {isSending ? (
        <div className="typing-indicator">Assistant is responding...</div>
      ) : null}

      <div ref={endRef} />
    </div>
  );
}
