export class ApiError extends Error {
	status: number;

	constructor(message: string, status: number) {
		super(message);
		this.name = "ApiError";
		this.status = status;
	}
}

function validationDetail(detail: unknown): string | null {
	if (!Array.isArray(detail)) return null;
	const parts = detail
		.map((item) => {
			if (typeof item === "object" && item && "msg" in item) {
				return String((item as { msg: string }).msg);
			}
			return null;
		})
		.filter(Boolean);
	return parts.length ? parts.join(" ") : null;
}

export function friendlyApiMessage(status: number, detail?: unknown): string {
	if (typeof detail === "string" && detail.trim()) {
		return detail;
	}

	const validation = validationDetail(detail);
	if (validation) return validation;

	switch (status) {
		case 400:
			return "That request was not valid. Check your input and try again.";
		case 401:
			return "Please sign in to continue.";
		case 403:
			return "You do not have permission to do that.";
		case 404:
			return "We could not find what you asked for.";
		case 429:
			return "You have hit a usage limit. Try again later or upgrade your plan.";
		case 500:
			return "Something went wrong on our side. Please try again.";
		case 503:
			return "The service is temporarily unavailable. Please try again soon.";
		default:
			return `Request failed (${status}). Please try again.`;
	}
}

export async function readApiErrorMessage(res: Response): Promise<string> {
	try {
		const body = await res.json();
		return friendlyApiMessage(res.status, body.detail ?? body.message);
	} catch {
		return friendlyApiMessage(res.status);
	}
}
