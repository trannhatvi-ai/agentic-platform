import { useState } from "react";
import { Chat } from "./components/Chat";
import UavDashboard from "./components/UavDashboard";

export default function App() {
  const [chatOpen, setChatOpen] = useState(false);

  return (
    <div className="app-shell">
      <section className="mode-panel">
        <UavDashboard />
      </section>

      <button
        type="button"
        className="chat-fab"
        aria-expanded={chatOpen}
        aria-controls="chat-drawer"
        onClick={() => setChatOpen((prev) => !prev)}
      >
        {chatOpen ? "Close Chat" : "Agent Chat"}
      </button>

      {chatOpen && (
        <aside id="chat-drawer" className="chat-drawer" aria-label="Agent chat panel">
          <div className="chat-drawer-header">
            <h2>Agent Chat</h2>
            <button type="button" className="chat-drawer-close" onClick={() => setChatOpen(false)}>
              Close
            </button>
          </div>
          <div className="chat-drawer-body">
            <Chat />
          </div>
        </aside>
      )}
    </div>
  );
}
