# AliExpress — MCP surface

Scrape AliExpress search and review pages conversationally from any MCP-capable AI agent or client — no code. The LLM drives a Scrapeless cloud browser through MCP
tools and you ask for the fields described in [`../../DATA_MODEL.md`](../../DATA_MODEL.md).

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

Once the server is connected, ask in plain language:

```
Using the scrapeless tools, open
https://www.aliexpress.com/w/wholesale-drills.html?catId=0&SearchText=drills
and return the search-result items from the embedded _init_data_ JSON.
```

## 4. Scrape reviews

The reviews come from AliExpress's feedback JSON endpoint:

```
Open https://feedback.aliexpress.com/pc/searchEvaluation.do?productId=1005006717259012&lang=en_US&country=US&page=1&pageSize=10&filter=all&sort=complex_default
and return the Reviews wrapper { reviews, evaluation_stats } from the JSON body.
```

## 5. Output shape

The MCP surface emits whatever shape you ask for. To stay aligned with the `cli/`, `nodejs/`, and
`python/` surfaces, ask for the search-result and `Reviews` shapes documented in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in [`results/`](results/).

## 6. Notes

- Tool arguments are camelCase (`sessionId`, `proxyCountry`); `browser_close` rejects snake_case.
- Set an `aep_usuc_f` cookie for USD pricing — AliExpress localizes price and currency by region.
- For repeatable, schema-validated output, use the `cli/`, `nodejs/`, or `python/` surfaces — the
  MCP surface is best for ad-hoc, conversational scraping. Product-detail data is best fetched from
  the `cli/`, `nodejs/`, or `python/` surfaces, which set a residential `proxyCountry`.
