export type SampleImageId = "fuzzy-text" | "blueprint" | "handwriting";

const SAMPLE_IMAGES: Record<SampleImageId, { url: string; filename: string }> =
	{
		"fuzzy-text": { url: "/tiny.png", filename: "tiny.png" },
		blueprint: { url: "/blueprint.png", filename: "blueprint.png" },
		handwriting: { url: "/handwriting.jpeg", filename: "handwriting.jpeg" },
	};

export async function fetchSampleImageFile(id: SampleImageId): Promise<File> {
	const { url, filename } = SAMPLE_IMAGES[id];
	const res = await fetch(url);
	if (!res.ok) {
		throw new Error("Could not load the sample image.");
	}
	const blob = await res.blob();
	const type = blob.type.startsWith("image/") ? blob.type : "image/png";
	return new File([blob], filename, { type });
}
