# Amazon — MCP surface

Scrape Amazon search, product, and review pages conversationally from any MCP-capable AI agent or client using the
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

## 3. Scrape a product page

Once the server is connected, ask in plain language. Start with a product page:

```
Using the scrapeless tools, open https://www.amazon.com/dp/B0BCNKKZ91 and return
the Product fields from ../../DATA_MODEL.md (name, asin, style, features, images,
info_table, stars, rating_count).
```

## 4. Scrape a search page

```
Using the scrapeless tools, open https://www.amazon.com/s?k=kindle and return
each result as { url, title, price, real_price, rating, rating_count }.
```

## 5. Scrape reviews

The review block renders on the product page itself:

```
Open https://www.amazon.com/dp/B0BCNKKZ91 with the scrapeless browser, scroll to
the reviews, and return each review as { title, text, location_and_date,
verified, rating }.
```

## 6. Output shape

The MCP surface emits whatever shape you ask for. To stay aligned with the `cli/`, `nodejs/`, and
`python/` surfaces, ask for the `SearchResult`, `Product`, and `Review` fields documented in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in [`results/`](results/).

## 7. Notes

- Tool arguments are camelCase (`sessionId`, `proxyCountry`); `browser_close` rejects snake_case.
- Per-call `proxyCountry` may be ignored — set the country at session creation if you need
  locale-specific pricing.
- For repeatable, schema-validated output, use the `cli/`, `nodejs/`, or `python/` surfaces — the
  MCP surface is best for ad-hoc, conversational scraping.
