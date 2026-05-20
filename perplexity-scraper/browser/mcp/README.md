# Perplexity — MCP surface

Scrape Perplexity answer pages conversationally from any MCP-capable AI agent or client using the [Scrapeless MCP server](https://github.com/scrapeless-ai/scrapeless-mcp-server).
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

## 3. Scrape an answer page

Once the server is connected, ask in plain language. Perplexity renders an answer page when you open
`https://www.perplexity.ai/search/new?q=<prompt>` — let it stream, then read it back:

```
Using the scrapeless tools, open
https://www.perplexity.ai/search/new?q=top%203%20smartphones%20in%202025%2C%20compare%20pricing%20across%20US%20marketplaces
wait for the answer prose (div[class*='prose']) to render, and return one Search object from
../../DATA_MODEL.md: { query, url, answer_text, citations }.
```

`citations` should be the deduped outbound `<a href="http...">` links that are not
Perplexity-internal, each as `{ url, domain, title }`. The `query` is read from the
`h1[class*='group/query']` heading (falling back to the `q` query param the page was opened with).

If the answer hasn't finished streaming, ask the model to wait a few seconds and re-read the page
before returning — otherwise `answer_text` / `citations` may come back empty.

## 4. Output shape

The MCP surface emits whatever shape you ask for. To stay aligned with the `cli/`, `nodejs/`, and
`python/` surfaces, ask for the `Search` fields documented in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). A sample payload is in [`results/`](results/).

## 5. Notes

- Tool arguments are camelCase (`sessionId`, `proxyCountry`); `browser_close` rejects snake_case.
- Per-call `proxyCountry` may be ignored — set the country at session creation if you need a
  specific locale for the answer.
- For repeatable, schema-validated output, use the `cli/`, `nodejs/`, or `python/` surfaces — the
  MCP surface is best for ad-hoc, conversational scraping.
