import MessageList from "./MessageList";
import MessageInput from "./MessageInput";

const AGENT_ICONS = {
  general:  "🤖",
  code:     "💻",
  data:     "📊",
  research: "🔍",
  document: "📄",
  image:    "🖼️",
};

export default function ChatWindow({
  activeAgent,
  agents,
  agentSwitched,
  attachedFiles,
  conversation,
  isLoading,
  isSending,
  isUploading,
  messages,
  onAttachFiles,
  onClearAttachedFiles,
  onRemoveAttachedFile,
  onSend,
  sendDisabledReason,
  selectedAgent,
  onAgentSelect,
}) {
  const agentLabel = agents.find((a) => a.name === activeAgent)?.label || "General Assistant";
  const agentIcon  = AGENT_ICONS[activeAgent] || "🤖";

  return (
    <section className="chat-window">
      {/* Active agent header bar */}
      {conversation && (
        <div className="active-agent-bar">
          <span className="active-agent-indicator">
            <span className="active-agent-dot" />
            {agentIcon} {agentLabel}
          </span>
        </div>
      )}

      <MessageList
        activeAgent={activeAgent}
        agentSwitched={agentSwitched}
        agents={agents}
        conversation={conversation}
        isLoading={isLoading}
        isSending={isSending}
        messages={messages}
      />
      <MessageInput
        agents={agents}
        attachedFiles={attachedFiles}
        disabled={!conversation}
        isSending={isSending}
        isUploading={isUploading}
        onAttachFiles={onAttachFiles}
        onClearAttachedFiles={onClearAttachedFiles}
        onRemoveAttachedFile={onRemoveAttachedFile}
        onSend={onSend}
        sendDisabledReason={sendDisabledReason}
        selectedAgent={selectedAgent}
        onAgentSelect={onAgentSelect}
      />
    </section>
  );
}
