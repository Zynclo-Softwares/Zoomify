import { useEffect, useState } from "react";
import { dismissToast, subscribeToasts, type ToastItem } from "../toast";
import "./ToastHost.css";

export default function ToastHost() {
	const [items, setItems] = useState<ToastItem[]>([]);

	useEffect(() => subscribeToasts(setItems), []);

	if (items.length === 0) return null;

	return (
		<div className="toast-stack" aria-live="polite" aria-relevant="additions">
			{items.map((item) => (
				<output
					key={item.id}
					className={`toast toast-${item.variant}${item.leaving ? " toast-leaving" : ""}`}
				>
					<button
						type="button"
						className="toast-close"
						aria-label="Dismiss notification"
						onClick={() => dismissToast(item.id)}
					>
						×
					</button>
					<span className="toast-message">{item.message}</span>
					{item.action &&
						(item.action.onClick ? (
							<button
								type="button"
								className="toast-action"
								onClick={item.action.onClick}
							>
								{item.action.label}
							</button>
						) : (
							<a
								className="toast-action"
								href={item.action.href}
								target="_blank"
								rel="noopener noreferrer"
							>
								{item.action.label}
							</a>
						))}
				</output>
			))}
		</div>
	);
}
