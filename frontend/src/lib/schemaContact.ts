type OpenListener = () => void;

const listeners = new Set<OpenListener>();

export function subscribeSchemaContactOpen(listener: OpenListener): () => void {
	listeners.add(listener);
	return () => listeners.delete(listener);
}

export function openSchemaContact() {
	for (const listener of listeners) {
		listener();
	}
}
