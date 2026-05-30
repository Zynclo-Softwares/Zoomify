import { FormEvent, useEffect, useRef, useState } from "react";
import {
  ChatMessage,
  fetchHealth,
  fetchModels,
  streamQuery,
} from "./api";

const DEFAULT_PROMPT =
  "Extract the key information from this image; zoom in to read any small text.";

export default function App() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [trailHtml, setTrailHtml] = useState("");
  const [query, setQuery] = useState("");
  const [image, setImage] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [models, setModels] = useState<string[]>([]);
  const [model, setModel] = useState("");
  const [schema, setSchema] = useState("");
  const [structured, setStructured] = useState(true);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [hasKey, setHasKey] = useState(false);
  const [busy, setBusy] = useState(false);
  const [schemaInfo, setSchemaInfo] = useState<string>("");
  const trailRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchHealth().then((h) => setHasKey(h.has_api_key));
    fetchModels()
      .then((m) => {
        setModels(m.choices);
        setModel(m.default);
      })
      .catch(() => setModels([]));
  }, []);

  useEffect(() => {
    if (!image) {
      setImagePreview(null);
      return;
    }
    const url = URL.createObjectURL(image);
    setImagePreview(url);
    return () => URL.revokeObjectURL(url);
  }, [image]);

  const onImageChange = (file: File | undefined) => {
    if (!file) {
      setImage(null);
      return;
    }
    if (!file.type.startsWith("image/")) {
      alert("Only image files are accepted.");
      return;
    }
    setImage(file);
  };

  const resetSession = async () => {
    if (sessionId) {
      await fetch(`/api/session/${sessionId}`, { method: "DELETE" }).catch(() => {});
    }
    setSessionId(null);
    setMessages([]);
    setTrailHtml("");
    setQuery("");
    setImage(null);
    setSchemaInfo("");
  };

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (busy) return;
    const text = query.trim();
    if (!text && !image) return;

    setBusy(true);
    setSchemaInfo("");

    try {
      for await (const event of streamQuery({
        query: text || DEFAULT_PROMPT,
        image,
        model,
        schema: schema || undefined,
        structured,
        sessionId,
      })) {
        if (event.type === "session") {
          setSessionId(event.session_id);
        } else if (event.type === "user") {
          setMessages((prev) => [...prev, { role: "user", content: event.content }]);
        } else if (event.type === "trail") {
          setTrailHtml(event.html);
        } else if (event.type === "schema") {
          if (event.structured && event.schema_id) {
            setSchemaInfo(`Structured: ${event.schema_id} (${event.source})`);
          } else {
            setSchemaInfo("Unstructured text response");
          }
        } else if (event.type === "assistant") {
          setMessages((prev) => [...prev, { role: "assistant", content: event.content }]);
        } else if (event.type === "error") {
          setMessages((prev) => [...prev, { role: "assistant", content: `❌ ${event.message}` }]);
          break;
        } else if (event.type === "done") {
          setQuery("");
          setImage(null);
        }
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `❌ ${err instanceof Error ? err.message : String(err)}` },
      ]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="app">
      <header className="header">
        <h1>Zoomify</h1>
        <p className="subtitle">
          Image detail extraction with zoom trail ·{" "}
          {hasKey ? "✅ API key detected" : "⚠️ set OPENROUTER_API_KEY on server"}
        </p>
        <div className="controls">
          <label>
            Vision model
            <select value={model} onChange={(e) => setModel(e.target.value)} disabled={busy}>
              {models.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </label>
          <label>
            Schema id (optional)
            <input
              type="text"
              placeholder="acme-sld-v1"
              value={schema}
              onChange={(e) => setSchema(e.target.value)}
              disabled={busy}
            />
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={structured}
              onChange={(e) => setStructured(e.target.checked)}
              disabled={busy}
            />
            Structured output
          </label>
          <button type="button" onClick={resetSession} disabled={busy}>
            Reset session
          </button>
        </div>
        {schemaInfo && <p className="schema-info">{schemaInfo}</p>}
        <aside className="schema-cta">
          Need a business schema?{" "}
          <a href="https://github.com/Zynclo-Softwares/Zoomify/issues/new">
            Request a custom schema from Zynclo
          </a>
        </aside>
      </header>

      <main className="layout">
        <section className="panel chat-panel">
          <h2>Conversation</h2>
          <div className="messages">
            {messages.length === 0 && (
              <p className="hint">Upload an image and ask a question to begin.</p>
            )}
            {messages.map((m, i) => (
              <div key={i} className={`msg msg-${m.role}`}>
                <strong>{m.role === "user" ? "You" : "Zoomify"}</strong>
                <div className="msg-body">{m.content}</div>
              </div>
            ))}
          </div>
          <form className="composer" onSubmit={onSubmit}>
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Ask about the image…"
              rows={3}
              disabled={busy}
            />
            <div className="composer-row">
              <label className="file-btn">
                + Image
                <input
                  type="file"
                  accept="image/*"
                  onChange={(e) => onImageChange(e.target.files?.[0])}
                  disabled={busy}
                />
              </label>
              {imagePreview && (
                <img src={imagePreview} alt="preview" className="thumb-preview" />
              )}
              <button type="submit" disabled={busy || (!query.trim() && !image)}>
                {busy ? "Working…" : "Send"}
              </button>
            </div>
          </form>
        </section>

        <section className="panel trail-panel">
          <h2>Zoom trail</h2>
          <div
            ref={trailRef}
            className="trail-host"
            dangerouslySetInnerHTML={{ __html: trailHtml || "<p class='hint'>Trail updates live during zoom.</p>" }}
          />
        </section>
      </main>
    </div>
  );
}
