import { openSchemaContact } from "./schemaContact";
import { showInfoToast } from "./toast";

let queued = false;

/** Bluish promo toast on full page load — mirrors the premium schema pricing card. */
export function showSchemaPromoOnLoad() {
	if (queued) return;
	queued = true;

	showInfoToast(
		"Need business schema extraction from your images? Zynclo designs custom schemas for invoices, forms, IDs, and domain-specific layouts.",
		{
			action: { label: "Contact now", onClick: openSchemaContact },
			duration: 12000,
		},
	);
}
