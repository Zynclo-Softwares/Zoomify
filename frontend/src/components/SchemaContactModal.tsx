import { type FormEvent, useEffect, useState } from "react";
import { submitSchemaInquiry } from "../lib/api";
import { showErrorToast, showSuccessToast } from "../lib/toast";
import "./SchemaContactModal.css";

type SchemaContactModalProps = {
	open: boolean;
	onClose: () => void;
};

export default function SchemaContactModal({
	open,
	onClose,
}: SchemaContactModalProps) {
	const [name, setName] = useState("");
	const [email, setEmail] = useState("");
	const [message, setMessage] = useState("");
	const [busy, setBusy] = useState(false);

	useEffect(() => {
		if (!open) return;
		const onKey = (event: KeyboardEvent) => {
			if (event.key === "Escape" && !busy) onClose();
		};
		window.addEventListener("keydown", onKey);
		return () => window.removeEventListener("keydown", onKey);
	}, [open, busy, onClose]);

	useEffect(() => {
		if (open) return;
		setName("");
		setEmail("");
		setMessage("");
		setBusy(false);
	}, [open]);

	if (!open) return null;

	const onSubmit = async (event: FormEvent) => {
		event.preventDefault();
		if (busy) return;
		setBusy(true);
		try {
			await submitSchemaInquiry({ name, email, message });
			showSuccessToast("Thanks — we received your inquiry and will follow up.");
			onClose();
		} catch (err) {
			showErrorToast(
				err instanceof Error ? err.message : "Could not send your inquiry.",
			);
		} finally {
			setBusy(false);
		}
	};

	return (
		<div className="schema-modal-backdrop" role="presentation">
			<button
				type="button"
				className="schema-modal-backdrop-btn"
				aria-label="Close dialog"
				onClick={busy ? undefined : onClose}
				disabled={busy}
			/>
			<div
				className="schema-modal card"
				role="dialog"
				aria-modal="true"
				aria-labelledby="schema-modal-title"
			>
				<button
					type="button"
					className="schema-modal-close"
					aria-label="Close"
					onClick={onClose}
					disabled={busy}
				>
					×
				</button>
				<p className="schema-modal-kicker">Custom skills &amp; enterprise</p>
				<h2 id="schema-modal-title">Tell us about your documents</h2>
				<p className="schema-modal-lead">
					Zynclo writes agent skills tuned to your drawings, forms, and house
					conventions, and can arrange higher limits or a private deployment.
					Share a few details and we&apos;ll open a tracking ticket for our
					team.
				</p>
				<form className="schema-modal-form" onSubmit={onSubmit}>
					<label>
						Name
						<input
							type="text"
							name="name"
							autoComplete="name"
							required
							maxLength={120}
							value={name}
							onChange={(e) => setName(e.target.value)}
							disabled={busy}
						/>
					</label>
					<label>
						Email
						<input
							type="email"
							name="email"
							autoComplete="email"
							required
							maxLength={254}
							value={email}
							onChange={(e) => setEmail(e.target.value)}
							disabled={busy}
						/>
					</label>
					<label>
						What do you need?
						<textarea
							name="message"
							required
							rows={4}
							maxLength={8000}
							placeholder="Describe your document types, agents, and expected volume…"
							value={message}
							onChange={(e) => setMessage(e.target.value)}
							disabled={busy}
						/>
					</label>
					<div className="schema-modal-actions">
						<button
							type="button"
							className="btn ghost"
							onClick={onClose}
							disabled={busy}
						>
							Cancel
						</button>
						<button type="submit" className="btn primary" disabled={busy}>
							{busy ? "Sending…" : "Send inquiry"}
						</button>
					</div>
				</form>
			</div>
		</div>
	);
}
