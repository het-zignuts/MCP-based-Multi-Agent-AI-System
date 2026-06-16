import React from "react";
import "./AgentSwitcher.css";

export default function AgentSwitcher({ activeAgent }) {
  // Fallback to "general" if no agent selected yet
  const displayName = activeAgent || "general";
  return (
    <div className="agent-switcher">
      <span className="label">Current Agent:</span>
      <span className={`badge badge-${displayName}`}>{displayName}</span>
    </div>
  );
}
