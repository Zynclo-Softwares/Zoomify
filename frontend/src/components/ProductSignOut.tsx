import { SignOutButton } from "@clerk/react";
import { LogOut } from "lucide-react";
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
				<LogOut size={16} aria-hidden="true" />
			</button>
		</SignOutButton>
	);
}
