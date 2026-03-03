import { useEffect, useRef, useState } from "react";
import { connectWebSocket, sendMessage } from "../services/websocket";
import MessageBubble from "./MessageBubble";
import ChatInput from "./ChatInput";

function ChatWindow() {
  const [messages, setMessages] = useState([]);
  const hasConnected = useRef(false);

  useEffect(() => {
    if (hasConnected.current) return;
    hasConnected.current = true;

    connectWebSocket(1, (msg) => {
      setMessages((prev) => [...prev, { role: "assistant", content: msg }]);
    });
  }, []);

  const handleSend = (text) => {
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    sendMessage(text);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div style={{ flex: 1, overflowY: "auto", padding: "20px" }}>
        {messages.map((msg, index) => (
          <MessageBubble
            key={index}
            role={msg.role}
            content={msg.content}
          />
        ))}
      </div>
      <ChatInput onSend={handleSend} />
    </div>
  );
}

export default ChatWindow;