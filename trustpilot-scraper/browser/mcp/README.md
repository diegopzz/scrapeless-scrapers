# Trustpilot — MCP surface

Scrape Trustpilot category and company pages conversationally from any MCP-capable AI agent or client using the
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

## 3. Scrape a category page

Once the server is connected, ask in plain language. Trustpilot hydrates everything into a
`<script id="__NEXT_DATA__">` payload, so the model just needs to read that JSON. Start with a
category page:

```
Using the scrapeless tools, open https://www.trustpilot.com/categories/electronics_technology and
return each business from props.pageProps.businessUnits.businesses as a SearchResult
{ identifyingName, displayName, trustScore, numberOfReviews, stars }.
```

## 4. Scrape a company page

```
Using the scrapeless tools, open https://www.trustpilot.com/review/www.flashbay.com and return a
Company { pageUrl, companyDetails, reviews } from props.pageProps (companyDetails is the
businessUnit object; reviews is the first page of reviews).
```

## 5. Scrape reviews

Trustpilot paginates reviews through its `/_next/data/<buildId>/review/<host>.json` data API. The
MCP browser flow can read the first page off the company page itself:

```
Open https://www.trustpilot.com/review/www.flashbay.com with the scrapeless browser and return each
review from props.pageProps.reviews as { id, consumer, rating, title, text, dates }.
```

For full multi-page review pagination, use the `nodejs/` or `python/` surface (`scrape_reviews`).

## 6. Output shape

The MCP surface emits whatever shape you ask for. To stay aligned with the `cli/`, `nodejs/`, and
`python/` surfaces, ask for the `SearchResult` (Business), `Company`, and `Review` fields documented
in [`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in [`results/`](results/).

## 7. Notes

- Tool arguments are camelCase (`sessionId`, `proxyCountry`); `browser_close` rejects snake_case.
- Per-call `proxyCountry` may be ignored — set the country at session creation if you need
  locale-specific results.
- For repeatable, schema-validated output, use the `cli/`, `nodejs/`, or `python/` surfaces — the
  MCP surface is best for ad-hoc, conversational scraping.
