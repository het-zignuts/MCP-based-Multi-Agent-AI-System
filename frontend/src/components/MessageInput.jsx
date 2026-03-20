import { useState } from "react";

export default function MessageInput({ disabled, isSending, onSend }) {
  const [text, setText] = useState("");

  const handleSubmit = () => {
    const trimmed = text.trim();
    if (!trimmed || disabled || isSending) {
      return;
    }

    onSend(trimmed);
    setText("");
  };

  const handleKeyDown = (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="composer-shell">
      <div className="composer">
        <textarea
          className="composer-input"
          disabled={disabled || isSending}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={
            disabled
              ? "Select or create a conversation"
              : "Type your message..."
          }
          rows={2}
          value={text}
        />
        <button
          className="primary-button"
          disabled={disabled || isSending || !text.trim()}
          onClick={handleSubmit}
          type="button"
        >
          {isSending ? "Sending..." : "Send"}
        </button>
      </div>
    </div>
  );
}
