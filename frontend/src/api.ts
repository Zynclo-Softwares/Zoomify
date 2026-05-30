import { ApiError, readApiErrorMessage } from "./apiErrors";
import { authHeaders } from "./auth";
import { byokHeaders } from "./byok";
import { showToast } from "./toast";

export class ApiKeyInvalidError extends Error {
	constructor() {
		super(
			"Your saved key no longer works. Please enter your OpenRouter key again.",
		);
		this.name = "ApiKeyInvalidError";
	}
}

export type ChatMessage = {
	id: string;
	role: "user" | "assistant";
	content: string;
};

export type StreamEvent =
	| { type: "session"; session_id: string }
	| { type: "user"; content: string }
	| { type: "trail"; html: string }
	| { type: "assistant"; content: string }
	| {
			type: "schema";
			structured: boolean;
			schema_id: string | null;
			source: string;
	  }
	| { type: "error"; message: string }
	| { type: "done" };

type FetchOptions = RequestInit & { silent?: boolean };

async function fetchWithAuth(input: string, init?: FetchOptions) {
	const { silent, ...requestInit } = init ?? {};
	const headers = new Headers(requestInit.headers);
	const auth = await authHeaders();
	for (const [key, value] of Object.entries(auth)) {
		headers.set(key, value as string);
	}
	for (const [key, value] of Object.entries(byokHeaders())) {
		headers.set(key, value as string);
	}
	const res = await fetch(input, { ...requestInit, headers });
	if (!res.ok && !silent) {
		const message = await readApiErrorMessage(res.clone());
		showToast(message);
		throw new ApiError(message, res.status);
	}
	return res;
}

export async function fetchModels(): Promise<{
	choices: string[];
	default: string;
}> {
	try {
		const res = await fetchWithAuth("/api/models");
		return res.json();
	} catch (err) {
		if (err instanceof ApiError && err.status === 400) {
			throw new ApiKeyInvalidError();
		}
		throw err;
	}
}

export async function fetchHealth(): Promise<{
	ok: boolean;
	byok_ready?: boolean;
	clerk_enabled?: boolean;
	mongodb_enabled?: boolean;
	stripe_webhook_configured?: boolean;
}> {
	const res = await fetch("/api/health");
	return res.json();
}

export type BillingPlan = {
	id: string;
	name: string;
	price_monthly_usd: number | null;
	price_yearly_usd: number | null;
	yearly_discount_percent: number | null;
	daily_limit: number | null;
	description: string;
	highlights: string[];
	unlimited: boolean;
	checkout: { monthly: string | null; yearly: string | null } | null;
};

export type BillingPlansResponse = {
	plans: BillingPlan[];
	yearly_discount_percent: number;
	money_back_days: number;
	metered_endpoint: string;
	premium_schema: {
		name: string;
		description: string;
		highlights: string[];
		contact: string;
	};
};

export type BillingStatus = {
	plan: string;
	plan_name: string;
	subscription_status: string;
	daily_limit: number | null;
	daily_used: number;
	daily_remaining: number | null;
	unlimited: boolean;
	current_period_end: string | null;
};

export async function fetchBillingPlans(): Promise<BillingPlansResponse> {
	const res = await fetch("/api/billing/plans");
	if (!res.ok) {
		const message = await readApiErrorMessage(res);
		showToast(message);
		throw new ApiError(message, res.status);
	}
	return res.json();
}

export async function fetchBillingStatus(): Promise<BillingStatus> {
	const res = await fetchWithAuth("/api/billing/status");
	return res.json();
}

export async function deleteSession(sessionId: string): Promise<void> {
	await fetchWithAuth(`/api/session/${sessionId}`, {
		method: "DELETE",
		silent: true,
	});
}

export async function* streamQuery(params: {
	query: string;
	image?: File | null;
	model: string;
	sessionId?: string | null;
}): AsyncGenerator<StreamEvent> {
	const form = new FormData();
	form.append("query", params.query);
	form.append("model", params.model);
	if (params.sessionId) form.append("session_id", params.sessionId);
	if (params.image) form.append("image", params.image);

	let res: Response;
	try {
		res = await fetchWithAuth("/api/query", { method: "POST", body: form });
	} catch (err) {
		if (err instanceof ApiError) throw err;
		throw err;
	}

	if (!res.body) {
		const message = "The extraction stream could not be started.";
		showToast(message);
		throw new ApiError(message, res.status);
	}

	const reader = res.body.getReader();
	const decoder = new TextDecoder();
	let buffer = "";

	while (true) {
		const { done, value } = await reader.read();
		if (done) break;
		buffer += decoder.decode(value, { stream: true });
		const lines = buffer.split("\n");
		buffer = lines.pop() ?? "";
		for (const line of lines) {
			if (!line.trim()) continue;
			yield JSON.parse(line) as StreamEvent;
		}
	}
	if (buffer.trim()) {
		yield JSON.parse(buffer) as StreamEvent;
	}
}
