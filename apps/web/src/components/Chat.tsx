import { FormEvent, useEffect, useMemo, useState } from "react";
import { Provider, fetchProviders, streamChat } from "../api";

type Msg = { role: "user" | "assistant"; content: string };

const PROVIDERS: Provider[] = [
  "local",
  "openai",
  "azure_openai",
  "chatgpt",
  "gemini",
  "claude",
  "groq",
  "mistral",
  "cohere",
  "openrouter",
  "together",
  "deepseek",
  "perplexity",
  "ollama",
];

export function Chat() {
  const [sessionId, setSessionId] = useState(`session-${Date.now()}`);
  const [userId, setUserId] = useState("uav-user");
  const [provider, setProvider] = useState<Provider>("local");
  const [providers, setProviders] = useState<Provider[]>(PROVIDERS);
  const [model, setModel] = useState("default");
  const [useRag, setUseRag] = useState(true);
  const [needHITL, setNeedHITL] = useState(false);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Msg[]>([]);
  const [busy, setBusy] = useState(false);

  const canSend = useMemo(() => input.trim().length > 0 && !busy, [input, busy]);

  useEffect(() => {
    fetchProviders()
      .then((items) => {
        if (items.length > 0) {
          setProviders(items);
          if (!items.includes(provider)) {
            setProvider(items[0]);
          }
        }
      })
      .catch(() => {
        // Keep fallback provider list if API is not available.
      });
  }, []);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSend) {
      return;
    }

    const userText = input.trim();
    setInput("");
    setBusy(true);
    setMessages((prev) => [...prev, { role: "user", content: userText }, { role: "assistant", content: "" }]);

    try {
      await streamChat(
        {
          session_id: sessionId,
          user_id: userId,
          message: userText,
          provider,
          model,
          use_rag: useRag,
          require_human_approval: needHITL,
        },
        {
          onStart: (sid) => setSessionId(sid),
          onDelta: (delta) => {
            setMessages((prev) => {
              const copy = [...prev];
              const idx = copy.length - 1;
              if (idx >= 0 && copy[idx].role === "assistant") {
                copy[idx] = { ...copy[idx], content: copy[idx].content + delta };
              }
              return copy;
            });
          },
          onEnd: () => {
            setBusy(false);
          },
        },
      );
    } catch (error) {
      setBusy(false);
      setMessages((prev) => [...prev, { role: "assistant", content: `Error: ${(error as Error).message}` }]);
    }
  }

  return (
    <div className="chat-shell">
      <h1>Agentic Platform</h1>
      <p className="subtitle">ReAct • LangGraph-ready • RAG Hybrid • Multi-Provider</p>

      <div className="controls">
        <label>
          User
          <input value={userId} onChange={(e) => setUserId(e.target.value)} />
        </label>
        <label>
          Session
          <input value={sessionId} onChange={(e) => setSessionId(e.target.value)} />
        </label>
        <label>
          Provider
          <select value={provider} onChange={(e) => setProvider(e.target.value as Provider)}>
            {providers.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </label>
        <label>
          Model
          <input value={model} onChange={(e) => setModel(e.target.value)} />
        </label>
        <label className="check">
          <input type="checkbox" checked={useRag} onChange={(e) => setUseRag(e.target.checked)} />
          Use RAG
        </label>
        <label className="check">
          <input type="checkbox" checked={needHITL} onChange={(e) => setNeedHITL(e.target.checked)} />
          Require HITL
        </label>
      </div>

      <div className="messages">
        {messages.map((msg, index) => (
          <div key={`${msg.role}-${index}`} className={`bubble ${msg.role}`}>
            <strong>{msg.role}</strong>
            <p>{msg.content}</p>
          </div>
        ))}
      </div>

      <form onSubmit={onSubmit} className="composer">
        <textarea value={input} onChange={(e) => setInput(e.target.value)} placeholder="Type message..." rows={4} />
        <button type="submit" disabled={!canSend}>
          {busy ? "Streaming..." : "Send"}
        </button>
      </form>
    </div>
  );
}
