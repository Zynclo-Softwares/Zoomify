import { SignOutButton } from "@clerk/react";
import { isClerkConfigured } from "../auth";

export default function ProductSignOut() {
	if (!isClerkConfigured()) return null;

	return (
		<SignOutButton>
			<button type="button" className="btn danger sign-out-btn">
				Sign out
			</button>
		</SignOutButton>
	);
}
