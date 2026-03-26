import { useState } from "react";

export default function MessageInput({
  attachedFiles,
  disabled,
  isSending,
  isUploading,
  onAttachFiles,
  onClearAttachedFiles,
  onRemoveAttachedFile,
  onSend,
  sendDisabledReason,
}) {
  const [text, setText] = useState("");
  const isSendBlocked =
    disabled ||
    isSending ||
    isUploading ||
    !text.trim() ||
    Boolean(sendDisabledReason);

  const handleSubmit = async () => {
    const trimmed = text.trim();
    if (!trimmed || isSendBlocked) {
      return;
    }

    const wasSent = await onSend({
      content: trimmed,
      fileIds: attachedFiles.map((file) => file.id),
    });

    if (wasSent === false) {
      return;
    }

    setText("");
    onClearAttachedFiles();
  };

  const handleKeyDown = (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void handleSubmit();
    }
  };

  const handleFileChange = async (event) => {
    const incomingFiles = Array.from(event.target.files || []);
    event.target.value = "";

    if (incomingFiles.length === 0) {
      return;
    }

    await onAttachFiles(incomingFiles);
  };

  return (
    <div className="composer-shell">
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
            className="composer-input"
            disabled={disabled || isSending || isUploading}
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
