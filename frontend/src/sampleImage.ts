/** Bundled demo image served from ``/tiny.png``. */
export const SAMPLE_IMAGE_URL = "/tiny.png";
export const SAMPLE_IMAGE_FILENAME = "tiny.png";

export async function fetchSampleImageFile(): Promise<File> {
	const res = await fetch(SAMPLE_IMAGE_URL);
	if (!res.ok) {
		throw new Error("Could not load the sample image.");
	}
	const blob = await res.blob();
	const type = blob.type.startsWith("image/") ? blob.type : "image/png";
	return new File([blob], SAMPLE_IMAGE_FILENAME, { type });
}
