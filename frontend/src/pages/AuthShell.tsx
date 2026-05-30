import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import ZoomifyLogo from "../components/ZoomifyLogo";
import "./LandingPage.css";

type Props = {
	children: ReactNode;
};

export default function AuthShell({ children }: Props) {
	return (
		<div className="auth-page">
			<div className="auth-glow auth-glow-a" aria-hidden="true" />
			<div className="auth-glow auth-glow-b" aria-hidden="true" />

			<div className="auth-shell">
				<header className="auth-top">
					<Link to="/" className="auth-brand">
						<ZoomifyLogo size={36} />
						<span>Zoomify</span>
					</Link>
					<Link to="/" className="auth-back">
						← Back to home
					</Link>
				</header>

				<div className="auth-card-wrap">{children}</div>

				<p className="auth-footnote">
					Powered by{" "}
					<a
						href="https://zynclo.com"
						target="_blank"
						rel="noopener noreferrer"
					>
						zynclo.com
					</a>
				</p>
			</div>
		</div>
	);
}
