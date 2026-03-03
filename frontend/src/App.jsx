import { useEffect, useState } from "react";
import { checkHealth } from "./services/api";
import Sidebar from "./components/Sidebar";
import ChatWindow from "./components/ChatWindow";

function App() {
  const [backendStatus, setBackendStatus] = useState("Checking...");

  useEffect(() => {
    checkHealth()
      .then((data) => setBackendStatus(data.status))
      .catch(() => setBackendStatus("Backend not reachable"));
  }, []);

  return (
    <div style={{ display: "flex", height: "100vh" }}>
      <Sidebar />
      <div style={{ flex: 1 }}>
        <div style={{ padding: "10px", borderBottom: "1px solid #ddd" }}>
          Backend Status: {backendStatus}
        </div>
        <ChatWindow />
      </div>
    </div>
  );
}

export default App;