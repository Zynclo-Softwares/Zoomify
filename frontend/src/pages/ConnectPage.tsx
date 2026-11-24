import { SignOutButton, useAuth } from "@clerk/react";
import {
	BookOpen,
	Check,
	Copy,
	Eye,
	EyeOff,
	KeyRound,
	LogOut,
	Plug,
	RefreshCw,
	Upload,
	Wrench,
} from "lucide-react";
import {
	type ChangeEvent,
	type DragEvent,
	type ReactNode,
	useCallback,
	useEffect,
	useMemo,
	useRef,
	useState,
} from "react";
import { Link, Navigate } from "react-router-dom";
import {
	type BillingStatus,
	createPlatformKey,
	fetchBillingStatus,
	fetchHealth,
	fetchMcpInfo,
	fetchPlatformKeyStatus,
	fetchSkills,
	type McpInfo,
	type PlatformKeyStatus,
	rotatePlatformKey,
	type Skill,
	type UploadedImage,
	uploadImage,
} from "../api";
import { isClerkConfigured, setAuthTokenGetter } from "../auth";
import PageLoading from "../components/PageLoading";
import ZoomifyLogo from "../components/ZoomifyLogo";
import {
	CLIENTS,
	EXAMPLE_PROMPT,
	KEY_PLACEHOLDER,
	uploadCurl,
} from "../connectSnippets";
import {
	clearStoredPlatformKey,
	getStoredPlatformKey,
	maskedPlatformKey,
	setStoredPlatformKey,
} from "../platformKeyStorage";
import { openSchemaContact } from "../schemaContact";
import { showErrorToast, showSuccessToast } from "../toast";
import "./ConnectPage.css";

const CLIENT_STORAGE_KEY = "zoomify.connect_client";

function formatNumber(value: number): string {
	return value.toLocaleString("en-US");
}

