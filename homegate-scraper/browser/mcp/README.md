# Homegate — MCP surface

Scrape Homegate search and property listing pages conversationally from any MCP-capable AI agent or client — no code, the LLM drives a Scrapeless cloud browser through MCP
tools.

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

Once the server is connected, ask in plain language. Homegate blocks cold deep links, so warm up on
the homepage first, then open a search page:

```
Using the scrapeless tools, open https://www.homegate.ch/ first to warm up the
session, then open https://www.homegate.ch/rent/real-estate/city-bern/matching-list
and extract the SearchResultEntry list from
window.__INITIAL_STATE__.resultList.search.fullSearch.result.listings.
```

## 4. Scrape a property listing

```
Using the scrapeless tools, open https://www.homegate.ch/ first to warm up the
session, then open https://www.homegate.ch/rent/4002086534 and return
window.__PINIA_INITIAL_STATE__.listing.listing as the Listing object.
```

## 5. Output shape

The MCP surface emits whatever shape you ask for. To stay aligned with the `cli/`, `nodejs/`, and
`python/` surfaces, ask for the `SearchResultEntry` and `Listing` fields documented in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in [`results/`](results/).

## 6. Notes

- Tool arguments are camelCase (`sessionId`, `proxyCountry`); `browser_close` rejects snake_case.
- Homegate blocks cold deep links — open the homepage first so the session holds a Homegate cookie,
  then navigate to the listing or search URL.
- For repeatable, schema-validated output, use the `cli/`, `nodejs/`, or `python/` surfaces — the
  MCP surface is best for ad-hoc, conversational scraping.
