import { ClerkProvider } from "@clerk/react";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { isClerkConfigured } from "./auth";
import { clerkAppearance } from "./clerkTheme";
import "./App.css";
import ToastHost from "./components/ToastHost";
import LandingPage from "./pages/LandingPage";
import PricingPage from "./pages/PricingPage";
import ProductPage from "./pages/ProductPage";
import SignInPage from "./pages/SignInPage";
import SignUpPage from "./pages/SignUpPage";

const clerkEnabled = isClerkConfigured();
const clerkPublishableKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY ?? "";

const routes = (
	<BrowserRouter>
		<ToastHost />
		<Routes>
			<Route path="/" element={<LandingPage />} />
			<Route path="/pricing" element={<PricingPage />} />
			<Route path="/product" element={<ProductPage />} />
			<Route
				path="/sign-in/*"
				element={
					clerkEnabled ? <SignInPage /> : <Navigate to="/product" replace />
				}
			/>
			<Route
				path="/sign-up/*"
				element={
					clerkEnabled ? <SignUpPage /> : <Navigate to="/product" replace />
				}
			/>
			<Route path="*" element={<Navigate to="/" replace />} />
		</Routes>
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
