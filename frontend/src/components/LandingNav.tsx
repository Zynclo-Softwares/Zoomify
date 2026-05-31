import type { ReactNode } from "react";
import { useEffect, useId, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import ZoomifyLogo from "./ZoomifyLogo";

type LandingNavProps = {
	brandTo?: string;
	children: ReactNode;
};

export default function LandingNav({
	brandTo = "/",
	children,
}: LandingNavProps) {
	const [open, setOpen] = useState(false);
	const menuId = useId();
	const { pathname } = useLocation();

	// biome-ignore lint/correctness/useExhaustiveDependencies: close menu on route change
	useEffect(() => {
		setOpen(false);
	}, [pathname]);

	useEffect(() => {
		if (!open) return;
		const onKeyDown = (e: KeyboardEvent) => {
			if (e.key === "Escape") setOpen(false);
		};
		window.addEventListener("keydown", onKeyDown);
		return () => window.removeEventListener("keydown", onKeyDown);
	}, [open]);

	useEffect(() => {
		document.body.style.overflow = open ? "hidden" : "";
		return () => {
			document.body.style.overflow = "";
		};
	}, [open]);

	return (
		<header className="landing-nav">
			<div className="landing-brand-wrap">
				<Link to={brandTo} className="landing-brand">
					<ZoomifyLogo size={36} />
					<span>Zoomify</span>
				</Link>
				<p className="landing-brand-by">
					by{" "}
					<a
						href="https://zynclo.com"
						target="_blank"
						rel="noopener noreferrer"
					>
						zynclo
					</a>
				</p>
			</div>

			<button
				type="button"
				className="landing-nav-toggle"
				aria-label={open ? "Close menu" : "Open menu"}
				aria-expanded={open}
				aria-controls={menuId}
				onClick={() => setOpen((prev) => !prev)}
			>
				<svg viewBox="0 0 24 24" aria-hidden="true">
					{open ? (
						<path
							d="M6 6l12 12M18 6L6 18"
							fill="none"
							stroke="currentColor"
							strokeWidth="1.75"
							strokeLinecap="round"
						/>
					) : (
						<path
							d="M4 7h16M4 12h16M4 17h16"
							fill="none"
							stroke="currentColor"
							strokeWidth="1.75"
							strokeLinecap="round"
						/>
					)}
				</svg>
			</button>

			<nav className="landing-links" aria-label="Site">
				{children}
			</nav>

			{open && (
				<div className="landing-nav-mobile-root" role="presentation">
					<button
						type="button"
						className="landing-nav-backdrop"
						aria-label="Close menu"
						onClick={() => setOpen(false)}
					/>
					<nav
						id={menuId}
						className="landing-nav-mobile"
						aria-label="Site menu"
					>
						{children}
					</nav>
				</div>
			)}
		</header>
	);
}
