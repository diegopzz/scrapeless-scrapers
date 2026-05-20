# Trivago — MCP surface

Scrape Trivago destination pages — both the accommodation result list and the destination summary —
conversationally from any MCP-capable AI agent or client. No code — the LLM
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

## 3. Scrape a destination's result list

Once the server is connected, ask in plain language. Both surfaces read the JSON-LD that Trivago
server-renders on every destination page, so a single open covers both. Start with the result list:

```
Using the scrapeless tools, open
https://www.trivago.com/en-US/odr/hotels-new-york-city-new-york-united-states-of-america?search=200-2755
read the application/ld+json ItemList block, and return each Hotel as a
SearchResult { position, name, url, address, image, description, priceRange,
ratingValue, reviewCount, bestRating, worstRating } from ../../DATA_MODEL.md.
```

## 4. Scrape the destination summary

The destination's breadcrumb and FAQ context render on the same page — no new open needed:

```
From that same Trivago destination page, also return the Destination object
{ url, name, breadcrumbs, totalHotels, faq, topHotels } — breadcrumbs from the
BreadcrumbList JSON-LD, faq as { question, answer } pairs from the FAQPage
JSON-LD, and topHotels from the ItemList.
```

## 5. Output shape

The MCP surface emits whatever shape you ask for. To stay aligned with the `cli/`, `nodejs/`, and
`python/` surfaces, ask for the `SearchResult` and `Destination` fields documented in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in [`results/`](results/).

## 6. Notes

- Tool arguments are camelCase (`sessionId`, `proxyCountry`); `browser_close` rejects snake_case.
- Trivago is anti-bot-heavy in the DOM (results hydrate via GraphQL after JS), but the JSON-LD
  `ItemList` is rendered server-side — ask the model to read the `script[type="application/ld+json"]`
  blocks rather than the rendered cards.
- The rating scale is 0–10 (`ratingValue`/`bestRating`), not the usual 0–5.
- For repeatable, schema-validated output, use the `cli/`, `nodejs/`, or `python/` surfaces — the
  MCP surface is best for ad-hoc, conversational scraping.
