let tokenGetter: (() => Promise<string | null>) | null = null;

export function isClerkConfigured(): boolean {
	return Boolean(import.meta.env.VITE_CLERK_PUBLISHABLE_KEY?.trim());
}

export function setAuthTokenGetter(fn: () => Promise<string | null>) {
	tokenGetter = fn;
}

export async function authHeaders(): Promise<HeadersInit> {
	if (!tokenGetter) return {};
	const token = await tokenGetter();
	return token ? { Authorization: `Bearer ${token}` } : {};
}