function formatBytes(bytes: number): string {
	if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
	return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function CopyButton({ text, label }: { text: string; label: string }) {
	const [copied, setCopied] = useState(false);

	const onCopy = async () => {
		try {
			await navigator.clipboard.writeText(text);
			setCopied(true);
			window.setTimeout(() => setCopied(false), 1600);
		} catch {
			showErrorToast("Could not copy to clipboard.");
		}
	};

	return (
		<button
			type="button"
			className="copy-btn"
			onClick={() => void onCopy()}
			aria-label={label}
			title={label}
		>
			{copied ? (
				<Check size={14} aria-hidden="true" />
			) : (
				<Copy size={14} aria-hidden="true" />
			)}
			<span>{copied ? "Copied" : "Copy"}</span>
		</button>
	);
}

function CodeBlock({
	code,
	copyText,
	caption,
}: {
	code: string;
	copyText?: string;
	caption?: string;
}) {
	return (
		<div className="code-block">
			<div className="code-block-head">
				<span className="code-block-caption">{caption}</span>
				<CopyButton text={copyText ?? code} label="Copy snippet" />
			</div>
			<pre>
				<code>{code}</code>
			</pre>
		</div>
	);
}

function Step({
	index,
	icon,
	title,
	lead,
	children,
}: {
	index?: number;
	icon: ReactNode;
	title: string;
	lead?: ReactNode;
	children: ReactNode;
}) {
	return (
		<section className="connect-step card">
			<header className="connect-step-head">
				<span className="connect-step-badge" aria-hidden="true">
					{index ?? icon}
				</span>
				<div>
					<h2>{title}</h2>
					{lead && <p className="connect-step-lead">{lead}</p>}
				</div>
			</header>
			<div className="connect-step-body">{children}</div>
		</section>
	);
}

function ApiKeyCard({
	fullKey,
	onKeyChange,
}: {
	fullKey: string | null;
	onKeyChange: (key: string | null) => void;
}) {
	const [keyStatus, setKeyStatus] = useState<PlatformKeyStatus | null>(null);
	const [loaded, setLoaded] = useState(false);
	const [revealed, setRevealed] = useState(false);
	const [busy, setBusy] = useState(false);

	useEffect(() => {
		fetchPlatformKeyStatus()
			.then((next) => {
				setKeyStatus(next);
				const stored = getStoredPlatformKey();
				if (stored && (!next.prefix || !stored.startsWith(next.prefix))) {
					clearStoredPlatformKey();
					onKeyChange(null);
				}
			})
			.catch(() => setKeyStatus(null))
			.finally(() => setLoaded(true));
	}, [onKeyChange]);

	const store = (
		created: { key: string; prefix: string; created_at: string },
		message: string,
	) => {
		setStoredPlatformKey(created.key);
		onKeyChange(created.key);
		setRevealed(true);
		setKeyStatus({
			has_key: true,
			prefix: created.prefix,
			created_at: created.created_at,
		});
		showSuccessToast(message);
	};

	const onCreate = async () => {
		setBusy(true);
		try {
			store(
				await createPlatformKey(),
				"API key created. Copy it now — it is only shown in this browser.",
			);
		} catch {
			// toast handled by fetchWithAuth
		} finally {
			setBusy(false);
		}
	};

	const onRotate = async () => {
		if (
			!window.confirm(
				"Rotate your API key? Agents using the current key stop working immediately.",
			)
		) {
			return;
		}
		setBusy(true);
		try {
			store(
				await rotatePlatformKey(),
				"API key rotated. Update your agent configs with the new key.",
			);
		} catch {
			// toast handled by fetchWithAuth
		} finally {
			setBusy(false);
		}
	};

	if (!loaded) {
		return <p className="connect-muted">Loading key…</p>;
	}

	if (!keyStatus?.has_key) {
		return (
			<div className="key-empty">
				<p className="connect-muted">
					You don&apos;t have a key yet. One key works for every agent you
					connect.
				</p>
				<button
					type="button"
					className="btn primary"
					onClick={() => void onCreate()}
					disabled={busy}
				>
					<KeyRound size={15} aria-hidden="true" />
					Create API key
				</button>
			</div>
		);
	}

	const shown =
		revealed && fullKey ? fullKey : maskedPlatformKey(keyStatus.prefix);

	return (
		<div className="key-row-wrap">
			<div className="key-row">
				<input
					className="key-input"
					type="text"
					value={shown}
					readOnly
					spellCheck={false}
					autoComplete="off"
					aria-label="Zoomify API key"
				/>
				<button
					type="button"
					className="icon-btn"
					onClick={() => setRevealed((v) => !v)}
					disabled={!fullKey}
					aria-label={revealed ? "Hide API key" : "Show API key"}
					title={revealed ? "Hide API key" : "Show API key"}
				>
					{revealed && fullKey ? (
						<EyeOff size={16} aria-hidden="true" />
					) : (
						<Eye size={16} aria-hidden="true" />
					)}
				</button>
				{fullKey && <CopyButton text={fullKey} label="Copy API key" />}
				<button
					type="button"
					className="icon-btn"
					onClick={() => void onRotate()}
					disabled={busy}
					aria-label="Rotate API key"
					title="Rotate API key"
				>
					<RefreshCw size={16} aria-hidden="true" />
				</button>
			</div>
			{!fullKey && (
				<p className="connect-hint">
					The full key is only kept in the browser where it was created. Rotate
					it to get a new one here — the snippets below use a placeholder until
					then.
				</p>
			)}
		</div>
	);
}

function UsageCard({ status }: { status: BillingStatus | null }) {
	if (!status) return null;
	const pct = Math.min(
		100,
		Math.round((status.monthly_used / Math.max(1, status.monthly_limit)) * 100),
	);
	const resets = new Date(status.resets_at).toLocaleDateString(undefined, {
		month: "short",
		day: "numeric",
	});
	const isFree = status.plan === "free";

	return (
		<aside className="usage-card card" aria-label="Plan and usage">
			<div className="usage-head">
				<div>
					<span className="usage-label">Your plan</span>
					<strong className="usage-plan">{status.plan_name}</strong>
				</div>
				<Link to="/pricing#plans" className="btn ghost usage-upgrade">
					{isFree ? "Upgrade" : "Change plan"}
				</Link>
			</div>
			<div
				className="usage-bar"
				role="progressbar"
				aria-valuemin={0}
				aria-valuemax={status.monthly_limit}
				aria-valuenow={status.monthly_used}
				aria-label="Requests used this month"
			>
				<span
					className={`usage-bar-fill${pct >= 90 ? " high" : ""}`}
					style={{ width: `${pct}%` }}
				/>
			</div>
			<p className="usage-line">
				<strong>{formatNumber(status.monthly_used)}</strong> of{" "}
				{formatNumber(status.monthly_limit)} requests used · resets {resets}
			</p>
			<dl className="usage-facts">
				<div>
					<dt>Rate limit</dt>
					<dd>{status.rate_limit_per_minute}/min</dd>
				</div>
				<div>
					<dt>Max file</dt>
					<dd>{status.max_image_mb} MB</dd>
				</div>
				<div>
					<dt>Open images</dt>
					<dd>{status.max_open_images}</dd>
				</div>
			</dl>
		</aside>
	);
}

function UploadCard({
	uploadUrl,
	keyForSnippets,
}: {
	uploadUrl: string;
	keyForSnippets: string;
}) {
	const [busy, setBusy] = useState(false);
	const [dragging, setDragging] = useState(false);
	const [result, setResult] = useState<UploadedImage | null>(null);
	const inputRef = useRef<HTMLInputElement>(null);

	const send = async (file: File | undefined) => {
		if (!file || busy) return;
		setBusy(true);
		try {
			setResult(await uploadImage(file));
		} catch {
			// toast handled by fetchWithAuth
		} finally {
			setBusy(false);
			if (inputRef.current) inputRef.current.value = "";
		}
	};

	const onDrop = (event: DragEvent<HTMLLabelElement>) => {
		event.preventDefault();
		setDragging(false);
		void send(event.dataTransfer.files?.[0]);
	};

	return (
		<div className="upload-grid">
			<div>
				<h3>Public file</h3>
				<p className="connect-muted">
					Give the agent the link. It calls <code>open_image(image_url=…)</code>{" "}
					and the server downloads it.
				</p>
				<h3>Local or private file</h3>
				<p className="connect-muted">
					Just give the agent the file path. It calls{" "}
					<code>request_upload</code>, gets a one-time upload link, sends the
					file from disk, and opens it. The link needs no API key, so the agent
					never touches yours.
				</p>
				<p className="connect-muted">
					To upload by hand instead, drop the file here or use your key:
				</p>
				<CodeBlock
					caption="Terminal"
					code={uploadCurl(uploadUrl, keyForSnippets)}
				/>
			</div>
			<div>
				<h3>Or upload here</h3>
				<label
					className={`dropzone${dragging ? " dragging" : ""}${busy ? " busy" : ""}`}
					onDragOver={(e) => {
						e.preventDefault();
						setDragging(true);
					}}
					onDragLeave={() => setDragging(false)}
					onDrop={onDrop}
				>
					<Upload size={20} aria-hidden="true" />
					<span>
						{busy ? "Uploading…" : "Drop an image or PDF, or click to choose"}
					</span>
					<input
						ref={inputRef}
						type="file"
						accept="image/*,application/pdf"
						disabled={busy}
						onChange={(e: ChangeEvent<HTMLInputElement>) =>
							void send(e.target.files?.[0])
						}
					/>
				</label>
				{result && (
					<div className="upload-result">
						<div className="upload-result-row">
							<code>{result.image_id}</code>
							<CopyButton text={result.image_id} label="Copy image id" />
						</div>
						<p className="connect-hint">
							{result.filename || "File"} · {formatBytes(result.bytes)}
							{result.kind === "pdf" ? ` · ${result.pages} page(s)` : ""} ·
							available for 1 hour. Tell your agent:{" "}
							<em>“open image_id {result.image_id} with Zoomify”</em>.
						</p>
					</div>
				)}
				<p className="connect-hint">
					Uploads are free and private to your account.
				</p>
			</div>
		</div>
	);
}

function SkillsList({ skills }: { skills: Skill[] }) {
	return (
		<div className="skills-list">
			{skills.map((skill) => (
				<details key={skill.name} className="skill-item">
					<summary>
						<span className="skill-title">{skill.title}</span>
						<code className="skill-name">{skill.name}</code>
						<span className="skill-desc">{skill.description}</span>
					</summary>
					<div className="skill-body">
						<div className="skill-actions">
							<a
								className="btn ghost"
								href={`/api/skills/${skill.name}.md`}
								download={`${skill.name}.md`}
							>
								Download .md
							</a>
							{skill.body && (
								<CopyButton text={skill.body} label="Copy skill text" />
							)}
						</div>
						<pre>{skill.body}</pre>
					</div>
				</details>
			))}
		</div>
	);
}

function ConnectDashboard({ signOut }: { signOut?: ReactNode }) {
	const [info, setInfo] = useState<McpInfo | null>(null);
	const [skills, setSkills] = useState<Skill[]>([]);
	const [status, setStatus] = useState<BillingStatus | null>(null);
	const [online, setOnline] = useState<boolean | null>(null);
	const [fullKey, setFullKey] = useState<string | null>(() =>
		getStoredPlatformKey(),
	);
	const [clientId, setClientId] = useState(() => {
		try {
			return localStorage.getItem(CLIENT_STORAGE_KEY) ?? CLIENTS[0].id;
		} catch {
			return CLIENTS[0].id;
		}
	});

	useEffect(() => {
		fetchHealth().then((h) => setOnline(h.ok));
		fetchMcpInfo()
			.then(setInfo)
			.catch(() => setInfo(null));
		fetchSkills()
			.then(setSkills)
			.catch(() => setSkills([]));
		fetchBillingStatus()
			.then(setStatus)
			.catch(() => setStatus(null));
	}, []);

	const onKeyChange = useCallback((key: string | null) => setFullKey(key), []);

	const selectClient = (id: string) => {
		setClientId(id);
		try {
			localStorage.setItem(CLIENT_STORAGE_KEY, id);
		} catch {
			// ignore storage failures
		}
	};

	const mcpUrl = info?.url ?? `${window.location.origin}/mcp`;
	const uploadUrl = info?.upload_url ?? `${window.location.origin}/api/images`;
	const client = CLIENTS.find((c) => c.id === clientId) ?? CLIENTS[0];
	const snippetKey = fullKey ?? KEY_PLACEHOLDER;
	const snippet = useMemo(
		() => client.build(mcpUrl, snippetKey),
		[client, mcpUrl, snippetKey],
	);

	return (
		<div className="connect">
			<div className="landing-glow landing-glow-a" aria-hidden />
			<div className="landing-glow landing-glow-b" aria-hidden />

			<header className="connect-topbar">
				<Link to="/" className="connect-brand">
					<ZoomifyLogo size={32} />
					<span>Zoomify</span>
					<span className="connect-brand-tag">MCP</span>
				</Link>
				<nav className="connect-nav" aria-label="Site">
					<Link to="/pricing">Pricing</Link>
					<a href="/api/docs" target="_blank" rel="noopener noreferrer">
						API docs
					</a>
					<a
						href="https://github.com/Zynclo-Softwares/Zoomify"
						target="_blank"
						rel="noopener noreferrer"
					>
						GitHub
					</a>
				</nav>
				<div className="connect-topbar-actions">
					<span
						className={`status-pill ${online === null ? "warn" : online ? "ok" : "error"}`}
					>
						<span className="status-dot" aria-hidden="true" />
						{online === null
							? "Checking…"
							: online
								? "Server online"
								: "Server offline"}
					</span>
					{signOut}
				</div>
			</header>

			<main className="connect-main">
				<div className="connect-intro">
					<h1>Connect your agent to Zoomify</h1>
					<p>
						Zoomify is a remote MCP server. Add it to any agent and it gains
						grid-and-zoom tools for reading large drawings, scans, long
						screenshots, and PDFs without guessing at the small print.
					</p>
				</div>

				<div className="connect-layout">
					<div className="connect-steps">
						<Step
							index={1}
							icon={<KeyRound size={16} />}
							title="Get your API key"
							lead="Agents authenticate with this key. Keep it secret; rotate it if it leaks."
						>
							<ApiKeyCard fullKey={fullKey} onKeyChange={onKeyChange} />
						</Step>

						<Step
							index={2}
							icon={<Plug size={16} />}
							title="Add the server to your agent"
							lead={
								<>
									Endpoint <code>{mcpUrl}</code> · Streamable HTTP ·{" "}
									<code>Authorization: Bearer &lt;key&gt;</code>
								</>
							}
						>
							<div className="client-tabs" role="tablist" aria-label="Agent">
								{CLIENTS.map((c) => (
									<button
										key={c.id}
										type="button"
										role="tab"
										aria-selected={c.id === client.id}
										className={`client-tab${c.id === client.id ? " active" : ""}`}
										onClick={() => selectClient(c.id)}
									>
										{c.label}
									</button>
								))}
							</div>
							<CodeBlock caption={client.target} code={snippet} />
							{client.note && <p className="connect-hint">{client.note}</p>}
							{!fullKey && (
								<p className="connect-hint">
									Replace <code>{KEY_PLACEHOLDER}</code> with your key.
								</p>
							)}
						</Step>

						<Step
							index={3}
							icon={<Upload size={16} />}
							title="Give it an image"
							lead="The server runs in the cloud and cannot read files on your machine. Agents upload local files themselves through a one-time link."
						>
							<UploadCard uploadUrl={uploadUrl} keyForSnippets={snippetKey} />
						</Step>

						<Step
							index={4}
							icon={<BookOpen size={16} />}
							title="Ask your agent"
							lead="Any wording works. Mentioning the skill makes the first run more reliable."
						>
							<div className="code-wrap">
								<CodeBlock caption="Example prompt" code={EXAMPLE_PROMPT} />
							</div>
						</Step>
					</div>

					<div className="connect-side">
						<UsageCard status={status} />

						<section className="side-card card">
							<h2>
								<Wrench size={15} aria-hidden="true" /> Tools
							</h2>
							<ul className="tool-list">
								{(info?.tools ?? []).map((tool) => (
									<li key={tool.name}>
										<div className="tool-line">
											<code>{tool.name}</code>
											<span
												className={`tool-tag${tool.metered ? " metered" : ""}`}
											>
												{tool.metered ? "1 request" : "free"}
											</span>
										</div>
										<p>{tool.summary}</p>
									</li>
								))}
							</ul>
						</section>

						<section className="side-card card side-contact">
							<h2>Need skills for your documents?</h2>
							<p>
								Zynclo writes custom skills for your drawing standards and
								forms, and can set up higher limits.
							</p>
							<button
								type="button"
								className="btn ghost"
								onClick={openSchemaContact}
							>
								Talk to us
							</button>
						</section>
					</div>
				</div>

				<section className="connect-skills card">
					<header>
						<h2>
							<BookOpen size={16} aria-hidden="true" /> Skills
						</h2>
						<p className="connect-muted">
							Short playbooks that teach an agent to use the tools well. They
							are served by the MCP server itself (as prompts, resources, and
							the <code>read_skill</code> tool), so there is nothing to install
							— or download one to keep as a local skill file.
						</p>
					</header>
					<SkillsList skills={skills} />
				</section>
			</main>
		</div>
	);
}

function AuthenticatedConnect() {
	const { isLoaded, isSignedIn, getToken } = useAuth();
	const [ready, setReady] = useState(false);

	useEffect(() => {
		if (isSignedIn) {
			setAuthTokenGetter(() => getToken());
			setReady(true);
		}
	}, [getToken, isSignedIn]);

	if (!isLoaded) {
		return <PageLoading label="Checking session…" />;
	}
	if (!isSignedIn) {
		return <Navigate to="/sign-in" replace />;
	}
	if (!ready) {
		return <PageLoading label="Loading Zoomify…" />;
	}

	return (
		<ConnectDashboard
			signOut={
				<SignOutButton redirectUrl="/">
					<button
						type="button"
						className="icon-btn"
						aria-label="Sign out"
						title="Sign out"
					>
						<LogOut size={16} aria-hidden="true" />
					</button>
				</SignOutButton>
			}
		/>
	);
}

export default function ConnectPage() {
	if (!isClerkConfigured()) {
		return <ConnectDashboard />;
	}
	return <AuthenticatedConnect />;
}
