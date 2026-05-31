import type { ReactNode } from "react";
import { useEffect } from "react";
import { SAMPLE_IMAGE_FILENAME, SAMPLE_IMAGE_URL } from "../sampleImage";
import { openSchemaContact } from "../schemaContact";
import SubscriptionBanner from "./SubscriptionBanner";
import "./SchemaContactModal.css";
import ZoomifyLogo from "./ZoomifyLogo";

type ProductSettingsDrawerProps = {
	open: boolean;
	onClose: () => void;
	busy: boolean;
	onSelectSampleImage: () => void | Promise<void>;
	schemaCtaVisible: boolean;
	schemaCtaLeaving: boolean;
	onDismissSchemaCta: () => void;
};

function DrawerSection({
	title,
	children,
}: {
	title: string;
	children: ReactNode;
}) {
	return (
		<section className="settings-drawer-section">
			<h3>{title}</h3>
			{children}
		</section>
	);
}

export default function ProductSettingsDrawer({
	open,
	onClose,
	busy,
	onSelectSampleImage,
	schemaCtaVisible,
	schemaCtaLeaving,
	onDismissSchemaCta,
}: ProductSettingsDrawerProps) {
	useEffect(() => {
		if (!open) return;
		const onKeyDown = (e: KeyboardEvent) => {
			if (e.key === "Escape") onClose();
		};
		window.addEventListener("keydown", onKeyDown);
		return () => window.removeEventListener("keydown", onKeyDown);
	}, [open, onClose]);

	useEffect(() => {
		document.body.style.overflow = open ? "hidden" : "";
		return () => {
			document.body.style.overflow = "";
		};
	}, [open]);

	if (!open) return null;

	return (
		<div className="settings-drawer-root" role="presentation">
			<button
				type="button"
				className="settings-drawer-backdrop"
				aria-label="Close settings"
				onClick={onClose}
			/>
			<aside
				className="settings-drawer card"
				role="dialog"
				aria-modal="true"
				aria-label="Settings"
			>
				<header className="settings-drawer-head">
					<h2>Settings</h2>
					<button
						type="button"
						className="settings-drawer-close"
						aria-label="Close settings"
						onClick={onClose}
					>
						×
					</button>
				</header>

				<div className="settings-drawer-body">
					<DrawerSection title="Try a sample">
						<p className="settings-drawer-hint">
							Attach the demo image to explore Zoomify without uploading your
							own file.
						</p>
						<button
							type="button"
							className="sample-picker"
							onClick={() => {
								void onSelectSampleImage();
								onClose();
							}}
							disabled={busy}
							title="Use sample image"
							aria-label="Use sample image"
						>
							<span className="sample-picker-frame">
								<img src={SAMPLE_IMAGE_URL} alt="" />
							</span>
							<span className="sample-picker-caption">
								Click to attach · {SAMPLE_IMAGE_FILENAME}
							</span>
						</button>
					</DrawerSection>

					<DrawerSection title="Plan &amp; billing">
						<SubscriptionBanner />
					</DrawerSection>

					{schemaCtaVisible && (
						<aside
							className={`schema-cta card${schemaCtaLeaving ? " leaving" : ""}`}
						>
							<button
								type="button"
								className="schema-cta-close"
								aria-label="Dismiss"
								onClick={onDismissSchemaCta}
							>
								×
							</button>
							<ZoomifyLogo size={28} className="cta-icon" decorative />
							<div>
								<strong>Need a business schema?</strong>
								<p>
									Tell us your use case — Zynclo designs custom extraction
									schemas for your documents.{" "}
									<button
										type="button"
										className="schema-contact-trigger"
										onClick={openSchemaContact}
									>
										Request schema →
									</button>
								</p>
							</div>
						</aside>
					)}
				</div>
			</aside>
		</div>
	);
}
