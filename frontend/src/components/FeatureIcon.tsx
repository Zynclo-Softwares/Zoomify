type IconName = "vision" | "grid" | "tree" | "json" | "undo" | "schema";

type Props = {
	name: IconName;
};

export default function FeatureIcon({ name }: Props) {
	return (
		<span className="feature-icon" aria-hidden="true">
			<svg
				viewBox="0 0 24 24"
				fill="none"
				stroke="currentColor"
				strokeWidth="1.6"
				aria-hidden="true"
			>
				<title>{name}</title>
				{name === "vision" && (
					<>
						<path
							d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z"
							strokeLinecap="round"
							strokeLinejoin="round"
						/>
						<circle cx="12" cy="12" r="2.5" />
					</>
				)}
				{name === "grid" && (
					<>
						<rect x="4" y="4" width="6" height="6" rx="1" />
						<rect x="14" y="4" width="6" height="6" rx="1" />
						<rect x="4" y="14" width="6" height="6" rx="1" />
						<rect x="14" y="14" width="6" height="6" rx="1" />
						<circle cx="17" cy="17" r="2.5" />
						<path d="M19 19l2 2" strokeLinecap="round" />
					</>
				)}
				{name === "tree" && (
					<>
						<circle cx="12" cy="5" r="1.5" fill="currentColor" stroke="none" />
						<path d="M12 6.5v3" strokeLinecap="round" />
						<circle cx="8" cy="12" r="1.5" fill="currentColor" stroke="none" />
						<circle cx="16" cy="12" r="1.5" fill="currentColor" stroke="none" />
						<path d="M12 9.5L8 10.5M12 9.5l4 1" strokeLinecap="round" />
						<path d="M8 13.5v3M16 13.5v3" strokeLinecap="round" />
						<circle cx="8" cy="18" r="1.5" fill="currentColor" stroke="none" />
						<circle cx="16" cy="18" r="1.5" fill="currentColor" stroke="none" />
					</>
				)}
				{name === "json" && (
					<>
						<path
							d="M8 4H7a2.5 2.5 0 0 0-2.5 2.5v2a2 2 0 0 1-2 2 2 2 0 0 1 2 2v2A2.5 2.5 0 0 0 7 20h1"
							strokeLinecap="round"
							strokeLinejoin="round"
						/>
						<path
							d="M16 4h1a2.5 2.5 0 0 1 2.5 2.5v2a2 2 0 0 0 2 2 2 2 0 0 0-2 2v2a2.5 2.5 0 0 1-2.5 2.5h-1"
							strokeLinecap="round"
							strokeLinejoin="round"
						/>
					</>
				)}
				{name === "undo" && (
					<>
						<path d="M5 8h8" strokeLinecap="round" />
						<path d="M5 8l3-2.5" strokeLinecap="round" strokeLinejoin="round" />
						<path d="M5 8l3 2.5" strokeLinecap="round" strokeLinejoin="round" />
						<path d="M19 16h-8" strokeLinecap="round" />
						<path
							d="M19 16l-3-2.5"
							strokeLinecap="round"
							strokeLinejoin="round"
						/>
						<path
							d="M19 16l-3 2.5"
							strokeLinecap="round"
							strokeLinejoin="round"
						/>
					</>
				)}
				{name === "schema" && (
					<>
						<rect x="6" y="4" width="12" height="16" rx="1.5" />
						<path d="M9 8h6M9 12h6M9 16h4" strokeLinecap="round" />
					</>
				)}
			</svg>
		</span>
	);
}

export type { IconName };
