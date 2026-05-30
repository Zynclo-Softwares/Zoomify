import { useEffect, useState } from "react";
import { subscribeToasts, type ToastItem } from "../toast";
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
					className={`toast${item.leaving ? " toast-leaving" : ""}`}
				>
					{item.message}
				</output>
			))}
		</div>
	);
}
