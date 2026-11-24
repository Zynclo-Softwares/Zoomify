import { ApiError, readApiErrorMessage } from "./apiErrors";
import { authHeaders } from "./auth";
import { showErrorToast } from "./toast";

type FetchOptions = RequestInit & { silent?: boolean };

async function fetchWithAuth(input: string, init?: FetchOptions) {
	const { silent, ...requestInit } = init ?? {};
	const headers = new Headers(requestInit.headers);
	const auth = await authHeaders();
	for (const [key, value] of Object.entries(auth)) {
		headers.set(key, value as string);
	}
	const res = await fetch(input, { ...requestInit, headers });
	if (!res.ok && !silent) {
		const message = await readApiErrorMessage(res.clone());
		showErrorToast(message);
		throw new ApiError(message, res.status);
	}
	return res;
}

export type Health = {
	ok: boolean;
	version?: string;
	clerk_enabled?: boolean;
	metering_enabled?: boolean;
	mongodb_enabled?: boolean;
	stripe_webhook_configured?: boolean;
};

export async function fetchHealth(): Promise<Health> {
	try {
		const res = await fetch("/api/health");
		if (!res.ok) return { ok: false };
		const data = await res.json();
		return { ...data, ok: Boolean(data.ok) };
	} catch {
		return { ok: false };
	}
}

export type McpTool = { name: string; metered: boolean; summary: string };

export type Skill = {
	name: string;
	title: string;
	description: string;
	uri: string;
	body?: string;
};

export type McpInfo = {
	name: string;
	version: string;
	transport: string;
	url: string;
	upload_url: string;
	auth: { type: string; header: string; format: string; required: boolean };
	tools: McpTool[];
	skills: Skill[];
};

export async function fetchMcpInfo(): Promise<McpInfo> {
	const res = await fetch("/api/mcp/info");
	if (!res.ok) {
		throw new ApiError(await readApiErrorMessage(res), res.status);
	}
	return res.json();
}

export async function fetchSkills(): Promise<Skill[]> {
	const res = await fetch("/api/skills");
	if (!res.ok) {
		throw new ApiError(await readApiErrorMessage(res), res.status);
	}
	return (await res.json()).skills;
}

export type UploadedImage = {
	image_id: string;
	filename: string;
	kind: "image" | "pdf";
	pages: number;
	bytes: number;
	expires_in_seconds: number;
	expires_at: string;
};

export async function uploadImage(file: File): Promise<UploadedImage> {
	const form = new FormData();
	form.append("file", file);
	const res = await fetchWithAuth("/api/images", {
		method: "POST",
		body: form,
	});
	return res.json();
}

export type BillingPlan = {
	id: string;
	name: string;
	price_monthly_usd: number | null;
	price_yearly_usd: number | null;
	yearly_discount_percent: number | null;
	monthly_limit: number;
	rate_limit_per_minute: number;
	max_image_mb: number;
	max_open_images: number;
	description: string;
	highlights: string[];
	checkout: { monthly: string | null; yearly: string | null } | null;
};

export type BillingPlansResponse = {
	plans: BillingPlan[];
	yearly_discount_percent: number;
	money_back_days: number;
	metered_tools: string[];
	custom_skills: {
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
	period: string;
	monthly_limit: number;
	monthly_used: number;
	monthly_remaining: number;
	resets_at: string;
	rate_limit_per_minute: number;
	max_image_mb: number;
	max_open_images: number;
	current_period_end: string | null;
};

export type PlatformKeyStatus = {
	has_key: boolean;
	prefix: string | null;
	created_at: string | null;
};

export type PlatformKeyCreated = {
	key: string;
	prefix: string;
	created_at: string;
};

export async function fetchBillingPlans(): Promise<BillingPlansResponse> {
	const res = await fetch("/api/billing/plans");
	if (!res.ok) {
		const message = await readApiErrorMessage(res);
		showErrorToast(message);
		throw new ApiError(message, res.status);
	}
	return res.json();
}

export async function fetchBillingStatus(): Promise<BillingStatus> {
	const res = await fetchWithAuth("/api/billing/status");
	return res.json();
}

export async function fetchPlatformKeyStatus(): Promise<PlatformKeyStatus> {
	const res = await fetchWithAuth("/api/platform-key");
	return res.json();
}

export async function createPlatformKey(): Promise<PlatformKeyCreated> {
	const res = await fetchWithAuth("/api/platform-key", { method: "POST" });
	return res.json();
}

export async function rotatePlatformKey(): Promise<PlatformKeyCreated> {
	const res = await fetchWithAuth("/api/platform-key/rotate", {
		method: "POST",
	});
	return res.json();
}

export type SchemaInquiryPayload = {
	name: string;
	email: string;
	message: string;
};

export type SchemaInquiryResponse = {
	issue_number: number;
	issue_url: string;
	title: string;
};

export async function submitSchemaInquiry(
	payload: SchemaInquiryPayload,
): Promise<SchemaInquiryResponse> {
	const res = await fetch("/api/schema-inquiry", {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(payload),
	});
	if (!res.ok) {
		const message = await readApiErrorMessage(res);
		showErrorToast(message);
		throw new ApiError(message, res.status);
	}
	return res.json();
}
