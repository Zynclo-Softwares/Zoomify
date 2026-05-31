/** Extract the first image from a clipboard paste, if any. */
export function imageFileFromClipboard(data: DataTransfer | null): File | null {
	if (!data) return null;

	for (const item of data.items) {
		if (item.kind !== "file") continue;
		if (!item.type.startsWith("image/")) continue;
		const blob = item.getAsFile();
		if (!blob) continue;
		const ext = blob.type.split("/")[1]?.replace("jpeg", "jpg") || "png";
		return new File([blob], `pasted-${Date.now()}.${ext}`, {
			type: blob.type,
		});
	}

	const fromFiles = data.files[0];
	if (fromFiles?.type.startsWith("image/")) {
		return fromFiles;
	}

	return null;
}

/** True when paste should not hijack image handling (password fields, etc.). */
export function isClipboardPasteTargetAllowed(
	target: EventTarget | null,
): boolean {
	if (!(target instanceof HTMLElement)) return true;
	if (target.closest(".composer-box")) return true;
	if (target.closest(".chat-panel")) return true;
	if (target === document.body) return true;
	return false;
}
