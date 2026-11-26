const STORAGE_KEY = "zoomify.platform_api_key";

export function getStoredPlatformKey(): string | null {
	try {
		const value = localStorage.getItem(STORAGE_KEY)?.trim();
		return value || null;
	} catch {
		return null;
	}
}

export function setStoredPlatformKey(key: string): void {
	try {
		localStorage.setItem(STORAGE_KEY, key.trim());
	} catch {
		// ignore quota / private mode
	}
}

export function clearStoredPlatformKey(): void {
	try {
		localStorage.removeItem(STORAGE_KEY);
	} catch {
		// ignore
	}
}

export function maskedPlatformKey(prefix: string | null | undefined): string {
	if (!prefix) return "zfy_live_••••••••••••••••••••";
	return `${prefix}${"•".repeat(28)}`;
}
