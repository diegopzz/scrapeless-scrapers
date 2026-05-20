# Similarweb — MCP surface

Scrape Similarweb website overview, head-to-head compare, and trending category pages
conversationally from any MCP-capable AI agent or client using the
[Scrapeless MCP server](https://github.com/scrapeless-ai/scrapeless-mcp-server). No code — the LLM
drives a Scrapeless cloud browser through MCP tools and you ask for the fields described in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md).

Similarweb is a React SPA whose data boots from a `window.__APP_DATA__` global; tell the model to
read that global (and the `script#dataset-json-ld` block for trending pages) rather than scraping
the rendered DOM.

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

## 3. Scrape a website overview

Once the server is connected, ask in plain language. Start with a website overview page:

```
Using the scrapeless tools, open https://www.similarweb.com/website/google.com/, wait for
the page to render, then return window.__APP_DATA__.layout.data as the Website object from
../../DATA_MODEL.md (overview, traffic, trafficSources, ranking, demographics, geography,
competitors, keywords).
```

## 4. Compare two domains

```
Using the scrapeless tools, open https://www.similarweb.com/website/google.com/vs/youtube.com/
and return { "google.com": {...}, "youtube.com": {...} } where each value has overview, traffic,
trafficSources, ranking, demographics, geography (from window.__APP_DATA__.layout.data).
```

## 5. Scrape a trending category

```
Using the scrapeless tools, open
https://www.similarweb.com/top-websites/computers-electronics-and-technology/programming-and-developer-software/
read the script#dataset-json-ld JSON-LD block, and return { name, url, list } where name is
mainEntity.name and list is mainEntity.itemListElement.
```

> The `nodejs/` `scrape_sitemaps` surface (gunzip of a `.xml.gz` sitemap) has no conversational MCP
> equivalent — it needs raw-byte gzip decoding, not an in-page read. Use the `nodejs/` or `python/`
> surface for sitemaps.

## 6. Output shape

The MCP surface emits whatever shape you ask for. To stay aligned with the `cli/`, `nodejs/`, and
`python/` surfaces, ask for the `Website`, `CompareResult`, and `Trending` fields documented in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). A live-captured `website` payload is in
[`results/website.json`](results/website.json).

## 7. Notes

- Tool arguments are camelCase (`sessionId`, `proxyCountry`); `browser_close` rejects snake_case.
- Per-call `proxyCountry` may be ignored — set the country at session creation if you need
  locale-specific traffic estimates. Similarweb data defaults to a US/global view.
- For repeatable, schema-validated output, use the `cli/`, `nodejs/`, or `python/` surfaces — the
  MCP surface is best for ad-hoc, conversational scraping.
