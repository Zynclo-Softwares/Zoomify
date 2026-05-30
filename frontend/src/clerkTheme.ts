import { dark } from "@clerk/themes";

export const clerkAppearance = {
	theme: dark,
	variables: {
		colorBackground: "rgba(17, 24, 39, 0.72)",
		colorNeutral: "white",
		colorPrimary: "#0055ff",
		colorPrimaryForeground: "#ffffff",
		colorForeground: "#f1f5f9",
		colorMutedForeground: "#94a3b8",
		colorInput: "rgba(15, 23, 42, 0.92)",
		colorInputForeground: "#f1f5f9",
		colorBorder: "rgba(148, 163, 184, 0.18)",
		colorDanger: "#f87171",
		borderRadius: "12px",
		fontFamily: '"DM Sans", ui-sans-serif, system-ui, sans-serif',
		fontSize: "0.9375rem",
	},
	options: {
		logoPlacement: "none" as const,
		logoLinkUrl: "/",
		socialButtonsPlacement: "bottom" as const,
		unsafe_disableDevelopmentModeWarnings: true,
	},
	elements: {
		rootBox: {
			width: "100%",
		},
		cardBox: {
			width: "100%",
			boxShadow: "none",
		},
		card: {
			background: "rgba(17, 24, 39, 0.78)",
			border: "1px solid rgba(148, 163, 184, 0.14)",
			borderRadius: "16px",
			backdropFilter: "blur(18px)",
			boxShadow:
				"0 24px 48px rgba(0, 0, 0, 0.42), inset 0 1px 0 rgba(255, 255, 255, 0.05)",
			padding: "1.75rem 1.5rem",
		},
		header: {
			gap: "0.35rem",
		},
		headerTitle: {
			fontSize: "1.35rem",
			fontWeight: 700,
			letterSpacing: "-0.03em",
			color: "#f8fafc",
		},
		headerSubtitle: {
			color: "#94a3b8",
			fontSize: "0.9rem",
			lineHeight: 1.5,
		},
		formFieldLabel: {
			color: "#cbd5e1",
			fontWeight: 500,
			fontSize: "0.84rem",
		},
		formFieldInput: {
			backgroundColor: "rgba(15, 23, 42, 0.92)",
			border: "1px solid rgba(148, 163, 184, 0.2)",
			borderRadius: "10px",
			minHeight: "2.65rem",
			padding: "0.65rem 0.85rem",
			transition: "border-color 0.15s ease, box-shadow 0.15s ease",
			"&:focus": {
				borderColor: "rgba(59, 130, 246, 0.65)",
				boxShadow: "0 0 0 3px rgba(0, 85, 255, 0.14)",
			},
		},
		formFieldInputShowPasswordButton: {
			color: "#94a3b8",
		},
		formButtonPrimary: {
			background: "linear-gradient(135deg, #3b82f6 0%, #0055ff 100%)",
			border: "none",
			borderRadius: "10px",
			fontWeight: 600,
			fontSize: "0.95rem",
			minHeight: "2.65rem",
			boxShadow: "0 10px 28px rgba(0, 85, 255, 0.32)",
			transition: "transform 0.15s ease, box-shadow 0.15s ease",
			"&:hover": {
				background: "linear-gradient(135deg, #4f8ff7 0%, #1a66ff 100%)",
				boxShadow: "0 12px 32px rgba(0, 85, 255, 0.4)",
			},
		},
		footer: {
			background: "transparent",
		},
		footerAction: {
			justifyContent: "center",
		},
		footerActionText: {
			color: "#64748b",
		},
		footerActionLink: {
			color: "#60a5fa",
			fontWeight: 600,
		},
		dividerLine: {
			backgroundColor: "rgba(148, 163, 184, 0.16)",
		},
		dividerText: {
			color: "#64748b",
		},
		socialButtonsBlockButton: {
			backgroundColor: "rgba(15, 23, 42, 0.85)",
			border: "1px solid rgba(148, 163, 184, 0.18)",
			borderRadius: "10px",
			color: "#f1f5f9",
			"&:hover": {
				backgroundColor: "rgba(30, 41, 59, 0.95)",
				borderColor: "rgba(59, 130, 246, 0.35)",
			},
		},
	},
};
