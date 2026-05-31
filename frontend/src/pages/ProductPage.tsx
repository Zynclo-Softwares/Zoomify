import { useAuth } from "@clerk/react";
import { lazy, Suspense, useEffect } from "react";
import { Navigate } from "react-router-dom";
import { isClerkConfigured, setAuthTokenGetter } from "../auth";
import PageLoading from "../components/PageLoading";
import { showSchemaPromoOnLoad } from "../schemaPromoToast";

const App = lazy(() => import("../App"));

function AuthenticatedProduct() {
	const { isLoaded, isSignedIn, getToken } = useAuth();

	useEffect(() => {
		if (isSignedIn) {
			setAuthTokenGetter(() => getToken());
		}
	}, [getToken, isSignedIn]);

	if (!isLoaded) {
		return <PageLoading label="Checking session…" />;
	}

	if (!isSignedIn) {
		return <Navigate to="/sign-in" replace />;
	}

	return (
		<Suspense fallback={<PageLoading label="Loading Zoomify…" />}>
			<App />
		</Suspense>
	);
}

export default function ProductPage() {
	useEffect(() => {
		void showSchemaPromoOnLoad();
	}, []);

	if (!isClerkConfigured()) {
		return (
			<Suspense fallback={<PageLoading label="Loading Zoomify…" />}>
				<App />
			</Suspense>
		);
	}

	return <AuthenticatedProduct />;
}
