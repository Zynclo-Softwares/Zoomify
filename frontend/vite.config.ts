import path from "node:path";
import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const frontendRoot = path.dirname(fileURLToPath(import.meta.url));
// Bundled by FastAPI (server.py → frontend/dist) and the production Dockerfile.
const bundleOutDir = path.resolve(frontendRoot, "dist");

export default defineConfig({
	plugins: [react()],
	server: {
		port: 5173,
		proxy: {
			"/api": "http://127.0.0.1:8000",
		},
	},
	build: {
		outDir: bundleOutDir,
		emptyOutDir: true,
	},
});
