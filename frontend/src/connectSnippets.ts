/** Connection snippets for popular MCP clients. Add a client by appending to CLIENTS. */

export const KEY_PLACEHOLDER = "YOUR_ZOOMIFY_API_KEY";

export type ClientSnippet = {
	id: string;
	label: string;
	/** Where the snippet goes (file path or "Terminal"). */
	target: string;
	language: "bash" | "json" | "toml";
	note?: string;
	build: (url: string, key: string) => string;
};

const json = (value: unknown) => JSON.stringify(value, null, 2);

export const CLIENTS: ClientSnippet[] = [
	{
		id: "claude-code",
		label: "Claude Code",
		target: "Terminal",
		language: "bash",
		note: "Add --scope user to make it available in every project.",
		build: (url, key) =>
			`claude mcp add --transport http zoomify ${url} \\\n  --header "Authorization: Bearer ${key}"`,
	},
	{
		id: "cursor",
		label: "Cursor",
		target: "~/.cursor/mcp.json",
		language: "json",
		note: "Use .cursor/mcp.json inside a repo to scope it to that project.",
		build: (url, key) =>
			json({
				mcpServers: {
					zoomify: { url, headers: { Authorization: `Bearer ${key}` } },
				},
			}),
	},
	{
		id: "vscode",
		label: "VS Code",
		target: ".vscode/mcp.json",
		language: "json",
		note: "Works with GitHub Copilot agent mode.",
		build: (url, key) =>
			json({
				servers: {
					zoomify: {
						type: "http",
						url,
						headers: { Authorization: `Bearer ${key}` },
					},
				},
			}),
	},
	{
		id: "codex",
		label: "Codex",
		target: "~/.codex/config.toml",
		language: "toml",
		note: "Codex reads the key from the environment variable named below.",
		build: (url, key) =>
			`# export ZOOMIFY_API_KEY="${key}"\n\n[mcp_servers.zoomify]\nurl = "${url}"\nbearer_token_env_var = "ZOOMIFY_API_KEY"`,
	},
	{
		id: "gemini",
		label: "Gemini CLI",
		target: "~/.gemini/settings.json",
		language: "json",
		build: (url, key) =>
			json({
				mcpServers: {
					zoomify: {
						httpUrl: url,
						headers: { Authorization: `Bearer ${key}` },
					},
				},
			}),
	},
	{
		id: "windsurf",
		label: "Windsurf",
		target: "~/.codeium/windsurf/mcp_config.json",
		language: "json",
		build: (url, key) =>
			json({
				mcpServers: {
					zoomify: {
						serverUrl: url,
						headers: { Authorization: `Bearer ${key}` },
					},
				},
			}),
	},
	{
		id: "claude-desktop",
		label: "Claude Desktop",
		target: "claude_desktop_config.json",
		language: "json",
		note: "Uses the mcp-remote bridge (needs Node.js) so the key can be sent as a header.",
		build: (url, key) =>
			json({
				mcpServers: {
					zoomify: {
						command: "npx",
						args: [
							"-y",
							"mcp-remote",
							url,
							"--header",
							`Authorization: Bearer ${key}`,
						],
					},
				},
			}),
	},
	{
		id: "url",
		label: "URL only",
		target: "Connector URL",
		language: "bash",
		note: "For clients that accept a URL but no custom headers. The URL contains your key — treat it like a password.",
		build: (url, key) => `${url}?api_key=${key}`,
	},
	{
		id: "curl",
		label: "cURL test",
		target: "Terminal",
		language: "bash",
		note: "Lists the tools — a quick way to check the key and endpoint.",
		build: (url, key) =>
			`curl -s ${url} \\\n  -H "Authorization: Bearer ${key}" \\\n  -H "Content-Type: application/json" \\\n  -H "Accept: application/json, text/event-stream" \\\n  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'`,
	},
];

export function uploadCurl(uploadUrl: string, key: string): string {
	return `curl -s ${uploadUrl} \\\n  -H "Authorization: Bearer ${key}" \\\n  -F "file=@drawing.pdf"`;
}

export const EXAMPLE_PROMPT =
	"Use Zoomify to open ./site-plan.png (a local path or a public link both work). Read the zoom-basics skill first, then list every label in the legend and the sheet number from the title block. Zoom until each value is sharp and tell me where you read it.";
