# Zillow — MCP surface

Scrape Zillow property (homedetails) pages conversationally from any MCP-capable AI agent or client — no code. The LLM drives a Scrapeless cloud browser through MCP tools
and you ask for the fields described in [`../../DATA_MODEL.md`](../../DATA_MODEL.md).

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

## 3. Scrape a property page

Once the server is connected, ask in plain language:

```
Using the scrapeless tools, open
https://www.zillow.com/homedetails/661-Lakeview-Ave-San-Francisco-CA-94112/15192198_zpid/
and return the Property object — unwrap props.pageProps.componentProps.gdpClientCache
from the embedded __NEXT_DATA__ script and emit its first entry's `property`.
```

## 4. Output shape

The MCP surface emits whatever shape you ask for. To stay aligned with the `cli/`, `nodejs/`, and
`python/` surfaces, ask for the `Property` and `SearchResult` fields documented in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in [`results/`](results/).

## 5. Notes

- Tool arguments are camelCase (`sessionId`, `proxyCountry`); `browser_close` rejects snake_case.
- Zillow is DataDome-protected — Scrapeless's residential proxy + fingerprinting handles the
  challenge; render the page fully before reading `__NEXT_DATA__`.
- Search results come from the `/async-create-search-page-state` PUT endpoint — ask the model to
  bootstrap the `queryState` from `__NEXT_DATA__` then `PUT` from inside the page, or just use the
  `nodejs/` / `python/` surface.
- For repeatable, schema-validated output, use the `cli/`, `nodejs/`, or `python/` surfaces — the
  MCP surface is best for ad-hoc, conversational scraping.
