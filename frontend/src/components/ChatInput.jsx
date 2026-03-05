import { useState } from "react";

function ChatInput({ onSend }) {
  const [input, setInput] = useState("");

  const handleSend = () => {
    if (!input.trim()) return;
    onSend(input);
    setInput("");
  };

  return (
    <div style={{ display: "flex", padding: "10px", borderTop: "1px solid #ddd" }}>
      <input
        style={{ flex: 1, padding: "10px" }}
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder="Type message..."
      />
      <button onClick={handleSend} style={{ marginLeft: "10px" }}>
        Send
      </button>
    </div>
  );
}

export default ChatInput;