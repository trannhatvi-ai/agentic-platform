export type Provider =
  | "local"
  | "openai"
  | "azure_openai"
  | "chatgpt"
  | "gemini"
  | "claude"
  | "groq"
  | "mistral"
  | "cohere"
  | "openrouter"
  | "together"
  | "deepseek"
  | "perplexity"
  | "ollama";

export interface StreamPayload {
  session_id: string;
  user_id: string;
  message: string;
  provider: Provider;
  model: string;
  use_rag: boolean;
  require_human_approval: boolean;
}

export interface StreamHandlers {
  onStart: (sessionId: string) => void;
  onDelta: (delta: string) => void;
  onEnd: (meta: Record<string, unknown>) => void;
}

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";
const API_KEY = import.meta.env.VITE_API_KEY ?? "dev-key";

export async function fetchProviders(): Promise<Provider[]> {
  const response = await fetch(`${API_BASE}/providers`);
  if (!response.ok) {
    throw new Error(`Failed to load providers (${response.status})`);
  }
  const data = (await response.json()) as { providers: Provider[] };
  return data.providers;
}

export async function streamChat(payload: StreamPayload, handlers: StreamHandlers): Promise<void> {
  const response = await fetch(`${API_BASE}/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-key": API_KEY,
      "x-user-id": payload.user_id,
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok || !response.body) {
    throw new Error(`Streaming failed (${response.status})`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });

    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";

    for (const part of parts) {
      const lines = part.split("\n");
      const eventLine = lines.find((line) => line.startsWith("event:"));
      const dataLine = lines.find((line) => line.startsWith("data:"));
      if (!eventLine || !dataLine) {
        continue;
      }
      const eventName = eventLine.replace("event:", "").trim();
      const data = JSON.parse(dataLine.replace("data:", "").trim()) as Record<string, unknown>;

      if (eventName === "start") {
        handlers.onStart(String(data.session_id));
      }
      if (eventName === "delta") {
        handlers.onDelta(String(data.delta ?? ""));
      }
      if (eventName === "end") {
        handlers.onEnd(data);
      }
    }
  }
}
