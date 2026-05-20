# Realtor.com — MCP surface

Scrape Realtor.com's sitemap feed conversationally from any MCP-capable AI agent or client using the
[Scrapeless MCP server](https://github.com/scrapeless-ai/scrapeless-mcp-server). No code — the LLM
drives a Scrapeless cloud browser through MCP tools and you ask for the fields described in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md).

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

Any MCP-capable AI agent or client works. Add the block above wherever your client stores its MCP servers. Two transports are available:

- **stdio** (shown above) — the client launches `npx -y scrapeless-mcp-server`.
- **HTTP** — agents that connect to a remote MCP URL can point at `https://api.scrapeless.com/mcp` with the header `x-api-token: sk_...`.

## 2. Set your API key

Use the key from [app.scrapeless.com](https://app.scrapeless.com) as `SCRAPELESS_KEY` in the config
above. Sign up there if you do not have one yet — new accounts include free Scraping Browser
runtime.

## 3. Scrape the sitemap feed

Once the server is connected, ask in plain language:

```
Open https://cdn.realtor.ca/sitemap/realtorsitemap/sitemap.xml with the
scrapeless browser and return a { loc: lastmod } mapping from the sitemap.
```

## 4. Output shape

The MCP surface emits whatever shape you ask for. To stay aligned with the `cli/`, `nodejs/`, and
`python/` surfaces, ask for the `FeedEntry` fields documented in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in [`results/`](results/).

## 5. Notes

- Tool arguments are camelCase (`sessionId`, `proxyCountry`); `browser_close` rejects snake_case.
- Search and property data are best fetched from the `cli/`, `nodejs/`, or `python/` surfaces
  (which set a residential `proxyCountry`). The sitemap feed above is served from the realtor.CA CDN.
