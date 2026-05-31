import { useEffect, useRef, useState } from "react";
import { fetchByokPublicKey, saveApiKey } from "../byok";

type Props = {
	disabled?: boolean;
	onKeyChange?: (hasKey: boolean) => void;
};

export default function ApiKeyField({ disabled = false, onKeyChange }: Props) {
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
		if (disabled || busy) return;
		inputRef.current?.focus();
	}, [disabled, busy]);

	const notify = (hasKey: boolean) => {
		onKeyChange?.(hasKey);
	};

	const persistKey = async () => {
		setError("");
		if (!draft.trim()) return;
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

	return (
		<div className="openrouter-key-form openrouter-key-form-composer">
			<div className="openrouter-key-head">
				<p className="openrouter-key-lead">
					Add your OpenRouter key to start extracting from images.
				</p>
				<a
					className="openrouter-key-link"
					href="https://openrouter.ai/keys"
					target="_blank"
					rel="noopener noreferrer"
				>
					Get a key at openrouter.ai
				</a>
			</div>
			<div className="openrouter-key-row">
				<input
					ref={inputRef}
					id="openrouter-api-key"
					className="openrouter-key-input"
					type="password"
					value={draft}
					onChange={(e) => setDraft(e.target.value)}
					onKeyDown={(e) => {
						if (e.key === "Enter") {
							e.preventDefault();
							void persistKey();
						}
					}}
					placeholder="OpenRouter API key"
					autoComplete="off"
					spellCheck={false}
					disabled={disabled || busy}
					aria-label="OpenRouter API key"
				/>
				<button
					type="button"
					className="btn primary openrouter-key-submit openrouter-key-submit-inline"
					onClick={() => void persistKey()}
					disabled={disabled || busy || !draft.trim()}
				>
					Add
				</button>
			</div>
			{error && <p className="key-error">{error}</p>}
		</div>
	);
}
