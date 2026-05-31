import { SignOutButton } from "@clerk/react";
import { isClerkConfigured } from "../auth";

export default function ProductSignOut() {
	if (!isClerkConfigured()) return null;

	return (
		<SignOutButton redirectUrl="/">
			<button
				type="button"
				className="header-sign-out-btn"
				aria-label="Sign out"
				title="Sign out"
			>
				<svg viewBox="0 0 24 24" aria-hidden="true">
					<path
						d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"
						fill="none"
						stroke="currentColor"
						strokeWidth="1.75"
						strokeLinecap="round"
						strokeLinejoin="round"
					/>
				</svg>
			</button>
		</SignOutButton>
	);
}
