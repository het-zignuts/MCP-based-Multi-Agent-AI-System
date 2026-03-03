function MessageBubble({ role, content }) {
  const isUser = role === "user";

  return (
    <div
      style={{
        textAlign: isUser ? "right" : "left",
        marginBottom: "10px"
      }}
    >
      <span
        style={{
          display: "inline-block",
          padding: "10px 14px",
          borderRadius: "16px",
          background: isUser ? "#007bff" : "#e5e5ea",
          color: isUser ? "white" : "black",
          maxWidth: "60%"
        }}
      >
        {content}
      </span>
    </div>
  );
}

export default MessageBubble;