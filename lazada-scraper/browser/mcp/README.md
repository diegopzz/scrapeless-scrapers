# Lazada — MCP surface

Scrape Lazada product and search pages conversationally from any MCP-capable AI agent or client using the
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

Once the server is connected, ask in plain language. Lazada is geo-locked, so ask for a Singapore
(`SG`) proxy session:

```
Using the scrapeless tools, open https://www.lazada.sg/products/pdp-i3529149697.html
in an SG proxy session and return the Product fields from ../../DATA_MODEL.md
(id, url, title, brand, price, originalPrice, discount, currency, rating, reviews,
images, seller, sellerUrl, availability, description, categories).
```

## 4. Scrape a search page

```
Using the scrapeless tools, open https://www.lazada.sg/catalog/?q=iphone%20case
with an SG proxy, scroll to load the cards, and return each product as
{ id, title, url, image, price, originalPrice, discount, rating, reviews, location }.
```

## 5. Output shape

The MCP surface emits whatever shape you ask for. To stay aligned with the `cli/`, `nodejs/`, and
`python/` surfaces, ask for the `Product` and `SearchResult` fields documented in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in [`results/`](results/).

## 6. Notes

- Tool arguments are camelCase (`sessionId`, `proxyCountry`); `browser_close` rejects snake_case.
- Lazada is geo-locked. Set `proxyCountry` to `SG` at session creation — per-call `proxyCountry` may
  be ignored, and the wrong country changes currency, catalog, and may block the PDP.
- Lazada hydrates the PDP from the `mtop.global.detail.web.getDetailInfo` XHR. Ask the LLM to read
  the inline `window.__moduleData__` blob if the rendered DOM is sparse.
- For repeatable, schema-validated output, use the `cli/`, `nodejs/`, or `python/` surfaces — the
  MCP surface is best for ad-hoc, conversational scraping.
