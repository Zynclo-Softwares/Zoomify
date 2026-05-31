import {
	type FormEvent,
	type ClipboardEvent as ReactClipboardEvent,
	type KeyboardEvent as ReactKeyboardEvent,
	useCallback,
	useEffect,
	useRef,
	useState,
} from "react";
import { createPortal } from "react-dom";
import "./App.css";
import {
	ApiKeyInvalidError,
	type ChatMessage,
	deleteSession,
	fetchModels,
	streamQuery,
} from "./api";
import {
	clearStoredApiKey,
	rememberKeyFingerprint,
	validateStoredKey,
} from "./byok";
import {
	imageFileFromClipboard,
	isClipboardPasteTargetAllowed,
} from "./clipboardImage";
import ApiKeyField from "./components/ApiKeyField";
import MarkdownMessage from "./components/MarkdownMessage";
import ModelCombobox from "./components/ModelCombobox";
import ProductSettingsDrawer from "./components/ProductSettingsDrawer";
import ProductSignOut from "./components/ProductSignOut";
import StatusIndicator from "./components/StatusIndicator";
import TrailHost from "./components/TrailHost";
import ZoomifyLogo from "./components/ZoomifyLogo";
import {
	getStoredModel,
	resolveModelPreference,
	setStoredModel,
} from "./modelPreference";
import {
	fetchSampleImageFile,
	SAMPLE_IMAGE_FILENAME,
	SAMPLE_IMAGE_URL,
} from "./sampleImage";

const DEFAULT_PROMPT =
	"Extract the key information from this image; zoom in to read any small text.";

const DEFAULT_MODEL = "anthropic/claude-opus-4.8-fast";

const SCHEMA_CTA_MS = 5000;
const SCHEMA_CTA_FADE_MS = 500;

function nextMessageId(): string {
	return crypto.randomUUID();
}

function PanelViewToggle({
	mobileView,
	onChange,
}: {
	mobileView: "chat" | "tree";
	onChange: (view: "chat" | "tree") => void;
}) {
	return (
		<div className="panel-view-toggle" role="tablist" aria-label="Workspace">
			<button
				type="button"
				role="tab"
				className={mobileView === "chat" ? "active" : ""}
				aria-selected={mobileView === "chat"}
				onClick={() => onChange("chat")}
			>
				Chat
			</button>
			<button
				type="button"
				role="tab"
				className={mobileView === "tree" ? "active" : ""}
				aria-selected={mobileView === "tree"}
				onClick={() => onChange("tree")}
			>
				Tree
			</button>
		</div>
	);
}

