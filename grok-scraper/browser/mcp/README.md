# Grok — MCP surface

Scrape public Grok shared conversations conversationally from any MCP-capable AI agent or client using the [Scrapeless MCP server](https://github.com/scrapeless-ai/scrapeless-mcp-server).
No code — the LLM drives a Scrapeless cloud browser through MCP tools and you ask for the fields
described in [`../../DATA_MODEL.md`](../../DATA_MODEL.md).

## 1. Install the scrapeless-mcp-server

Install the [`scrapeless-mcp-server`](https://github.com/scrapeless-ai/scrapeless-mcp-server) and add it from [`mcp.json`](mcp.json) to your MCP client:

```jsonc
{
  "mcpServers": {
    "scrapeless": {
      "command": "npx",
      "args": ["-y", "scrapeless-mcp-server"],
      "env": { "SCRAPELESS_KEY": "sk_..." }
    }
  }
}
```

Any MCP-capable AI agent or client works. Two transports are available:

- **stdio** (shown above) — the client launches `npx -y scrapeless-mcp-server`.
- **HTTP** — point at `https://api.scrapeless.com/mcp` with header `x-api-token: sk_...`.

## 2. Set your API key

Use the key from [app.scrapeless.com](https://app.scrapeless.com) as `SCRAPELESS_KEY`.

## 3. Scrape a shared conversation

Grok shared conversations at `grok.com/share/<id>` are publicly readable. Open the URL and read the DOM — no extra wait needed (page is server-side rendered):

```
Using the scrapeless tools, open
https://grok.com/share/bGVnYWN5_d6991719-5568-4608-b613-609cbd3f2842
and return one SharedConversation from ../../DATA_MODEL.md:
{ url, title, messages: [{ role, content }] }.

Read messages from [data-testid="user-message"] (role="user") and
[data-testid="assistant-message"] (role="assistant") elements, in DOM order.
The title comes from <title>. Strip the ?rid=... query parameter from the URL.
```

## 4. Output shape

The MCP surface emits whatever shape you ask for. To stay aligned with the `cli/`,
`nodejs/`, and `python/` surfaces, ask for the `SharedConversation` fields documented in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). A sample payload is in [`results/`](results/).

## 5. Notes

- Tool arguments are camelCase (`sessionId`, `proxyCountry`); `browser_close` rejects snake_case.
- Do **not** add a `wait` call after `open` — Grok's Cloudflare challenge can terminate idle sessions.
- For repeatable, schema-validated output use the `cli/`, `nodejs/`, or `python/` surfaces.
