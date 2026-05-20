# Google News — MCP surface

Scrape Google News article cards conversationally from any MCP-capable AI agent or client using the
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

## 3. Scrape a news search page

Once the server is connected, ask in plain language. Google News is a client-side SPA, so let the
LLM wait for the headline anchors (`a.JtKRv`) to mount before extracting.

```
Using the scrapeless tools, open
https://news.google.com/search?q=adidas&hl=en-US&gl=US&ceid=US:en and return
each article card as { position, title, url, source, time, thumbnail } — the
Article fields from ../../DATA_MODEL.md. Resolve the relative ./read/CBM... hrefs
to absolute https://news.google.com URLs.
```

## 4. Scrape a topic feed

Topic pages use the same card markup — just swap the URL. The topic id is the trailing path
component of a `news.google.com/topics/<id>` URL.

```
Using the scrapeless tools, open
https://news.google.com/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGRqTVhZU0FtVnVHZ0pWVXlnQVAB?hl=en-US&gl=US&ceid=US:en
and return each article as { position, title, url, source, time, thumbnail }.
```

## 5. Output shape

The MCP surface emits whatever shape you ask for. To stay aligned with the `cli/`, `nodejs/`, and
`python/` surfaces, ask for the `Article` fields documented in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in [`results/`](results/).

## 6. Notes

- Tool arguments are camelCase (`sessionId`, `proxyCountry`); `browser_close` rejects snake_case.
- The `hl` / `gl` / `ceid` URL params set the news locale; pair them with a matching `proxyCountry`
  at session creation if you need region-specific results. A per-call `proxyCountry` may be ignored.
- For repeatable, schema-validated output, use the `cli/`, `nodejs/`, or `python/` surfaces — the
  MCP surface is best for ad-hoc, conversational scraping.
