import { friendlyApiMessage } from "./apiErrors";

export type ToastItem = {
	id: string;
	message: string;
	leaving: boolean;
};

type Listener = (toasts: ToastItem[]) => void;

const FADE_MS = 400;
const VISIBLE_MS = 5000;

let toasts: ToastItem[] = [];
const listeners = new Set<Listener>();
const timers = new Map<string, ReturnType<typeof setTimeout>>();

function emit() {
	for (const listener of listeners) {
		listener([...toasts]);
	}
}

function removeToast(id: string) {
	toasts = toasts.filter((t) => t.id !== id);
	timers.delete(id);
	emit();
}

export function subscribeToasts(listener: Listener): () => void {
	listeners.add(listener);
	listener([...toasts]);
	return () => listeners.delete(listener);
}

export function showToast(message: string) {
	const id = crypto.randomUUID();
	toasts = [...toasts, { id, message, leaving: false }];
	emit();

	const fadeTimer = setTimeout(() => {
		toasts = toasts.map((t) => (t.id === id ? { ...t, leaving: true } : t));
		emit();
	}, VISIBLE_MS);

	const removeTimer = setTimeout(() => {
		removeToast(id);
	}, VISIBLE_MS + FADE_MS);

	timers.set(id, fadeTimer);
	timers.set(`${id}:remove`, removeTimer);
}

export function showApiToast(status: number, detail?: unknown) {
	showToast(friendlyApiMessage(status, detail));
}
