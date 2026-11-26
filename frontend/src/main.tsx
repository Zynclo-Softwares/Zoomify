import { ClerkProvider } from "@clerk/react";
import { lazy, StrictMode, Suspense } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import PageLoading from "./components/PageLoading";
import SchemaContactHost from "./components/SchemaContactHost";
import { isClerkConfigured } from "./lib/auth";
import { clerkAppearance } from "./lib/clerkTheme";
import "./global.css";
import ToastHost from "./components/ToastHost";
import LandingPage from "./pages/LandingPage";
import PricingPage from "./pages/PricingPage";

const ConnectPage = lazy(() => import("./pages/ConnectPage"));
const SignInPage = lazy(() => import("./pages/SignInPage"));
const SignUpPage = lazy(() => import("./pages/SignUpPage"));

const clerkEnabled = isClerkConfigured();
const clerkPublishableKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY ?? "";

const routes = (
	<BrowserRouter>
		<ToastHost />
		<SchemaContactHost />
		<Suspense fallback={<PageLoading />}>
			<Routes>
				<Route path="/" element={<LandingPage />} />
				<Route path="/pricing" element={<PricingPage />} />
				<Route path="/connect" element={<ConnectPage />} />
				<Route path="/product" element={<Navigate to="/connect" replace />} />
				<Route
					path="/sign-in/*"
					element={
						clerkEnabled ? <SignInPage /> : <Navigate to="/connect" replace />
					}
				/>
				<Route
					path="/sign-up/*"
					element={
						clerkEnabled ? <SignUpPage /> : <Navigate to="/connect" replace />
					}
				/>
				<Route path="*" element={<Navigate to="/" replace />} />
			</Routes>
		</Suspense>
	</BrowserRouter>
);

const rootEl = document.getElementById("root");
if (rootEl) {
	createRoot(rootEl).render(
		<StrictMode>
			{clerkEnabled ? (
				<ClerkProvider
					publishableKey={clerkPublishableKey}
					afterSignOutUrl="/"
					appearance={clerkAppearance}
				>
					{routes}
				</ClerkProvider>
			) : (
				routes
			)}
		</StrictMode>,
	);
}
