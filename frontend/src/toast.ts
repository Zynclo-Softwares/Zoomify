export type ToastVariant = "error" | "info" | "success";

export type ToastAction = {
	label: string;
	href: string;
};

export type ToastItem = {
	id: string;
	message: string;
	variant: ToastVariant;
	action?: ToastAction;
	leaving: boolean;
};

export type ShowToastOptions = {
	variant?: ToastVariant;
	action?: ToastAction;
	/** Visible time before fade-out (ms). Default 5000. */
	duration?: number;
};

type Listener = (toasts: ToastItem[]) => void;

const FADE_MS = 400;
const DEFAULT_VISIBLE_MS = 5000;

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
	timers.delete(`${id}:remove`);
	emit();
}

export function subscribeToasts(listener: Listener): () => void {
	listeners.add(listener);
	listener([...toasts]);
	return () => listeners.delete(listener);
}

export function showToast(message: string, options: ShowToastOptions = {}) {
	const { variant = "info", action, duration = DEFAULT_VISIBLE_MS } = options;
	const id = crypto.randomUUID();
	toasts = [...toasts, { id, message, variant, action, leaving: false }];
	emit();

	const fadeTimer = setTimeout(() => {
		toasts = toasts.map((t) => (t.id === id ? { ...t, leaving: true } : t));
		emit();
	}, duration);

	const removeTimer = setTimeout(() => {
		removeToast(id);
	}, duration + FADE_MS);

	timers.set(id, fadeTimer);
	timers.set(`${id}:remove`, removeTimer);
}

export function showErrorToast(message: string) {
	showToast(message, { variant: "error" });
}

export function showSuccessToast(message: string) {
	showToast(message, { variant: "success" });
}

export function showInfoToast(
	message: string,
	options?: Omit<ShowToastOptions, "variant">,
) {
	showToast(message, { ...options, variant: "info" });
}
