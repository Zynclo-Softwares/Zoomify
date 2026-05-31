import { openSchemaContact } from "./schemaContact";
import { showInfoToast } from "./toast";

const STORAGE_KEY = "zoomify-schema-promo-last-shown";
const COOLDOWN_MS = 30 * 60 * 1000;

function readLastShownAt(): number | null {
	try {
		const raw = localStorage.getItem(STORAGE_KEY);
		if (!raw) return null;
		const parsed = Number.parseInt(raw, 10);
		return Number.isFinite(parsed) ? parsed : null;
	} catch {
		return null;
	}
}

function markShownNow(): void {
	try {
		localStorage.setItem(STORAGE_KEY, String(Date.now()));
	} catch {
		// Ignore storage failures (private mode, quota, etc.).
	}
}

function isPromoCooldownActive(now = Date.now()): boolean {
	const lastShownAt = readLastShownAt();
	if (lastShownAt === null) return false;
	return now - lastShownAt < COOLDOWN_MS;
}

/** Schema promo toast for the product workspace (respects 30-minute cooldown). */
export function showSchemaPromoOnLoad() {
	if (isPromoCooldownActive()) return;
	markShownNow();

	showInfoToast(
		"Need business schema extraction from your images? Zynclo designs custom schemas for invoices, forms, IDs, and domain-specific layouts.",
		{
			action: { label: "Contact now", onClick: openSchemaContact },
			duration: 12000,
		},
	);
}
