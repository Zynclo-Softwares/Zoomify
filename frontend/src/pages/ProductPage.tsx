import { Show, useAuth } from "@clerk/react";
import { useEffect } from "react";
import { Navigate } from "react-router-dom";
import App from "../App";
import { isClerkConfigured, setAuthTokenGetter } from "../auth";

function AuthenticatedProduct() {
	const { getToken } = useAuth();

	useEffect(() => {
		setAuthTokenGetter(() => getToken());
	}, [getToken]);

	return (
		<>
			<Show when="signed-in">
				<App />
			</Show>
			<Show when="signed-out">
				<Navigate to="/sign-in" replace />
			</Show>
		</>
	);
}

export default function ProductPage() {
	if (!isClerkConfigured()) {
		return <App />;
	}

	return <AuthenticatedProduct />;
}
