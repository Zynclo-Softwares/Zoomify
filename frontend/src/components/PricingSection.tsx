import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { type BillingPlansResponse, fetchBillingPlans } from "../api";
import { openSchemaContact } from "../schemaContact";
import "./PricingSection.css";
import "./SchemaContactModal.css";

type BillingCycle = "monthly" | "yearly";

function checkoutUrl(
	base: string | null | undefined,
	userId?: string | null,
): string | null {
	if (!base) return null;
	if (!userId) return base;
	const url = new URL(base);
	url.searchParams.set("client_reference_id", userId);
	return url.toString();
}

type PricingSectionProps = {
	userId?: string | null;
	compact?: boolean;
};

export default function PricingSection({
	userId,
	compact,
}: PricingSectionProps) {
	const [plansData, setPlansData] = useState<BillingPlansResponse | null>(null);
	const [cycle, setCycle] = useState<BillingCycle>("monthly");
	const [error, setError] = useState("");

	useEffect(() => {
		fetchBillingPlans()
			.then(setPlansData)
			.catch((err) =>
				setError(err instanceof Error ? err.message : "Could not load plans"),
			);
	}, []);

	if (error) {
		return <p className="pricing-error">{error}</p>;
	}

	if (!plansData) {
		return <p className="pricing-loading">Loading plans…</p>;
	}

	const premium = plansData.custom_skills;

	return (
		<section className="pricing-section" id="plans">
			<div className="pricing-intro">
				<p className="pricing-kicker">Pricing</p>
				<h2>Free to start. Pay only when your agents get busy.</h2>
				<p className="pricing-lead">
					A request is one <code>open_image</code> or <code>zoom</code> tool
					call. Undo, redo, restore, uploads, and skills are always free.
					Reading one drawing typically takes 5 to 15 requests.
				</p>
				<div className="pricing-badges">
					<span className="pricing-badge">
						{plansData.yearly_discount_percent}% off yearly
					</span>
					<span className="pricing-badge">
						{plansData.money_back_days}-day money-back guarantee
					</span>
				</div>
				{!compact && (
					<fieldset className="billing-toggle">
						<legend className="billing-toggle-legend">Billing cycle</legend>
						<button
							type="button"
							className={cycle === "monthly" ? "active" : ""}
							onClick={() => setCycle("monthly")}
						>
							Monthly
						</button>
						<button
							type="button"
							className={cycle === "yearly" ? "active" : ""}
							onClick={() => setCycle("yearly")}
						>
							Yearly
						</button>
					</fieldset>
				)}
			</div>

			<div className="pricing-grid">
				{plansData.plans.map((plan) => {
					const isPro = plan.id === "pro";
					const isFree = plan.id === "free";
					const price =
						cycle === "yearly" && plan.price_yearly_usd != null
							? plan.price_yearly_usd
							: plan.price_monthly_usd;
					const period =
						cycle === "yearly" && !isFree ? "/year" : isFree ? "" : "/mo";
					const checkout =
						cycle === "yearly" ? plan.checkout?.yearly : plan.checkout?.monthly;
					const checkoutHref = checkoutUrl(checkout, userId);

					return (
						<article
							key={plan.id}
							className={`pricing-card${isPro ? " featured" : ""}`}
						>
							{isPro && <span className="pricing-popular">Most popular</span>}
							<h3>{plan.name}</h3>
							<p className="pricing-desc">{plan.description}</p>
							<div className="pricing-price">
								{isFree ? (
									<span className="amount">Free</span>
								) : (
									<>
										<span className="amount">${price}</span>
										<span className="period">{period}</span>
									</>
								)}
							</div>
							<p className="pricing-limit">
								{plan.monthly_limit.toLocaleString("en-US")} requests / month
							</p>
							<ul className="pricing-highlights">
								{plan.highlights.map((h) => (
									<li key={h}>{h}</li>
								))}
							</ul>
							{isFree ? (
								<Link to="/sign-up" className="pricing-cta ghost">
									Get started
								</Link>
							) : checkoutHref ? (
								<a
									href={checkoutHref}
									className="pricing-cta"
									target="_blank"
									rel="noopener noreferrer"
								>
									Subscribe
								</a>
							) : (
								<span className="pricing-cta disabled">
									Checkout coming soon
								</span>
							)}
						</article>
					);
				})}

				<article className="pricing-card premium">
					<span className="pricing-popular premium-tag">Zynclo service</span>
					<h3>{premium.name}</h3>
					<p className="pricing-desc">{premium.description}</p>
					<div className="pricing-price">
						<span className="amount custom">Custom</span>
					</div>
					<p className="pricing-limit">
						For teams with their own document standards
					</p>
					<ul className="pricing-highlights">
						{premium.highlights.map((h) => (
							<li key={h}>{h}</li>
						))}
					</ul>
					<button
						type="button"
						className="schema-contact-trigger pricing-cta ghost"
						onClick={openSchemaContact}
					>
						Talk to us →
					</button>
				</article>
			</div>

			<p className="pricing-footnote">
				Allowances reset on the 1st of each month (UTC). When a limit is reached
				your agent gets a clear message — there are no overage charges. Zoomify
				is open source (MIT), so you can also{" "}
				<a
					href="https://github.com/Zynclo-Softwares/Zoomify#self-hosting"
					target="_blank"
					rel="noopener noreferrer"
				>
					host it yourself
				</a>
				.
			</p>
		</section>
	);
}
