import { SignUp } from "@clerk/react";
import { clerkAppearance } from "../clerkTheme";
import AuthShell from "./AuthShell";

export default function SignUpPage() {
	return (
		<AuthShell>
			<SignUp
				routing="path"
				path="/sign-up"
				signInUrl="/sign-in"
				forceRedirectUrl="/product"
				appearance={clerkAppearance}
			/>
		</AuthShell>
	);
}
