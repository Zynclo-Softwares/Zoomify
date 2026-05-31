import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchHealth, fetchOpenRouterHealth } from "../api";

type Props = {
	hasKey: boolean;
};

type CheckState = boolean | null;

function statusColor(
	serverOk: CheckState,
	openrouterOk: CheckState,
	hasKey: boolean,
): "ok" | "warn" | "error" {
	if (serverOk === null || (hasKey && openrouterOk === null)) return "warn";
	if (!hasKey) return serverOk ? "warn" : "error";
	if (serverOk && openrouterOk) return "ok";
	if (!serverOk && !openrouterOk) return "error";
	return "warn";
}

function serverLabel(ok: CheckState): string {
	if (ok === null) return "Checking…";
	return ok ? "Healthy" : "Unreachable";
}

function openrouterLabel(
	ok: CheckState,
	hasKey: boolean,
	detail: string,
): string {
	if (!hasKey) return "Key not configured";
	if (ok === null) return "Checking…";
	if (ok) return "Connected";
	return detail || "Check failed";
}

export default function StatusIndicator({ hasKey }: Props) {
	const [serverOk, setServerOk] = useState<CheckState>(null);
	const [openrouterOk, setOpenrouterOk] = useState<CheckState>(null);
	const [openrouterDetail, setOpenrouterDetail] = useState("");

	const refresh = useCallback(async () => {
		setServerOk(null);
		if (hasKey) setOpenrouterOk(null);

		const health = await fetchHealth();
		setServerOk(health.ok);

		if (!hasKey) {
			setOpenrouterOk(null);
			setOpenrouterDetail("");
			return;
		}

		const openrouter = await fetchOpenRouterHealth();
		setOpenrouterOk(openrouter.ok);
		setOpenrouterDetail(openrouter.detail ?? "");
	}, [hasKey]);

	useEffect(() => {
		void refresh();
		const timer = window.setInterval(() => void refresh(), 60_000);
		return () => window.clearInterval(timer);
	}, [refresh]);

	const color = statusColor(serverOk, openrouterOk, hasKey);
	const tooltipLines = useMemo(
		() => [
			`Zoomify server: ${serverLabel(serverOk)}`,
			`OpenRouter: ${openrouterLabel(openrouterOk, hasKey, openrouterDetail)}`,
		],
		[serverOk, openrouterOk, hasKey, openrouterDetail],
	);
	const statusLabel = tooltipLines.join(". ");

	return (
		<div className="status-indicator">
			<span
				className={`status-dot ${color}`}
				role="img"
				aria-label={`Service status: ${statusLabel}`}
			/>
			<div className="status-tooltip" role="tooltip">
				{tooltipLines.map((line) => (
					<p key={line}>{line}</p>
				))}
			</div>
		</div>
	);
}
