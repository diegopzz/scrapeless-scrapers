# Bing — MCP surface

Scrape Bing search results and keyword suggestions conversationally from any MCP-capable AI agent or client — no code. The LLM drives a Scrapeless cloud browser through MCP
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

Once the server is connected, ask in plain language. Start with a search-results page:

```
Using the scrapeless tools, open https://www.bing.com/search?q=web+scraping+emails
and return each organic result as { position, title, url, origin, domain, description, date }.
```

## 4. Scrape keyword suggestions

The keyword suggestions come from Bing's `/AS/Suggestions` autosuggest endpoint:

```
Open https://www.bing.com/AS/Suggestions?qry=web+scraping+emails&cc=us&FORM=BESBTB with the
scrapeless browser and return the related-keyword strings from the autosuggest JSON body.
```

## 5. Output shape

The MCP surface emits whatever shape you ask for. To stay aligned with the `cli/`, `nodejs/`, and
`python/` surfaces, ask for the `SearchResult` fields and the keyword string list documented in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in [`results/`](results/).

## 6. Notes

- Tool arguments are camelCase (`sessionId`, `proxyCountry`); `browser_close` rejects snake_case.
- Bing's classic `b_ans` related-searches block was replaced by Copilot in 2024 — keyword
  suggestions now come from the `/AS/Suggestions` autosuggest endpoint, whose body is escaped HTML.
- For repeatable, schema-validated output, use the `cli/`, `nodejs/`, or `python/` surfaces — the
  MCP surface is best for ad-hoc, conversational scraping.
