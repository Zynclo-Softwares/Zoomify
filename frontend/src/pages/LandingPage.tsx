import { Link } from "react-router-dom";
import FeatureIcon, { type IconName } from "../components/FeatureIcon";
import LandingNav from "../components/LandingNav";
import ZoomifyLogo from "../components/ZoomifyLogo";
import "./LandingPage.css";

const FEATURES: { icon: IconName; title: string; desc: string }[] = [
	{
		icon: "tree",
		title: "Works with any agent",
		desc: "A standard remote MCP server — Claude Code, Cursor, VS Code, Codex, Gemini CLI, and more.",
	},
	{
		icon: "grid",
		title: "Grid and zoom tools",
		desc: "Your agent names a cell, the server crops, upscales, and re-grids it until small print is sharp.",
	},
	{
		icon: "vision",
		title: "Drawings, scans, PDFs",
		desc: "Single-line diagrams, site plans, long screenshots, and PDF pages too big to read in one look.",
	},
	{
		icon: "schema",
		title: "Built-in skills",
		desc: "Playbooks served with the tools teach your agent how to read each kind of document.",
	},
	{
		icon: "undo",
		title: "Undo, redo, restore",
		desc: "Navigation is free, so agents can back out of a wrong zoom and try again.",
	},
	{
		icon: "json",
		title: "Free to start",
		desc: "1,000 requests a month at no cost. Open source, so you can also host it yourself.",
	},
];

export default function LandingPage() {
	return (
		<div className="landing">
			<div className="landing-glow landing-glow-a" aria-hidden />
			<div className="landing-glow landing-glow-b" aria-hidden />

			<LandingNav>
				<div className="landing-links-group">
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
					<a
						href="https://github.com/Zynclo-Softwares/Zoomify"
						className="landing-link"
						target="_blank"
						rel="noopener noreferrer"
					>
						GitHub
					</a>
				</div>
			</LandingNav>

			<main className="landing-hero">
				<ZoomifyLogo size={88} className="landing-logo" decorative />
				<p className="landing-kicker">by Zynclo</p>
				<h1>Give your AI agent a zoom lens</h1>
				<p className="landing-lead">
					Vision models skim large images and guess at the small print. Zoomify
					is a cloud MCP server that lets any agent grid, zoom, and re-read
					drawings, scans, and PDFs until every value is legible.
				</p>
				<div className="landing-cta">
					<Link to="/sign-up" className="landing-btn landing-btn-lg">
						Get a free API key
					</Link>
					<Link to="/connect" className="landing-btn ghost landing-btn-lg">
						Connect an agent
					</Link>
				</div>
				<pre className="landing-snippet">
					<code>
						{"claude mcp add --transport http zoomify "}
						{window.location.origin}
						{'/mcp \\\n  --header "Authorization: Bearer zfy_live_…"'}
					</code>
				</pre>
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
