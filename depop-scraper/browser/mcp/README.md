# Depop — MCP surface

Scrape Depop product, search, and shop pages conversationally from any MCP-capable AI agent or client using the [Scrapeless MCP server](https://github.com/scrapeless-ai/scrapeless-mcp-server).
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

## 3. Scrape a product page

Once the server is connected, ask in plain language. Start with a product page:

```
Using the scrapeless tools, open
https://www.depop.com/products/gasbiegzr-levis-jeans-size-25-light-7515/
and return the Product fields from ../../DATA_MODEL.md (id, title, price,
currency, brand, condition, size, images, seller, hashtags, sold) from the
ld+json Product tag.
```

## 4. Scrape a search page

```
Open https://www.depop.com/search/?q=levi+jeans with the scrapeless browser
and return each card as { id, title, url, image, price, originalPrice,
seller, size }.
```

## 5. Scrape a shop page

```
Open https://www.depop.com/depopofficial/ and return the Shop fields from
../../DATA_MODEL.md (username, displayName, bio, followers, following,
reviews, rating, listings) — read the __NEXT_DATA__ blob and the streaming
RSC seller chunk.
```

## 6. Output shape

The MCP surface emits whatever shape you ask for. To stay aligned with the `cli/`, `nodejs/`, and
`python/` surfaces, ask for the `Product`, `SearchResult`, and `Shop` fields documented in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in [`results/`](results/).

## 7. Notes

- Tool arguments are camelCase (`sessionId`, `proxyCountry`); `browser_close` rejects snake_case.
- Depop is a Next.js app — product cards and shop stats lazy-render; scroll the page before
  reading.
- For repeatable, schema-validated output, use the `cli/`, `nodejs/`, or `python/` surfaces — the
  MCP surface is best for ad-hoc, conversational scraping.
