export default function PageLoading({
	label = "Loading…",
}: {
	label?: string;
}) {
	return (
		<div className="page-loading" aria-busy="true" aria-live="polite">
			{label}
		</div>
	);
}
