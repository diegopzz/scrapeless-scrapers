# G2 — MCP surface

Scrape G2 search, reviews, and alternatives pages conversationally from any MCP-capable AI agent or client — no code. The [Scrapeless MCP server](https://github.com/scrapeless-ai/scrapeless-mcp-server)
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

## 3. Scrape a search page

Once the server is connected, ask in plain language. Start with a search page:

```
Using the scrapeless tools, open https://www.g2.com/search?query=Infrastructure
and return each product card as { name, link, image, rate, reviewsNumber,
description, categories }.
```

## 4. Scrape a reviews page

```
Open https://www.g2.com/products/digitalocean/reviews with the scrapeless
browser and extract each Review as { author, review } per ../../DATA_MODEL.md.
```

Expect each entry to carry an `author` ({ authorName, authorProfile, authorPosition,
authorCompanySize }) and a `review` ({ reviewTags, reviewData, reviewRate, reviewTitle,
reviewLikes, reviewDislikes }).

## 5. Scrape an alternatives page

```
Open https://www.g2.com/products/digitalocean/competitors/alternatives/ with the
scrapeless browser and return each Alternative as { name, link, ranking,
numberOfReviews, rate, description }.
```

## 6. Output shape

The MCP surface emits whatever shape you ask for. To stay aligned with the `cli/`, `nodejs/`, and
`python/` surfaces, ask for the `SearchResult`, `Review`, and `Alternative` fields documented in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in [`results/`](results/).

## 7. Notes

- Tool arguments are camelCase (`sessionId`, `proxyCountry`); `browser_close` rejects snake_case.
- G2 review pages lazy-load — let the page settle (scroll down) before extracting so all `article`
  review nodes are present.
- For repeatable, schema-validated output, use the `cli/`, `nodejs/`, or `python/` surfaces — the
  MCP surface is best for ad-hoc, conversational scraping.
