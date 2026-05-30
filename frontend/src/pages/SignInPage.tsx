import { SignIn } from "@clerk/react";
import { clerkAppearance } from "../clerkTheme";
import AuthShell from "./AuthShell";

export default function SignInPage() {
	return (
		<AuthShell>
			<SignIn
				routing="path"
				path="/sign-in"
				signUpUrl="/sign-up"
				forceRedirectUrl="/product"
				appearance={clerkAppearance}
			/>
		</AuthShell>
	);
}
