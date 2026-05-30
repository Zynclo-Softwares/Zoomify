const STORAGE_KEY = "zoomify.selected_model";

export function getStoredModel(): string | null {
	try {
		const value = localStorage.getItem(STORAGE_KEY);
		const trimmed = value?.trim() ?? "";
		return trimmed || null;
	} catch {
		return null;
	}
}

export function setStoredModel(model: string): void {
	const trimmed = model.trim();
	if (!trimmed) {
		localStorage.removeItem(STORAGE_KEY);
		return;
	}
	localStorage.setItem(STORAGE_KEY, trimmed);
}

export function resolveModelPreference(fallback: string): string {
	return getStoredModel() ?? fallback;
}
