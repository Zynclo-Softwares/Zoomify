import { useUser } from "@clerk/react";
import { Link } from "react-router-dom";
import { isClerkConfigured } from "../auth";
import LandingNav from "../components/LandingNav";
import PricingSection from "../components/PricingSection";
import "../pages/LandingPage.css";

function PricingShell({ userId }: { userId?: string | null }) {
	return (
		<div className="landing">
			<div className="landing-glow landing-glow-a" aria-hidden />
			<div className="landing-glow landing-glow-b" aria-hidden />

			<LandingNav>
				<div className="landing-links-group">
					<Link to="/" className="landing-link">
						Home
					</Link>
					<a
						href="/api/docs"
						className="landing-link"
						target="_blank"
						rel="noopener noreferrer"
					>
						API docs
					</a>
				</div>
			</LandingNav>

			<main className="landing-pricing-main">
				<PricingSection userId={userId} />
			</main>

			<footer className="landing-footer">
				<span>
					Zoomify · Powered by{" "}
					<a
						href="https://zynclo.com"
						target="_blank"
						rel="noopener noreferrer"
					>
						zynclo.com
					</a>
				</span>
			</footer>
		</div>
	);
}

function PricingPageAuthed() {
	const { user } = useUser();
	return <PricingShell userId={user?.id} />;
}

export default function PricingPage() {
	if (isClerkConfigured()) {
		return <PricingPageAuthed />;
	}
	return <PricingShell />;
}
