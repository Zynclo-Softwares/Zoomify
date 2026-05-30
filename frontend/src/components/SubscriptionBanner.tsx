import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { type BillingStatus, fetchBillingStatus } from "../api";
import "./SubscriptionBanner.css";

export default function SubscriptionBanner() {
	const [status, setStatus] = useState<BillingStatus | null>(null);

	useEffect(() => {
		fetchBillingStatus()
			.then(setStatus)
			.catch(() => setStatus(null));
	}, []);

	if (!status) return null;

	const isFree = status.plan === "free";
	const usageLabel = status.unlimited
		? `${status.daily_used} extractions today`
		: `${status.daily_used} / ${status.daily_limit} used today`;

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
			<Link to="/pricing#plans" className="subscription-upgrade">
				{isFree ? "Upgrade plan" : "Change plan"}
			</Link>
		</aside>
	);
}
