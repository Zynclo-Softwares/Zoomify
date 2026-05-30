import { Link } from "react-router-dom";
import FeatureIcon, { type IconName } from "../components/FeatureIcon";
import ZoomifyLogo from "../components/ZoomifyLogo";
import "./LandingPage.css";

const FEATURES: { icon: IconName; title: string; desc: string }[] = [
	{
		icon: "vision",
		title: "Vision extraction",
		desc: "Upload maps, scans, or diagrams — AI reads what models miss at full-frame scale.",
	},
	{
		icon: "grid",
		title: "Smart zoom grid",
		desc: "Auto-grids images and zooms into tiny text, labels, and dense regions.",
	},
	{
		icon: "tree",
		title: "Live zoom tree",
		desc: "Follow every zoom step in a breadcrumb trail with thumbnail previews.",
	},
	{
		icon: "json",
		title: "Structured JSON",
		desc: "Metadata-tagged images auto-route to business schemas for typed output.",
	},
	{
		icon: "undo",
		title: "Undo & redo",
		desc: "Agent navigates, backtracks, and refines — just like a human inspector.",
	},
	{
		icon: "schema",
		title: "Custom schemas",
		desc: "Zynclo designs extraction schemas tailored to your documents.",
	},
];

export default function LandingPage() {
	return (
		<div className="landing">
			<div className="landing-glow landing-glow-a" aria-hidden />
			<div className="landing-glow landing-glow-b" aria-hidden />

			<header className="landing-nav">
				<div className="landing-brand">
					<ZoomifyLogo size={36} />
					<span>Zoomify</span>
				</div>
				<nav className="landing-links">
					<Link to="/pricing" className="landing-link">
						Pricing
					</Link>
					<a
						href="/api/docs"
						className="landing-link"
						target="_blank"
						rel="noopener noreferrer"
					>
						API
					</a>
					<Link to="/sign-in" className="landing-link">
						Sign in
					</Link>
					<Link to="/sign-up" className="landing-btn">
						Get started
					</Link>
				</nav>
			</header>

			<main className="landing-hero">
				<ZoomifyLogo size={88} className="landing-logo" decorative />
				<p className="landing-kicker">by Zynclo</p>
				<h1>Extract detail from any complex image</h1>
				<p className="landing-lead">
					Zoomify grids hard-to-read maps, diagrams, scans, and tiny text — then
					zooms with AI until every field is captured accurately.
				</p>
				<div className="landing-cta">
					<Link to="/sign-up" className="landing-btn landing-btn-lg">
						Start free
					</Link>
					<Link to="/product" className="landing-btn ghost landing-btn-lg">
						Open product
					</Link>
				</div>
				<div className="landing-features">
					{FEATURES.map((f) => (
						<article key={f.title} className="feature-card">
							<FeatureIcon name={f.icon} />
							<h3>{f.title}</h3>
							<p>{f.desc}</p>
						</article>
					))}
				</div>
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
