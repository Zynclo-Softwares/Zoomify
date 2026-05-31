import { readApiErrorMessage } from "./apiErrors";
import { showErrorToast } from "./toast";

const STORAGE_KEY = "zoomify.encrypted_api_key";
const FINGERPRINT_KEY = "zoomify.byok_key_fingerprint";
export const BYOK_HEADER = "X-Encrypted-Api-Key";

let cachedPublicKeyPem: string | null = null;
let cachedCryptoKey: CryptoKey | null = null;

function pemToArrayBuffer(pem: string): ArrayBuffer {
	const b64 = pem
		.replace(/-----BEGIN PUBLIC KEY-----/, "")
		.replace(/-----END PUBLIC KEY-----/, "")
		.replace(/\s/g, "");
	const binary = atob(b64);
	const bytes = new Uint8Array(binary.length);
	for (let i = 0; i < binary.length; i += 1) {
		bytes[i] = binary.charCodeAt(i);
	}
	return bytes.buffer;
}

async function fingerprintPem(pem: string): Promise<string> {
	const digest = await crypto.subtle.digest(
		"SHA-256",
		new TextEncoder().encode(pem),
	);
	return Array.from(new Uint8Array(digest))
		.map((b) => b.toString(16).padStart(2, "0"))
		.join("");
}

export async function fetchByokPublicKey(): Promise<string> {
	if (cachedPublicKeyPem) return cachedPublicKeyPem;
	const res = await fetch("/api/byok/public-key");
	if (!res.ok) {
		const message = await readApiErrorMessage(res);
		showErrorToast(message);
		throw new Error(message);
	}
	const data = (await res.json()) as { public_key_pem: string };
	cachedPublicKeyPem = data.public_key_pem;
	return cachedPublicKeyPem;
}

async function importPublicKey(pem: string): Promise<CryptoKey> {
	if (cachedCryptoKey) return cachedCryptoKey;
	cachedCryptoKey = await crypto.subtle.importKey(
		"spki",
		pemToArrayBuffer(pem),
		{ name: "RSA-OAEP", hash: "SHA-256" },
		false,
		["encrypt"],
	);
	return cachedCryptoKey;
}

export async function encryptApiKey(plaintext: string): Promise<string> {
	const pem = await fetchByokPublicKey();
	const key = await importPublicKey(pem);
	const encrypted = await crypto.subtle.encrypt(
		{ name: "RSA-OAEP" },
		key,
		new TextEncoder().encode(plaintext.trim()),
	);
	const bytes = new Uint8Array(encrypted);
	let binary = "";
	for (const byte of bytes) {
		binary += String.fromCharCode(byte);
	}
	return btoa(binary);
}

export function getStoredEncryptedKey(): string | null {
	try {
		const value = localStorage.getItem(STORAGE_KEY);
		return value?.trim() || null;
	} catch {
		return null;
	}
}

/** Drop saved key when the server encryption key changed (e.g. dev restart). */
export async function validateStoredKey(): Promise<boolean> {
	if (!getStoredEncryptedKey()) return false;
	resetByokCache();
	try {
		const pem = await fetchByokPublicKey();
		const storedFp = localStorage.getItem(FINGERPRINT_KEY);
		if (!storedFp) return true;
		const currentFp = await fingerprintPem(pem);
		if (storedFp !== currentFp) {
			clearStoredApiKey();
			return false;
		}
		return true;
	} catch {
		return Boolean(getStoredEncryptedKey());
	}
}

export async function rememberKeyFingerprint(): Promise<void> {
	if (!getStoredEncryptedKey()) return;
	const pem = await fetchByokPublicKey();
	localStorage.setItem(FINGERPRINT_KEY, await fingerprintPem(pem));
}

export async function saveApiKey(plaintext: string): Promise<void> {
	const trimmed = plaintext.trim();
	if (!trimmed) {
		clearStoredApiKey();
		return;
	}
	resetByokCache();
	const pem = await fetchByokPublicKey();
	const encrypted = await encryptApiKey(trimmed);
	localStorage.setItem(STORAGE_KEY, encrypted);
	localStorage.setItem(FINGERPRINT_KEY, await fingerprintPem(pem));
}

export function clearStoredApiKey(): void {
	localStorage.removeItem(STORAGE_KEY);
	localStorage.removeItem(FINGERPRINT_KEY);
}

export function byokHeaders(): HeadersInit {
	const encrypted = getStoredEncryptedKey();
	return encrypted ? { [BYOK_HEADER]: encrypted } : {};
}

export function resetByokCache(): void {
	cachedPublicKeyPem = null;
	cachedCryptoKey = null;
}
