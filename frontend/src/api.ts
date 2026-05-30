export type ChatMessage = { role: "user" | "assistant"; content: string };

export type StreamEvent =
  | { type: "session"; session_id: string }
  | { type: "user"; content: string }
  | { type: "trail"; html: string }
  | { type: "assistant"; content: string }
  | { type: "schema"; structured: boolean; schema_id: string | null; source: string }
  | { type: "error"; message: string }
  | { type: "done" };

export async function fetchModels(): Promise<{ choices: string[]; default: string }> {
  const res = await fetch("/api/models");
  if (!res.ok) throw new Error("Failed to load models");
  return res.json();
}

export async function fetchHealth(): Promise<{ ok: boolean; has_api_key: boolean }> {
  const res = await fetch("/api/health");
  return res.json();
}

export async function* streamQuery(params: {
  query: string;
  image?: File | null;
  model: string;
  schema?: string;
  structured: boolean;
  sessionId?: string | null;
}): AsyncGenerator<StreamEvent> {
  const form = new FormData();
  form.append("query", params.query);
  form.append("model", params.model);
  form.append("structured", String(params.structured));
  if (params.schema?.trim()) form.append("schema", params.schema.trim());
  if (params.sessionId) form.append("session_id", params.sessionId);
  if (params.image) form.append("image", params.image);

  const res = await fetch("/api/query", { method: "POST", body: form });
  if (!res.ok || !res.body) {
    throw new Error(`Query failed (${res.status})`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      if (!line.trim()) continue;
      yield JSON.parse(line) as StreamEvent;
    }
  }
  if (buffer.trim()) {
    yield JSON.parse(buffer) as StreamEvent;
  }
}
