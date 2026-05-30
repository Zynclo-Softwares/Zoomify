import { useEffect, useRef, useState } from "react";
import {
	clearStoredApiKey,
	fetchByokPublicKey,
	hasStoredApiKey,
	saveApiKey,
} from "../byok";

type Props = {
	disabled?: boolean;
	changing?: boolean;
	onKeyChange?: (hasKey: boolean) => void;
};

export default function ApiKeyField({
	disabled = false,
	changing = false,
	onKeyChange,
}: Props) {
	const [saved, setSaved] = useState(hasStoredApiKey());
	const [draft, setDraft] = useState("");
	const [busy, setBusy] = useState(false);
	const [error, setError] = useState("");
	const inputRef = useRef<HTMLInputElement>(null);

	useEffect(() => {
		fetchByokPublicKey().catch(() => {
			setError("Encryption unavailable");
		});
	}, []);

	useEffect(() => {
		if (!changing || disabled || busy) return;
		inputRef.current?.focus();
	}, [changing, disabled, busy]);

	const notify = (hasKey: boolean) => {
		setSaved(hasKey);
		onKeyChange?.(hasKey);
	};

	const persistKey = async () => {
		setError("");
		if (!draft.trim()) {
			if (!saved) return;
			clearStoredApiKey();
			setDraft("");
			notify(false);
			return;
		}
		setBusy(true);
		try {
			await saveApiKey(draft);
			setDraft("");
			notify(true);
		} catch (err) {
			setError(err instanceof Error ? err.message : "Could not save key");
		} finally {
			setBusy(false);
		}
	};

	const clearKey = () => {
		clearStoredApiKey();
		setDraft("");
		setError("");
		notify(false);
	};

	return (
		<div className="field field-key">
			<div className="field-label-row">
				<label htmlFor="openrouter-api-key">OpenRouter key</label>
				<a
					className="field-external-link"
					href="https://openrouter.ai/keys"
					target="_blank"
					rel="noopener noreferrer"
				>
					openrouter.ai
				</a>
			</div>
			<div className="key-row">
				<input
					ref={inputRef}
					id="openrouter-api-key"
					type="password"
					value={draft}
					onChange={(e) => setDraft(e.target.value)}
					onBlur={() => void persistKey()}
					onKeyDown={(e) => {
						if (e.key === "Enter") {
							e.preventDefault();
							void persistKey();
						}
					}}
					placeholder="Open router api key"
					autoComplete="off"
					spellCheck={false}
					disabled={disabled || busy}
				/>
				{saved && !draft && !changing ? (
					<span className="status-pill ok key-status">Key ready</span>
				) : (
					<span className="status-pill warn key-status">
						Add OpenRouter key
					</span>
				)}
				{saved && !changing && (
					<button
						type="button"
						className="btn ghost key-clear"
						onClick={clearKey}
						disabled={disabled || busy}
					>
						Clear
					</button>
				)}
			</div>
			{error && <p className="key-error">{error}</p>}
		</div>
	);
}