export default function App() {
	const [messages, setMessages] = useState<ChatMessage[]>([]);
	const [trailHtml, setTrailHtml] = useState("");
	const [query, setQuery] = useState("");
	const [image, setImage] = useState<File | null>(null);
	const [imagePreview, setImagePreview] = useState<string | null>(null);
	const [imagePreviewOpen, setImagePreviewOpen] = useState(false);
	const [models, setModels] = useState<string[]>([]);
	const [model, setModel] = useState(() => getStoredModel() ?? "");
	const [sessionId, setSessionId] = useState<string | null>(null);
	const [hasKey, setHasKey] = useState(false);
	const [modelsError, setModelsError] = useState("");
	const [busy, setBusy] = useState(false);
	const [schemaInfo, setSchemaInfo] = useState<string>("");
	const [schemaCtaVisible, setSchemaCtaVisible] = useState(true);
	const [schemaCtaLeaving, setSchemaCtaLeaving] = useState(false);
	const [settingsOpen, setSettingsOpen] = useState(false);
	const [mobileView, setMobileView] = useState<"chat" | "tree">("chat");
	const [showHomeEmpty, setShowHomeEmpty] = useState(true);
	const schemaCtaDismissedRef = useRef(false);
	const messagesEndRef = useRef<HTMLDivElement>(null);
	const fileInputRef = useRef<HTMLInputElement>(null);
	const queryAbortRef = useRef<AbortController | null>(null);

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
			setModel(resolveModelPreference(m.default));
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
			setModel(resolveModelPreference(DEFAULT_MODEL));
			setModelsError("Could not load models — type a model id manually.");
		}
	}, []);

	const onModelChange = useCallback((next: string) => {
		setModel(next);
		setStoredModel(next);
	}, []);

	const dismissHomeEmpty = useCallback(() => {
		setShowHomeEmpty(false);
	}, []);

	useEffect(() => {
		void (async () => {
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
				void loadModels();
				return;
			}
			setModels([]);
			setModel("");
		},
		[loadModels],
	);

	const onReplaceOpenRouterKey = useCallback(() => {
		if (
			!window.confirm(
				"Remove your OpenRouter key? You'll need to add it again to continue.",
			)
		) {
			return;
		}
		clearStoredApiKey();
		onApiKeyChange(false);
	}, [onApiKeyChange]);

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

	const onImageChange = useCallback(
		(file: File | undefined) => {
			if (!file) {
				setImage(null);
				return;
			}
			if (!file.type.startsWith("image/")) {
				alert("Only image files are accepted.");
				return;
			}
			setImage(file);
			dismissHomeEmpty();
		},
		[dismissHomeEmpty],
	);

	const selectSampleImage = useCallback(async () => {
		if (busy) return;
		try {
			setImage(await fetchSampleImageFile());
			dismissHomeEmpty();
		} catch {
			// Sample is optional if the static asset is unavailable.
		}
	}, [busy, dismissHomeEmpty]);

	const onQueryChange = (value: string) => {
		if (showHomeEmpty && value.trim().length > 0) {
			dismissHomeEmpty();
		}
		setQuery(value);
	};

	const attachClipboardImage = useCallback(
		(data: DataTransfer | null) => {
			const file = imageFileFromClipboard(data);
			if (!file) return false;
			onImageChange(file);
			return true;
		},
		[onImageChange],
	);

	const onComposerPaste = (event: ReactClipboardEvent<HTMLTextAreaElement>) => {
		if (busy) return;
		if (attachClipboardImage(event.clipboardData)) {
			event.preventDefault();
		}
	};

	const onComposerKeyDown = (
		event: ReactKeyboardEvent<HTMLTextAreaElement>,
	) => {
		if (event.key !== "Enter" || event.shiftKey) return;
		event.preventDefault();
		if (busy || (!query.trim() && !image)) return;
		event.currentTarget.form?.requestSubmit();
	};

	useEffect(() => {
		if (!hasKey || busy) return;

		const onPaste = (event: ClipboardEvent) => {
			if (!isClipboardPasteTargetAllowed(event.target)) return;
			if (attachClipboardImage(event.clipboardData)) {
				event.preventDefault();
			}
		};

		document.addEventListener("paste", onPaste);
		return () => document.removeEventListener("paste", onPaste);
	}, [hasKey, busy, attachClipboardImage]);

	const clearAttachedImage = useCallback(() => {
		setImage(null);
		setImagePreviewOpen(false);
		if (fileInputRef.current) fileInputRef.current.value = "";
	}, []);

	useEffect(() => {
		if (!imagePreviewOpen) return;
		const onKeyDown = (event: KeyboardEvent) => {
			if (event.key === "Escape") setImagePreviewOpen(false);
		};
		window.addEventListener("keydown", onKeyDown);
		return () => window.removeEventListener("keydown", onKeyDown);
	}, [imagePreviewOpen]);

	const resetSession = async () => {
		if (sessionId) {
			await deleteSession(sessionId).catch(() => {});
		}
		setSessionId(null);
		setMessages([]);
		setTrailHtml("");
		setQuery("");
		setSchemaInfo("");
		setShowHomeEmpty(true);
		clearAttachedImage();
	};

	const onStop = () => {
		queryAbortRef.current?.abort();
	};

	const onSubmit = async (e: FormEvent) => {
		e.preventDefault();
		if (busy) return;
		const text = query.trim();
		if (!text && !image) return;

		queryAbortRef.current?.abort();
		const abortController = new AbortController();
		queryAbortRef.current = abortController;

		setBusy(true);
		setSchemaInfo("");

		try {
			for await (const event of streamQuery({
				query: text || DEFAULT_PROMPT,
				image,
				model,
				sessionId,
				signal: abortController.signal,
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
				} else if (event.type === "cancelled") {
					break;
				} else if (event.type === "done") {
					setQuery("");
					clearAttachedImage();
				}
			}
		} catch (err) {
			if (err instanceof DOMException && err.name === "AbortError") {
				return;
			}
			setMessages((prev) => [
				...prev,
				{
					id: nextMessageId(),
					role: "assistant",
					content: err instanceof Error ? err.message : String(err),
				},
			]);
		} finally {
			if (queryAbortRef.current === abortController) {
				queryAbortRef.current = null;
			}
			setBusy(false);
		}
	};

	return (
		<div className="app">
			<div className="bg-glow bg-glow-a" aria-hidden />
			<div className="bg-glow bg-glow-b" aria-hidden />

			<header className="header header-compact">
				<div className="header-bar">
					<div className="brand-compact">
						<ZoomifyLogo size={36} className="logo-mark" />
						<h1 className="brand-name">Zoomify</h1>
						{busy && <span className="live-badge">Working</span>}
					</div>
					<div className="header-bar-actions">
						<StatusIndicator hasKey={hasKey} />
						<ProductSignOut />
						<button
							type="button"
							className="product-menu-btn"
							aria-label="Open settings"
							aria-expanded={settingsOpen}
							onClick={() => setSettingsOpen(true)}
						>
							<svg viewBox="0 0 24 24" aria-hidden="true">
								<path
									d="M4 7h16M4 12h16M4 17h16"
									fill="none"
									stroke="currentColor"
									strokeWidth="1.75"
									strokeLinecap="round"
								/>
							</svg>
						</button>
					</div>
				</div>
			</header>

			<ProductSettingsDrawer
				open={settingsOpen}
				onClose={() => setSettingsOpen(false)}
				schemaCtaVisible={schemaCtaVisible}
				schemaCtaLeaving={schemaCtaLeaving}
				onDismissSchemaCta={dismissSchemaCta}
			/>

			<main className="layout">
				<section
					className={`panel card chat-panel${mobileView === "tree" ? " mobile-hidden" : ""}`}
				>
					<div className="panel-head">
						<div className="panel-head-title">
							<h2>Conversation</h2>
							<button
								type="button"
								className="panel-icon-btn"
								onClick={() => void resetSession()}
								disabled={busy}
								title="Reset conversation"
								aria-label="Reset conversation"
							>
								<svg viewBox="0 0 24 24" aria-hidden="true">
									<path
										d="M4 4v6h6M20 20v-6h-6M5 19a9 9 0 0 0 14-2M19 5a9 9 0 0 0-14 2"
										fill="none"
										stroke="currentColor"
										strokeWidth="1.75"
										strokeLinecap="round"
										strokeLinejoin="round"
									/>
								</svg>
							</button>
						</div>
						<div className="panel-head-meta">
							{schemaInfo && (
								<span className="schema-info-inline">{schemaInfo}</span>
							)}
							{busy && <span className="live-badge">Agent working</span>}
							<PanelViewToggle
								mobileView={mobileView}
								onChange={setMobileView}
							/>
						</div>
					</div>

					<div className="messages">
						{messages.length === 0 && showHomeEmpty && (
							<div className="empty-state">
								<div className="empty-brand">
									<ZoomifyLogo size={72} className="empty-logo" decorative />
									<p className="empty-brand-name">Zoomify</p>
								</div>
								<p className="empty-title">Try a sample image</p>
								<p className="hint">
									Click the demo image below to attach it, add your OpenRouter
									key, ask a question, and send. Or use the paperclip / paste
									with <kbd className="kbd-hint">⌘V</kbd> /{" "}
									<kbd className="kbd-hint">Ctrl+V</kbd>.
								</p>
								<button
									type="button"
									className="empty-sample"
									onClick={() => void selectSampleImage()}
									disabled={busy}
									title="Use sample image"
									aria-label="Use sample image"
								>
									<span className="empty-sample-frame">
										<img src={SAMPLE_IMAGE_URL} alt="" />
									</span>
									<span className="empty-sample-caption">
										Click to attach · {SAMPLE_IMAGE_FILENAME}
									</span>
								</button>
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

					<div className="composer">
						{!hasKey ? (
							<div className="composer-box composer-box-setup">
								<ApiKeyField disabled={busy} onKeyChange={onApiKeyChange} />
							</div>
						) : (
							<form onSubmit={onSubmit}>
								{imagePreview && (
									<div className="composer-preview">
										<div className="composer-preview-chip">
											<button
												type="button"
												className="composer-preview-thumb"
												onClick={() => setImagePreviewOpen(true)}
												title="View full image"
												aria-label="View attached image full size"
											>
												<img src={imagePreview} alt="" />
											</button>
											<button
												type="button"
												className="composer-preview-remove"
												onClick={clearAttachedImage}
												disabled={busy}
												title="Remove image"
												aria-label="Remove attached image"
											>
												×
											</button>
										</div>
									</div>
								)}
								<div className="composer-box">
									<textarea
										value={query}
										onChange={(e) => onQueryChange(e.target.value)}
										onPaste={onComposerPaste}
										onKeyDown={onComposerKeyDown}
										placeholder="What should we extract from this image? Enter to send, Shift+Enter for new line."
										rows={3}
										disabled={busy}
									/>
									<div className="composer-toolbar">
										<div className="composer-toolbar-left">
											<ModelCombobox
												models={models}
												value={model}
												onChange={onModelChange}
												onReplaceKey={onReplaceOpenRouterKey}
												disabled={busy}
											/>
											{modelsError && (
												<span className="composer-models-error">
													{modelsError}
												</span>
											)}
										</div>
										<div className="composer-toolbar-right">
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
													ref={fileInputRef}
													type="file"
													accept="image/*"
													onChange={(e) => onImageChange(e.target.files?.[0])}
													disabled={busy}
												/>
											</label>
											{busy ? (
												<button
													type="button"
													className="composer-icon-btn composer-stop"
													title="Stop extraction"
													aria-label="Stop extraction"
													onClick={onStop}
												>
													<svg viewBox="0 0 24 24" aria-hidden="true">
														<rect
															x="7"
															y="7"
															width="10"
															height="10"
															rx="1.5"
															fill="currentColor"
														/>
													</svg>
												</button>
											) : (
												<button
													type="submit"
													className="composer-icon-btn composer-send"
													title="Send"
													aria-label="Send"
													disabled={!query.trim() && !image}
												>
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
												</button>
											)}
										</div>
									</div>
								</div>
							</form>
						)}
					</div>
				</section>

				<section
					className={`panel card tree-panel${mobileView === "chat" ? " mobile-hidden" : ""}`}
				>
					<div className="panel-head">
						<h2>Zoom tree</h2>
						<PanelViewToggle mobileView={mobileView} onChange={setMobileView} />
					</div>
					<TrailHost html={trailHtml} />
				</section>
			</main>
			{imagePreviewOpen &&
				imagePreview &&
				createPortal(
					<div
						className="zmodal"
						role="dialog"
						aria-modal="true"
						aria-label="Attached image preview"
					>
						<button
							type="button"
							className="zbackdrop"
							aria-label="Close preview"
							onClick={() => setImagePreviewOpen(false)}
						/>
						<div className="zcontent">
							<button
								type="button"
								className="zclose"
								aria-label="Close preview"
								onClick={() => setImagePreviewOpen(false)}
							>
								×
							</button>
							<img
								src={imagePreview}
								alt={image?.name || "Attached upload preview"}
							/>
							{image?.name && <div className="zcap">{image.name}</div>}
						</div>
					</div>,
					document.body,
				)}
		</div>
	);
}
