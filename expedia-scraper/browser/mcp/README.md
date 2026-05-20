# Expedia — MCP surface

Scrape Expedia hotel-search and hotel-detail pages conversationally from any MCP-capable AI agent or client using the
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

## 3. Scrape a hotel-search page

Once the server is connected, ask in plain language. Expedia ships a "Bot or Not?" interstitial on
cold visits to `/Hotel-Search`, so tell the model to warm up at the homepage first, then navigate to
the search URL.

```
Using the scrapeless tools, first open https://www.expedia.com/ to warm up the session,
then open https://www.expedia.com/Hotel-Search?destination=New+York&startDate=2026-06-15&endDate=2026-06-16&rooms=1&adults=2
and return each lodging card as { id, name, url, price, review, image }.
```

## 4. Scrape a hotel-detail page

Reuse the same warmed-up session — open a `.Hotel-Information` detail URL (one of the `url` values
from the search result above works).

```
Using the scrapeless tools, open https://www.expedia.com/New-York-Hotels-The-St-Regis-New-York.h6365.Hotel-Information
and return the Hotel fields from ../../DATA_MODEL.md
(id, url, name, address, description, amenities, images, review, price).
```

## 5. Output shape

The MCP surface emits whatever shape you ask for. To stay aligned with the `cli/`, `nodejs/`, and
`python/` surfaces, ask for the `SearchResult` and `Hotel` fields documented in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in [`results/`](results/).

## 6. Notes

- Tool arguments are camelCase (`sessionId`, `proxyCountry`); `browser_close` rejects snake_case.
- Warm up at `https://www.expedia.com/` before the search URL — a cold direct hit on `/Hotel-Search`
  trips Expedia's "Bot or Not?" interstitial.
- Per-call `proxyCountry` may be ignored — set the country (e.g. `US`) at session creation if you
  need USD pricing and US inventory.
- For repeatable, schema-validated output, use the `cli/`, `nodejs/`, or `python/` surfaces — the
  MCP surface is best for ad-hoc, conversational scraping.
