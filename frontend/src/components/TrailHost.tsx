import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import FeatureIcon from "./FeatureIcon";

type Preview = { src: string; cap: string };

type Props = {
	html: string;
};

function hasTrailCrumbs(html: string): boolean {
	return html.includes('class="crumb');
}

function emptyTrailMessage(html: string): string {
	if (html.includes("Upload an image")) {
		return "Upload an image to start the zoom trail.";
	}
	return "Breadcrumb trail appears as the agent zooms.";
}

function TrailEmptyState({ message }: { message: string }) {
	return (
		<div className="trail-empty">
			<div className="trail-empty-icon" aria-hidden="true">
				<FeatureIcon name="tree" />
			</div>
			<p className="trail-empty-title">Live zoom trail</p>
			<p className="trail-empty-text">{message}</p>
		</div>
	);
}

export default function TrailHost({ html }: Props) {
	const hostRef = useRef<HTMLDivElement>(null);
	const [preview, setPreview] = useState<Preview | null>(null);
	const showCrumbs = hasTrailCrumbs(html);

	useEffect(() => {
		if (!showCrumbs) return;
		const host = hostRef.current;
		if (!host) return;
		host.innerHTML = html;

		const scrollHost = host.closest(".trail-host");
		if (scrollHost) scrollHost.scrollTop = scrollHost.scrollHeight;

		const onClick = (e: MouseEvent) => {
			const el = (e.target as HTMLElement).closest(
				".thumb",
			) as HTMLImageElement | null;
			if (!el?.dataset.full) return;
			e.preventDefault();
			setPreview({ src: el.dataset.full, cap: el.dataset.cap || "" });
		};

		host.addEventListener("click", onClick);
		return () => host.removeEventListener("click", onClick);
	}, [html, showCrumbs]);

	useEffect(() => {
		if (!preview) return;
		const onKeyDown = (e: KeyboardEvent) => {
			if (e.key === "Escape") setPreview(null);
		};
		document.addEventListener("keydown", onKeyDown);
		return () => document.removeEventListener("keydown", onKeyDown);
	}, [preview]);

	return (
		<>
			<div className={`trail-host${showCrumbs ? "" : " trail-host--empty"}`}>
				{showCrumbs ? (
					<div ref={hostRef} className="trail-host-inner" />
				) : (
					<TrailEmptyState message={emptyTrailMessage(html)} />
				)}
			</div>
			{preview &&
				createPortal(
					<div
						className="zmodal"
						role="dialog"
						aria-modal="true"
						aria-label="Zoom preview"
					>
						<button
							type="button"
							className="zbackdrop"
							aria-label="Close preview"
							onClick={() => setPreview(null)}
						/>
						<div className="zcontent">
							<button
								type="button"
								className="zclose"
								aria-label="Close preview"
								onClick={() => setPreview(null)}
							>
								×
							</button>
							<img src={preview.src} alt={preview.cap} />
							<div className="zcap">{preview.cap}</div>
						</div>
					</div>,
					document.body,
				)}
		</>
	);
}
