let socket = null;

export const connectWebSocket = (conversationId, onMessage) => {
  socket = new WebSocket(`ws://127.0.0.1:8000/ws/${conversationId}`);

  socket.onmessage = (event) => {
    onMessage(event.data);
  };

  socket.onclose = () => {
    console.log("WebSocket disconnected");
  };
};

export const sendMessage = (message) => {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(message);
  }
};