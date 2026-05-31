import { useEffect, useState } from "react";
import { showSchemaPromoOnLoad } from "../schemaPromoToast";
import { subscribeToasts, type ToastItem } from "../toast";
import "./ToastHost.css";

export default function ToastHost() {
	const [items, setItems] = useState<ToastItem[]>([]);

	useEffect(() => subscribeToasts(setItems), []);

	useEffect(() => {
		void showSchemaPromoOnLoad();
	}, []);

	if (items.length === 0) return null;

	return (
		<div className="toast-stack" aria-live="polite" aria-relevant="additions">
			{items.map((item) => (
				<output
					key={item.id}
					className={`toast toast-${item.variant}${item.leaving ? " toast-leaving" : ""}${item.action ? " toast-has-action" : ""}`}
				>
					<span className="toast-message">{item.message}</span>
					{item.action && (
						<a
							className="toast-action"
							href={item.action.href}
							target="_blank"
							rel="noopener noreferrer"
						>
							{item.action.label}
						</a>
					)}
				</output>
			))}
		</div>
	);
}
