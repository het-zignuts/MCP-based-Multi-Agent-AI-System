import { useState, useRef, useEffect, useCallback } from "react";

const AGENT_ICONS = {
  general:  "🤖",
  code:     "💻",
  data:     "📊",
  research: "🔍",
  document: "📄",
  image:    "🖼️",
};

export default function MessageInput({
  agents,
  attachedFiles,
  disabled,
  isSending,
  isUploading,
  onAttachFiles,
  onClearAttachedFiles,
  onRemoveAttachedFile,
  onSend,
  sendDisabledReason,
  selectedAgent,
  onAgentSelect,
}) {
  const [text, setText] = useState("");
  const [mentionQuery, setMentionQuery] = useState(null); // null = closed, "" = open with no filter
  const [highlightedIndex, setHighlightedIndex] = useState(0);
  const textareaRef = useRef(null);
  const dropdownRef = useRef(null);

  const isSendBlocked =
    disabled ||
    isSending ||
    isUploading ||
    !text.trim() ||
    Boolean(sendDisabledReason);

  // Filter agents list based on what the user typed after @
  const filteredAgents = mentionQuery !== null
    ? agents.filter((a) => a.name.startsWith(mentionQuery.toLowerCase()))
    : [];

  // Detect @ mention as the user types
  const handleChange = useCallback((event) => {
    const value = event.target.value;
    setText(value);

    // Find the last @ in the current text before cursor
    const cursorPos = event.target.selectionStart;
    const textBeforeCursor = value.slice(0, cursorPos);
    const atIdx = textBeforeCursor.lastIndexOf("@");

    if (atIdx !== -1) {
      const query = textBeforeCursor.slice(atIdx + 1);
      // Only trigger if no space in the query (user is still typing the agent name)
      if (!query.includes(" ")) {
        setMentionQuery(query.toLowerCase());
        setHighlightedIndex(0);
        return;
      }
    }
    setMentionQuery(null);
  }, []);

  const selectAgent = useCallback((agent) => {
    // Strip the @<partial query> fragment from the input
    setText((prev) => {
      const atIdx = prev.lastIndexOf("@");
      return atIdx !== -1 ? prev.slice(0, atIdx) : prev;
    });
    onAgentSelect(agent.name);
    setMentionQuery(null);
    textareaRef.current?.focus();
  }, [onAgentSelect]);

  // Keyboard navigation inside the dropdown
  const handleKeyDown = useCallback((event) => {
    if (mentionQuery !== null && filteredAgents.length > 0) {
      if (event.key === "ArrowDown") {
        event.preventDefault();
        setHighlightedIndex((i) => (i + 1) % filteredAgents.length);
        return;
      }
      if (event.key === "ArrowUp") {
        event.preventDefault();
        setHighlightedIndex((i) => (i - 1 + filteredAgents.length) % filteredAgents.length);
        return;
      }
      if (event.key === "Enter") {
        event.preventDefault();
        selectAgent(filteredAgents[highlightedIndex]);
        return;
      }
      if (event.key === "Escape") {
        setMentionQuery(null);
        return;
      }
    }

    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void handleSubmit();
    }
  }, [mentionQuery, filteredAgents, highlightedIndex, selectAgent]);

  const handleSubmit = async () => {
    const trimmed = text.trim();
    if (!trimmed || isSendBlocked) return;

    const wasSent = await onSend({
      content: trimmed,
      fileIds: attachedFiles.map((file) => file.id),
    });

    if (wasSent === false) return;

    setText("");
    onClearAttachedFiles();
    // Do NOT reset selectedAgent here — user keeps the chosen agent across messages
  };

  const handleFileChange = async (event) => {
    const incomingFiles = Array.from(event.target.files || []);
    event.target.value = "";
    if (incomingFiles.length === 0) return;
    await onAttachFiles(incomingFiles);
  };

  // Close dropdown on click outside
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(e.target) &&
        !textareaRef.current?.contains(e.target)
      ) {
        setMentionQuery(null);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const currentAgentIcon = AGENT_ICONS[selectedAgent] || "🤖";
  const currentAgentLabel = agents.find((a) => a.name === selectedAgent)?.label || "General Assistant";

  return (
    <div className="composer-shell">
      {/* Active agent badge shown above the input */}
      {selectedAgent && (
        <div className="agent-badge-bar">
          <span className="agent-badge">
            {currentAgentIcon} {currentAgentLabel}
          </span>
          <button
            className="agent-badge-clear"
            onClick={() => onAgentSelect(null)}
            title="Clear agent selection (auto-route)"
            type="button"
          >
            ✕
          </button>
        </div>
      )}

      {/* @ mention dropdown */}
      {mentionQuery !== null && filteredAgents.length > 0 && (
        <div className="mention-dropdown" ref={dropdownRef} role="listbox" aria-label="Agent suggestions">
          {filteredAgents.map((agent, idx) => (
            <button
              key={agent.name}
              id={`mention-option-${agent.name}`}
              className={`mention-option${idx === highlightedIndex ? " mention-option--highlighted" : ""}`}
              onMouseDown={(e) => { e.preventDefault(); selectAgent(agent); }}
              onMouseEnter={() => setHighlightedIndex(idx)}
              role="option"
              aria-selected={idx === highlightedIndex}
              type="button"
            >
              <span className="mention-option__icon">{AGENT_ICONS[agent.name]}</span>
              <span className="mention-option__name">@{agent.name}</span>
              <span className="mention-option__desc">{agent.description}</span>
            </button>
          ))}
        </div>
      )}

      <div className="composer">
        <div className="composer-main">
          {attachedFiles.length > 0 ? (
            <div className="composer-files">
              {attachedFiles.map((file) => (
                <div className="composer-file-chip" key={file.id}>
                  <span>{file.filename}</span>
                  <span className={`composer-file-status composer-file-status--${file.status}`}>
                    {file.status}
                  </span>
                  <button
                    className="composer-file-remove"
                    disabled={isSending || isUploading}
                    onClick={() => onRemoveAttachedFile(file.id)}
                    type="button"
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>
          ) : null}

          <textarea
            ref={textareaRef}
            className="composer-input"
            disabled={disabled || isSending || isUploading}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            placeholder={
              disabled
                ? "Select or create a conversation"
                : "Type your message... (@ to mention an agent)"
            }
            rows={2}
            value={text}
            aria-label="Chat message input"
            aria-autocomplete="list"
            aria-controls={mentionQuery !== null ? "mention-dropdown" : undefined}
          />
          {sendDisabledReason ? (
            <p className="composer-help-text">{sendDisabledReason}</p>
          ) : null}
          <div className="composer-actions">
            <label className="secondary-button composer-upload-button">
              <input
                className="composer-file-input"
                disabled={disabled || isSending || isUploading}
                multiple
                onChange={handleFileChange}
                type="file"
              />
              Add files
            </label>
          </div>
        </div>
        <button
          className="primary-button"
          disabled={isSendBlocked}
          onClick={() => void handleSubmit()}
          type="button"
        >
          {isUploading ? "Uploading..." : isSending ? "Sending..." : "Send"}
        </button>
      </div>
    </div>
  );
}
