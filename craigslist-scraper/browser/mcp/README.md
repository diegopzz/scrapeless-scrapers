# Craigslist — MCP surface

Scrape Craigslist search and listing pages conversationally from any MCP-capable AI agent or client using the [Scrapeless MCP server](https://github.com/scrapeless-ai/scrapeless-mcp-server).
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

Any MCP-capable AI agent or client works. Add the block above wherever your client stores its MCP servers. Two transports are available:

- **stdio** (shown above) — the client launches `npx -y scrapeless-mcp-server`.
- **HTTP** — agents that connect to a remote MCP URL can point at `https://api.scrapeless.com/mcp` with the header `x-api-token: sk_...`.

## 2. Set your API key

Use the key from [app.scrapeless.com](https://app.scrapeless.com) as `SCRAPELESS_KEY` in the config
above. Sign up there if you do not have one yet — new accounts include free Scraping Browser
runtime.

## 3. Scrape a search page

Once the server is connected, ask in plain language. Start with a search page:

```
Using the scrapeless tools, open
https://newyork.craigslist.org/search/sss?query=bicycle and return each
.cl-search-result card as { id, title, url, price, location, postedAt, image }.
```

## 4. Scrape a listing page

```
Open a Craigslist listing detail page (e.g.
https://newyork.craigslist.org/.../d/.../1234567890.html) with the scrapeless
browser and extract the Listing fields from ../../DATA_MODEL.md (id, title,
price, location, description, attributes, images, latitude, longitude, ...).
```

## 5. Output shape

The MCP surface emits whatever shape you ask for. To stay aligned with the `cli/`, `nodejs/`, and
`python/` surfaces, ask for the `SearchResult` and `Listing` fields documented in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in [`results/`](results/).

## 6. Notes

- Tool arguments are camelCase (`sessionId`, `proxyCountry`); `browser_close` rejects snake_case.
- Craigslist is light on anti-bot but rate-limits aggressively — scrape one page at a time and
  pause between hits.
- For repeatable, schema-validated output, use the `cli/`, `nodejs/`, or `python/` surfaces — the
  MCP surface is best for ad-hoc, conversational scraping.
