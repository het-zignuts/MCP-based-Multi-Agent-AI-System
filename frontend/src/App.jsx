import { useEffect, useState } from "react";
import ChatPage from "./pages/ChatPage.jsx";
import AgentSwitcher from "./components/AgentSwitcher.jsx";

function App() {
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [activeAgent, setActiveAgent] = useState("general");

  // Load persisted agent selection
  useEffect(() => {
    const saved = localStorage.getItem("selectedAgent");
    if (saved) setSelectedAgent(saved);
  }, []);

  // Persist when it changes
  useEffect(() => {
    if (selectedAgent) {
      localStorage.setItem("selectedAgent", selectedAgent);
    } else {
      localStorage.removeItem("selectedAgent");
    }
  }, [selectedAgent]);

  return (
    <>
      <AgentSwitcher activeAgent={activeAgent} />
      <ChatPage
        selectedAgent={selectedAgent}
        setSelectedAgent={setSelectedAgent}
        activeAgent={activeAgent}
        setActiveAgent={setActiveAgent}
      />
    </>
  );
}

export default App;
