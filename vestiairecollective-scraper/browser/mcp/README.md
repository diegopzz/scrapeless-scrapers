# Vestiaire Collective — MCP surface

Scrape Vestiaire Collective conversationally from any MCP-capable AI agent or client — no code. The LLM drives a Scrapeless cloud browser through MCP tools and you ask for
the fields described in [`../../DATA_MODEL.md`](../../DATA_MODEL.md).

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

## 3. Scrape a product listing page

Once the server is connected, ask in plain language. Start with a product listing page:

```
Using the scrapeless tools, open https://us.vestiairecollective.com/men-clothing/jackets/louis-vuitton/camel-polyester-louis-vuitton-jacket-66935196.shtml
and return the Product fields from ../../DATA_MODEL.md (id, name, price,
description, likeCount, brand, ...) read from __NEXT_DATA__ props.pageProps.product.
```

## 4. Scrape a search page

```
Open https://www.vestiairecollective.com/search/?q=louis+vuitton with the
scrapeless browser and return each search item as the SearchResult shape from
../../DATA_MODEL.md (id, name, price, seller, pictures, link, ...).
```

## 5. Output shape

The MCP surface emits whatever shape you ask for. To stay aligned with the `cli/`, `nodejs/`, and
`python/` surfaces, ask for the `Product` and `SearchResult` fields documented in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in [`results/`](results/).

## 6. Notes

- Listing pages hydrate the product object into `<script id="__NEXT_DATA__">` — point the LLM at
  `props.pageProps.product`.
- Search results come from the `/v1/product/search` XHR rather than server-rendered HTML; ask the
  LLM to read the rendered result tiles, or use the `nodejs/` / `python/` surface which intercepts
  that API directly.
- Tool arguments are camelCase (`sessionId`, `proxyCountry`); `browser_close` rejects snake_case.
- For repeatable, schema-validated output, use the `cli/`, `nodejs/`, or `python/` surfaces — the
  MCP surface is best for ad-hoc, conversational scraping.
