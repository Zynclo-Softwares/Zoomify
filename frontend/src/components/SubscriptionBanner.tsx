import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
	type BillingStatus,
	createPlatformKey,
	fetchBillingStatus,
	fetchPlatformKeyStatus,
	type PlatformKeyStatus,
	rotatePlatformKey,
} from "../api";
import {
	clearStoredPlatformKey,
	getStoredPlatformKey,
	maskedPlatformKey,
	setStoredPlatformKey,
} from "../platformKeyStorage";
import { showToast } from "../toast";
import "./SubscriptionBanner.css";

export default function SubscriptionBanner() {
	const [status, setStatus] = useState<BillingStatus | null>(null);
	const [keyStatus, setKeyStatus] = useState<PlatformKeyStatus | null>(null);
	const [fullKey, setFullKey] = useState(() => getStoredPlatformKey());
	const [revealed, setRevealed] = useState(false);
	const [keyBusy, setKeyBusy] = useState(false);

	const loadKeyStatus = useCallback(async () => {
		try {
			const next = await fetchPlatformKeyStatus();
			setKeyStatus(next);
			const stored = getStoredPlatformKey();
			if (stored && next.prefix && !stored.startsWith(next.prefix)) {
				clearStoredPlatformKey();
				setFullKey(null);
			} else if (stored) {
				setFullKey(stored);
			}
		} catch {
			setKeyStatus(null);
		}
	}, []);

	useEffect(() => {
		fetchBillingStatus()
			.then(setStatus)
			.catch(() => setStatus(null));
		void loadKeyStatus();
	}, [loadKeyStatus]);

	if (!status) return null;

	const isFree = status.plan === "free";
	const usageLabel = status.unlimited
		? `${status.daily_used} extractions today`
		: `${status.daily_used} / ${status.daily_limit} used today`;

	const onCreateKey = async () => {
		setKeyBusy(true);
		try {
			const created = await createPlatformKey();
			setStoredPlatformKey(created.key);
			setFullKey(created.key);
			setRevealed(true);
			setKeyStatus({
				has_key: true,
				prefix: created.prefix,
				created_at: created.created_at,
			});
			showToast("API key created — copy it now; it won't be shown again.");
		} catch {
			// toast handled by fetchWithAuth
		} finally {
			setKeyBusy(false);
		}
	};

	const onRotateKey = async () => {
		if (
			!window.confirm(
				"Rotate your API key? The current key stops working immediately.",
			)
		) {
			return;
		}
		setKeyBusy(true);
		try {
			const rotated = await rotatePlatformKey();
			setStoredPlatformKey(rotated.key);
			setFullKey(rotated.key);
			setRevealed(true);
			setKeyStatus({
				has_key: true,
				prefix: rotated.prefix,
				created_at: rotated.created_at,
			});
			showToast("API key rotated — copy the new key now.");
		} catch {
			// toast handled by fetchWithAuth
		} finally {
			setKeyBusy(false);
		}
	};

	const displayValue =
		revealed && fullKey ? fullKey : maskedPlatformKey(keyStatus?.prefix);

	return (
		<aside className={`subscription-banner card${isFree ? " free" : ""}`}>
			<div className="subscription-main">
				<span className="subscription-label">Your plan</span>
				<strong className="subscription-plan">{status.plan_name}</strong>
				<span className="subscription-usage">{usageLabel}</span>
				{status.subscription_status !== "none" && (
					<span className="subscription-status">
						{status.subscription_status}
					</span>
				)}
			</div>

			<div className="subscription-api-key">
				<span className="subscription-label">API key</span>
				{keyStatus?.has_key ? (
					<div className="subscription-api-key-row">
						<div className="subscription-api-key-field">
							<input
								className="subscription-api-key-input"
								type={revealed && fullKey ? "text" : "password"}
								value={displayValue}
								readOnly
								spellCheck={false}
								autoComplete="off"
								aria-label="Zoomify platform API key"
							/>
							<button
								type="button"
								className="subscription-api-key-eye"
								onClick={() => setRevealed((v) => !v)}
								disabled={!fullKey}
								title={
									fullKey
										? revealed
											? "Hide API key"
											: "Show API key"
										: "Full key only available after create or rotate in this browser"
								}
								aria-label={revealed ? "Hide API key" : "Show API key"}
							>
								{revealed ? "Hide" : "Show"}
							</button>
						</div>
						<button
							type="button"
							className="btn ghost subscription-api-key-rotate"
							onClick={() => void onRotateKey()}
							disabled={keyBusy}
						>
							Rotate key
						</button>
					</div>
				) : (
					<button
						type="button"
						className="btn ghost subscription-api-key-create"
						onClick={() => void onCreateKey()}
						disabled={keyBusy}
					>
						Create API key
					</button>
				)}
			</div>

			<Link to="/pricing#plans" className="subscription-upgrade">
				{isFree ? "Upgrade plan" : "Change plan"}
			</Link>
		</aside>
	);
}
