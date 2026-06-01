import {
	ArrowRight,
	DraftingCompass,
	MessageCircle,
	MessagesSquare,
	Paperclip,
	PenLine,
	RefreshCw,
	ScanText,
	Settings,
	Square,
} from "lucide-react";
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
import { fetchSampleImageFile, type SampleImageId } from "./sampleImage";

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
	const [showHomeEmpty, setShowHomeEmpty] = useState(true);
	const schemaCtaDismissedRef = useRef(false);
	const messagesRef = useRef<HTMLDivElement>(null);
	const composerRef = useRef<HTMLTextAreaElement>(null);
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

	const focusApiKey = useCallback(() => {
		window.requestAnimationFrame(() => {
			const input = document.querySelector<HTMLInputElement>(
				".openrouter-key-input",
			);
			if (input) {
				input.focus();
				input.scrollIntoView({ block: "center", behavior: "smooth" });
				return;
			}
			setSettingsOpen(true);
		});
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

	// biome-ignore lint/correctness/useExhaustiveDependencies: re-scroll as zoom crumbs stream in
	useEffect(() => {
		if (messages.length === 0 && !busy) return;
		const el = messagesRef.current;
		if (!el) return;
		el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
	}, [messages.length, busy, trailHtml]);

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

	const runQuery = useCallback(
		async (opts?: { image?: File | null; text?: string }) => {
			if (busy) return;
			const text = (opts?.text ?? query).trim();
			const imageToSend = opts?.image !== undefined ? opts.image : image;
			if (!text && !imageToSend) return;

			setQuery("");

			queryAbortRef.current?.abort();
			const abortController = new AbortController();
			queryAbortRef.current = abortController;

			setBusy(true);
			setSchemaInfo("");
			dismissHomeEmpty();

			try {
				for await (const event of streamQuery({
					query: text || DEFAULT_PROMPT,
					image: imageToSend,
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
							setSchemaInfo(
								`Structured · ${event.schema_id} (${event.source})`,
							);
						} else {
							setSchemaInfo("Free-text response");
						}
					} else if (event.type === "assistant") {
						setMessages((prev) => [
							...prev,
							{
								id: nextMessageId(),
								role: "assistant",
								content: event.content,
							},
						]);
					} else if (event.type === "error") {
						setMessages((prev) => [
							...prev,
							{
								id: nextMessageId(),
								role: "assistant",
								content: event.message,
							},
						]);
						break;
					} else if (event.type === "cancelled") {
						break;
					} else if (event.type === "done") {
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
		},
		[
			busy,
			query,
			image,
			model,
			sessionId,
			clearAttachedImage,
			dismissHomeEmpty,
		],
	);

	const onSubmit = async (e: FormEvent) => {
		e.preventDefault();
		await runQuery();
	};

	const attachSampleImage = useCallback(
		async (sampleId: SampleImageId) => {
			if (busy) return;
			try {
				const file = await fetchSampleImageFile(sampleId);
				dismissHomeEmpty();
				setImage(file);
				if (hasKey) {
					composerRef.current?.focus();
					return;
				}
				focusApiKey();
			} catch {
				// Sample is optional if the static asset is unavailable.
			}
		},
		[busy, dismissHomeEmpty, focusApiKey, hasKey],
	);

	return (
		<div className="app">
			<div className="bg-glow bg-glow-a" aria-hidden />
			<div className="bg-glow bg-glow-b" aria-hidden />

			<header className="header product-topbar">
				<div className="product-topbar-inner">
					<div className="product-brand">
						<ZoomifyLogo size={32} className="logo-mark" />
						<span className="brand-name">Zoomify</span>
						{busy && <span className="live-badge">Working</span>}
					</div>

					<nav className="product-nav" aria-label="Workspace views">
						<button
							type="button"
							className="product-nav-item active"
							aria-current="page"
						>
							<MessageCircle size={16} aria-hidden="true" />
							<span>Chat</span>
						</button>
						<button
							type="button"
							className="product-nav-item"
							aria-haspopup="dialog"
							aria-expanded={settingsOpen}
							onClick={() => setSettingsOpen(true)}
						>
							<Settings size={16} aria-hidden="true" />
							<span>Settings</span>
						</button>
					</nav>

					<div className="product-topbar-actions">
						<StatusIndicator hasKey={hasKey} />
						<ProductSignOut />
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
				<section className="panel card chat-panel">
					<div className="panel-head">
						<div className="panel-head-title">
							<MessagesSquare
								size={20}
								className="panel-head-lucide"
								aria-hidden="true"
							/>
							<h2>Conversation</h2>
						</div>
						<div className="panel-head-meta">
							{schemaInfo && (
								<span className="schema-info-inline">{schemaInfo}</span>
							)}
							<button
								type="button"
								className="panel-icon-btn"
								onClick={() => void resetSession()}
								disabled={busy}
								title="Reset conversation"
								aria-label="Reset conversation"
							>
								<RefreshCw size={16} aria-hidden="true" />
							</button>
						</div>
					</div>

					<div className="messages" ref={messagesRef}>
						{messages.length === 0 && showHomeEmpty && !busy && (
							<div className="empty-state">
								<div className="empty-brand">
									<span className="empty-icon-box">
										<ZoomifyLogo size={44} className="empty-logo" decorative />
									</span>
									<p className="empty-brand-name">ZOOMIFY</p>
								</div>
								<p className="empty-title">Start extracting</p>
								<p className="hint">
									Attach a fuzzy-text, blueprint, or handwriting sample, add
									your OpenRouter key, then ask what to extract.
									<span className="empty-hint-desktop">
										{" "}
										Or attach with the paperclip / paste with{" "}
										<kbd className="kbd-hint">⌘V</kbd> /{" "}
										<kbd className="kbd-hint">Ctrl+V</kbd>.
									</span>
								</p>
								<div className="empty-actions">
									<button
										type="button"
										className="empty-action-btn"
										onClick={() => void attachSampleImage("fuzzy-text")}
										disabled={busy}
									>
										<ScanText
											size={16}
											className="empty-action-icon"
											aria-hidden="true"
										/>
										Fuzzy text
									</button>
									<button
										type="button"
										className="empty-action-btn"
										onClick={() => void attachSampleImage("blueprint")}
										disabled={busy}
									>
										<DraftingCompass
											size={16}
											className="empty-action-icon"
											aria-hidden="true"
										/>
										Blueprint
									</button>
									<button
										type="button"
										className="empty-action-btn"
										onClick={() => void attachSampleImage("handwriting")}
										disabled={busy}
									>
										<PenLine
											size={16}
											className="empty-action-icon"
											aria-hidden="true"
										/>
										Handwriting
									</button>
								</div>
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
						{busy && (
							<div
								className="msg msg-assistant msg-loading"
								aria-live="polite"
								aria-busy="true"
							>
								<div className="msg-head">
									<ZoomifyLogo size={22} decorative />
									<strong>Zoomify</strong>
								</div>
								<div className="msg-body">
									<TrailHost html={trailHtml} variant="inline" />
								</div>
							</div>
						)}
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
										ref={composerRef}
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
												<Paperclip size={16} aria-hidden="true" />
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
													<Square
														size={14}
														fill="currentColor"
														aria-hidden="true"
													/>
												</button>
											) : (
												<button
													type="submit"
													className="composer-icon-btn composer-send"
													title="Send"
													aria-label="Send"
													disabled={!query.trim() && !image}
												>
													<ArrowRight size={16} aria-hidden="true" />
												</button>
											)}
										</div>
									</div>
								</div>
							</form>
						)}
					</div>
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
