# SeLoger — MCP surface

Scrape SeLoger search results and property detail pages conversationally from any MCP-capable AI agent or client. No code — the LLM drives a Scrapeless cloud browser
through MCP tools and you ask for the fields described in [`../../DATA_MODEL.md`](../../DATA_MODEL.md).

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
Using the scrapeless tools, open a seloger.com classified-search page and
return each card as { title, url, images, price, price_per_m2,
property_facts, address, agency }.
```

## 4. Scrape a property

Property detail comes from the page's embedded bootstrap state:

```
Open a seloger.com property page with the scrapeless browser, decode the
window.__UFRN_LIFECYCLE_SERVERREQUEST__ bootstrap state, and return the
app_cldp.data.classified object.
```

## 5. Output shape

The MCP surface emits whatever shape you ask for. To stay aligned with the `cli/`, `nodejs/`, and
`python/` surfaces, ask for the `SearchResult` and `PropertyResult` fields documented in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in [`results/`](results/).

## 6. Notes

- Tool arguments are camelCase (`sessionId`, `proxyCountry`); `browser_close` rejects snake_case.
- SeLoger is a French real estate portal — create the session with an `FR` proxy country.
- The property detail payload is the raw decoded `classified` blob — downstream consumers should
  treat it as opaque JSON.
- For repeatable, schema-validated output, use the `cli/`, `nodejs/`, or `python/` surfaces — the
  MCP surface is best for ad-hoc, conversational scraping.
