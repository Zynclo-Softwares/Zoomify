import {
	type FormEvent,
	useCallback,
	useEffect,
	useRef,
	useState,
} from "react";
import {
	ApiKeyInvalidError,
	type ChatMessage,
	deleteSession,
	fetchHealth,
	fetchModels,
	streamQuery,
} from "./api";
import {
	clearStoredApiKey,
	rememberKeyFingerprint,
	validateStoredKey,
} from "./byok";
import ApiKeyField from "./components/ApiKeyField";
import MarkdownMessage from "./components/MarkdownMessage";
import ModelCombobox, {
	MODEL_COMBOBOX_INPUT_ID,
} from "./components/ModelCombobox";
import ProductSignOut from "./components/ProductSignOut";
import SubscriptionBanner from "./components/SubscriptionBanner";
import TrailHost from "./components/TrailHost";
import ZoomifyLogo from "./components/ZoomifyLogo";

const DEFAULT_PROMPT =
	"Extract the key information from this image; zoom in to read any small text.";

const DEFAULT_MODEL = "anthropic/claude-opus-4.8-fast";

const SCHEMA_CTA_MS = 5000;
const SCHEMA_CTA_FADE_MS = 500;

function nextMessageId(): string {
	return crypto.randomUUID();
}

export default function App() {
	const [messages, setMessages] = useState<ChatMessage[]>([]);
	const [trailHtml, setTrailHtml] = useState("");
	const [query, setQuery] = useState("");
	const [image, setImage] = useState<File | null>(null);
	const [imagePreview, setImagePreview] = useState<string | null>(null);
	const [models, setModels] = useState<string[]>([]);
	const [model, setModel] = useState("");
	const [sessionId, setSessionId] = useState<string | null>(null);
	const [hasKey, setHasKey] = useState(false);
	const [changingKey, setChangingKey] = useState(false);
	const [modelsError, setModelsError] = useState("");
	const [busy, setBusy] = useState(false);
	const [schemaInfo, setSchemaInfo] = useState<string>("");
	const [schemaCtaVisible, setSchemaCtaVisible] = useState(true);
	const [schemaCtaLeaving, setSchemaCtaLeaving] = useState(false);
	const schemaCtaDismissedRef = useRef(false);
	const messagesEndRef = useRef<HTMLDivElement>(null);

	const dismissSchemaCta = useCallback(() => {
		if (schemaCtaDismissedRef.current) return;
		schemaCtaDismissedRef.current = true;
		setSchemaCtaLeaving(true);
		window.setTimeout(() => setSchemaCtaVisible(false), SCHEMA_CTA_FADE_MS);
	}, []);

	useEffect(() => {
		const timer = window.setTimeout(dismissSchemaCta, SCHEMA_CTA_MS);
		return () => window.clearTimeout(timer);
	}, [dismissSchemaCta]);

	const loadModels = useCallback(async () => {
		try {
			const m = await fetchModels();
			setModels(m.choices);
			setModel(m.default);
			setModelsError("");
			await rememberKeyFingerprint();
		} catch (err) {
			if (err instanceof ApiKeyInvalidError) {
				clearStoredApiKey();
				setHasKey(false);
				setModels([]);
				setModel("");
				setModelsError(err.message);
				return;
			}
			setModels([]);
			setModel(DEFAULT_MODEL);
			setModelsError("Could not load models — type a model id manually.");
		}
	}, []);

	useEffect(() => {
		void (async () => {
			fetchHealth().catch(() => {});
			const valid = await validateStoredKey();
			setHasKey(valid);
			if (valid) await loadModels();
		})();
	}, [loadModels]);

	const onApiKeyChange = useCallback(
		(ready: boolean) => {
			setHasKey(ready);
			setModelsError("");
			if (ready) {
				setChangingKey(false);
				void loadModels();
				return;
			}
			setChangingKey(false);
			setModels([]);
			setModel("");
		},
		[loadModels],
	);

	useEffect(() => {
		if (messages.length === 0 && !busy) return;
		messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
	}, [messages.length, busy]);

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
			await deleteSession(sessionId).catch(() => {});
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
				sessionId,
			})) {
				if (event.type === "session") {
					setSessionId(event.session_id);
				} else if (event.type === "user") {
					setMessages((prev) => [
						...prev,
						{ id: nextMessageId(), role: "user", content: event.content },
					]);
				} else if (event.type === "trail") {
					setTrailHtml(event.html);
				} else if (event.type === "schema") {
					if (event.structured && event.schema_id) {
						setSchemaInfo(`Structured · ${event.schema_id} (${event.source})`);
					} else {
						setSchemaInfo("Free-text response");
					}
				} else if (event.type === "assistant") {
					setMessages((prev) => [
						...prev,
						{ id: nextMessageId(), role: "assistant", content: event.content },
					]);
				} else if (event.type === "error") {
					setMessages((prev) => [
						...prev,
						{ id: nextMessageId(), role: "assistant", content: event.message },
					]);
					break;
				} else if (event.type === "done") {
					setQuery("");
					setImage(null);
				}
			}
		} catch (err) {
			setMessages((prev) => [
				...prev,
				{
					id: nextMessageId(),
					role: "assistant",
					content: err instanceof Error ? err.message : String(err),
				},
			]);
		} finally {
			setBusy(false);
		}
	};

	return (
		<div className="app">
			<div className="bg-glow bg-glow-a" aria-hidden />
			<div className="bg-glow bg-glow-b" aria-hidden />

			<header className="header">
				<div className="brand">
					<ZoomifyLogo size={48} className="logo-mark" />
					<div>
						<h1>
							Zoomify
							<span className="brand-tag">by Zynclo</span>
						</h1>
						<p className="subtitle">
							Precision extraction from complex images — maps, diagrams, scans
							&amp; tiny text.
						</p>
					</div>
					<div className="header-actions">
						<ProductSignOut />
					</div>
				</div>

				<SubscriptionBanner />

				<div
					className={`toolbar card${hasKey && !changingKey ? " toolbar-controls" : " toolbar-byok"}`}
				>
					{hasKey && !changingKey ? (
						<>
							<div className="field field-model">
								<label htmlFor={MODEL_COMBOBOX_INPUT_ID}>Model</label>
								<ModelCombobox
									models={models}
									value={model}
									onChange={setModel}
									disabled={busy}
								/>
							</div>
							<button
								type="button"
								className="btn ghost"
								onClick={() => setChangingKey(true)}
								disabled={busy}
							>
								Change key
							</button>
							<span className="status-pill ok key-status">Key ready</span>
							<button
								type="button"
								className="btn ghost"
								onClick={resetSession}
								disabled={busy}
							>
								Reset
							</button>
						</>
					) : (
						<>
							<ApiKeyField
								disabled={busy}
								changing={changingKey}
								onKeyChange={onApiKeyChange}
							/>
							{changingKey && hasKey && (
								<button
									type="button"
									className="btn ghost"
									onClick={() => setChangingKey(false)}
									disabled={busy}
								>
									Cancel
								</button>
							)}
						</>
					)}
				</div>

				{modelsError && hasKey && (
					<p className="schema-info models-info">{modelsError}</p>
				)}

				{schemaInfo && <p className="schema-info">{schemaInfo}</p>}

				{schemaCtaVisible && (
					<aside
						className={`schema-cta card${schemaCtaLeaving ? " leaving" : ""}`}
					>
						<button
							type="button"
							className="schema-cta-close"
							aria-label="Dismiss"
							onClick={dismissSchemaCta}
						>
							×
						</button>
						<ZoomifyLogo size={28} className="cta-icon" decorative />
						<div>
							<strong>Need a business schema?</strong>
							<p>
								Tell us your use case — Zynclo designs custom extraction schemas
								for your documents.{" "}
								<a href="https://github.com/Zynclo-Softwares/Zoomify/issues/new">
									Request schema →
								</a>
							</p>
						</div>
					</aside>
				)}
			</header>

			<main className="layout">
				<section className="panel card chat-panel">
					<div className="panel-head">
						<h2>Conversation</h2>
						{busy && <span className="live-badge">Agent working</span>}
					</div>

					<div className="messages">
						{messages.length === 0 && (
							<div className="empty-state">
								<div className="empty-brand">
									<ZoomifyLogo size={72} className="empty-logo" decorative />
									<p className="empty-brand-name">Zoomify</p>
								</div>
								<p className="empty-title">Upload &amp; ask</p>
								<p className="hint">
									Attach a high-resolution map, diagram, or scan. Zoomify grids
									the image and zooms into the details for you.
								</p>
							</div>
						)}
						{messages.map((m) => (
							<div key={m.id} className={`msg msg-${m.role}`}>
								<div className="msg-head">
									{m.role === "assistant" && (
										<ZoomifyLogo size={22} decorative />
									)}
									<strong>{m.role === "user" ? "You" : "Zoomify"}</strong>
								</div>
								<div className="msg-body">
									{m.role === "assistant" ? (
										<MarkdownMessage content={m.content} />
									) : (
										m.content
									)}
								</div>
							</div>
						))}
						<div ref={messagesEndRef} />
					</div>

					<form className="composer" onSubmit={onSubmit}>
						{imagePreview && (
							<div className="composer-preview">
								<img src={imagePreview} alt="Attached preview" />
							</div>
						)}
						<div className="composer-box">
							<textarea
								value={query}
								onChange={(e) => setQuery(e.target.value)}
								placeholder="What should we extract from this image?"
								rows={3}
								disabled={busy}
							/>
							<div className="composer-actions">
								<label
									className="composer-icon-btn"
									title="Attach image"
									aria-label="Attach image"
								>
									<svg viewBox="0 0 24 24" aria-hidden="true">
										<path
											d="M16.5 6.5v8.25a4.5 4.5 0 1 1-9 0V7.5a3 3 0 1 1 6 0v7.5a1.5 1.5 0 1 1-3 0V7.5"
											fill="none"
											stroke="currentColor"
											strokeWidth="1.75"
											strokeLinecap="round"
										/>
									</svg>
									<input
										type="file"
										accept="image/*"
										onChange={(e) => onImageChange(e.target.files?.[0])}
										disabled={busy}
									/>
								</label>
								<button
									type="submit"
									className="composer-icon-btn composer-send"
									title={busy ? "Extracting…" : "Send"}
									aria-label={busy ? "Extracting" : "Send"}
									disabled={busy || (!query.trim() && !image)}
								>
									{busy ? (
										<svg
											viewBox="0 0 24 24"
											className="spin"
											aria-hidden="true"
										>
											<circle
												cx="12"
												cy="12"
												r="9"
												fill="none"
												stroke="currentColor"
												strokeWidth="2"
												strokeDasharray="28 56"
											/>
										</svg>
									) : (
										<svg viewBox="0 0 24 24" aria-hidden="true">
											<path
												d="M5 12h12M13 7l5 5-5 5"
												fill="none"
												stroke="currentColor"
												strokeWidth="1.75"
												strokeLinecap="round"
												strokeLinejoin="round"
											/>
										</svg>
									)}
								</button>
							</div>
						</div>
					</form>
				</section>

				<section className="panel card tree-panel">
					<div className="panel-head">
						<h2>Zoom tree</h2>
						<span className="panel-meta">Live trail</span>
					</div>
					<TrailHost html={trailHtml} />
				</section>
			</main>

			<footer className="footer">
				<ZoomifyLogo size={20} decorative />
				<span>
					Zoomify · Powered by{" "}
					<a
						href="https://zynclo.com"
						target="_blank"
						rel="noopener noreferrer"
					>
						zynclo.com
					</a>
				</span>
			</footer>
		</div>
	);
}
