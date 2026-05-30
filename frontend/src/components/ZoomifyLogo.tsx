type Props = {
	size?: number;
	className?: string;
	decorative?: boolean;
};

export default function ZoomifyLogo({
	size = 40,
	className = "",
	decorative = false,
}: Props) {
	return (
		<img
			src="/zoomify-logo.png"
			alt={decorative ? "" : "Zoomify"}
			width={size}
			height={size}
			className={`zoomify-logo ${className}`.trim()}
			draggable={false}
			aria-hidden={decorative || undefined}
		/>
	);
}
