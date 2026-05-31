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
import { showErrorToast, showInfoToast, showSuccessToast } from "../toast";
import "./SubscriptionBanner.css";

function EyeIcon({ hidden }: { hidden: boolean }) {
	if (hidden) {
		return (
			<svg viewBox="0 0 24 24" aria-hidden="true">
				<path
					d="M3 3l18 18M10.6 10.6a2 2 0 0 0 2.8 2.8M9.9 5.1A10.7 10.7 0 0 1 12 5c5 0 9.3 3 11 7-1 2.2-2.8 4-5 5.2M6.7 6.7C4.5 8.1 3 10 2 12c1.7 4 6 7 10 7 1.1 0 2.2-.2 3.2-.6"
					fill="none"
					stroke="currentColor"
					strokeWidth="1.75"
					strokeLinecap="round"
				/>
			</svg>
		);
	}
	return (
		<svg viewBox="0 0 24 24" aria-hidden="true">
			<path
				d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z"
				fill="none"
				stroke="currentColor"
				strokeWidth="1.75"
			/>
			<circle
				cx="12"
				cy="12"
				r="3"
				fill="none"
				stroke="currentColor"
				strokeWidth="1.75"
			/>
		</svg>
	);
}

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
			showSuccessToast("API key created — view or copy it below.");
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
			showSuccessToast("API key rotated — your new key is shown below.");
		} catch {
			// toast handled by fetchWithAuth
		} finally {
			setKeyBusy(false);
		}
	};

	const onCopyKey = async () => {
		if (!fullKey) {
			showInfoToast(
				"Copy unavailable — create or rotate the key in this browser first.",
			);
			return;
		}
		try {
			await navigator.clipboard.writeText(fullKey);
			showSuccessToast("API key copied.");
		} catch {
			showErrorToast("Could not copy to clipboard.");
		}
	};

	const displayValue =
		revealed && fullKey ? fullKey : maskedPlatformKey(keyStatus?.prefix);

	return (
		<aside className={`subscription-banner card${isFree ? " free" : ""}`}>
			<div className="subscription-plan-row">
				<div className="subscription-main">
					<span className="subscription-label">Your plan</span>
					<div className="subscription-plan-line">
						<strong className="subscription-plan">{status.plan_name}</strong>
						<span className="subscription-usage">{usageLabel}</span>
						{status.subscription_status !== "none" && (
							<span className="subscription-status">
								{status.subscription_status}
							</span>
						)}
					</div>
				</div>
				<Link to="/pricing#plans" className="subscription-upgrade">
					{isFree ? "Upgrade plan" : "Change plan"}
				</Link>
			</div>

			<div className="subscription-api-key">
				<span className="subscription-label">API key</span>
				{keyStatus?.has_key ? (
					<div className="subscription-api-key-row">
						<input
							className="subscription-api-key-input"
							type={revealed && fullKey ? "text" : "password"}
							value={displayValue}
							readOnly
							spellCheck={false}
							autoComplete="off"
							aria-label="Zoomify platform API key"
						/>
						<div className="subscription-api-key-actions">
							<button
								type="button"
								className="subscription-api-key-icon-btn"
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
								<EyeIcon hidden={revealed && Boolean(fullKey)} />
							</button>
							<button
								type="button"
								className="subscription-api-key-icon-btn"
								onClick={() => void onRotateKey()}
								disabled={keyBusy}
								title="Rotate API key"
								aria-label="Rotate API key"
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
							<button
								type="button"
								className="subscription-api-key-icon-btn"
								onClick={() => void onCopyKey()}
								disabled={!fullKey}
								title="Copy API key"
								aria-label="Copy API key"
							>
								<svg viewBox="0 0 24 24" aria-hidden="true">
									<rect
										x="9"
										y="9"
										width="11"
										height="11"
										rx="2"
										fill="none"
										stroke="currentColor"
										strokeWidth="1.75"
									/>
									<path
										d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"
										fill="none"
										stroke="currentColor"
										strokeWidth="1.75"
										strokeLinecap="round"
									/>
								</svg>
							</button>
						</div>
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
		</aside>
	);
}
