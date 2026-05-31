import { showInfoToast } from "./toast";

const DEFAULT_CONTACT =
	"https://github.com/Zynclo-Softwares/Zoomify/issues/new";

let queued = false;

/** Bluish promo toast on full page load — mirrors the premium schema pricing card. */
export async function showSchemaPromoOnLoad() {
	if (queued) return;
	queued = true;

	let contact = DEFAULT_CONTACT;
	try {
		const res = await fetch("/api/billing/plans");
		if (res.ok) {
			const data = (await res.json()) as {
				premium_schema?: { contact?: string };
			};
			contact = data.premium_schema?.contact?.trim() || contact;
		}
	} catch {
		// use default contact link
	}

	showInfoToast(
		"Need business schema extraction from your images? Zynclo designs custom schemas for invoices, forms, IDs, and domain-specific layouts.",
		{
			action: { label: "Contact now", href: contact },
			duration: 12000,
		},
	);
}
