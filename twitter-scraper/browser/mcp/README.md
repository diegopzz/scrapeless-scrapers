# Twitter (X) — MCP surface

Scrape Twitter / X conversationally from any MCP-capable AI agent or client —
no code. The LLM drives a Scrapeless cloud browser through MCP tools and you ask for the fields
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

## 3. Scrape a tweet detail page

Once the server is connected, ask in plain language. Start with a tweet detail page:

```
Using the scrapeless tools, open https://x.com/robinhanson/status/1872047986873885082
and return the Tweet fields from ../../DATA_MODEL.md (text, created_at,
favorite_count, retweet_count, reply_count, quote_count, views, ...).
```

## 4. Scrape a profile

```
Open https://x.com/robinhanson/ with the scrapeless browser and extract the
Profile fields from ../../DATA_MODEL.md (id, rest_id, verified, screen_name,
name, description, followers_count, friends_count, ...).
```

## 5. Output shape

The MCP surface emits whatever shape you ask for. To stay aligned with the `nodejs/` and `python/`
surfaces, ask for the `Tweet` and `Profile` fields documented in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in [`results/`](results/).

## 6. Notes

- X is a client-side SPA — the tweet/profile objects live in GraphQL XHR responses, not in the
  page DOM. Ask the LLM to read the rendered text/counts, or to inspect network responses if your
  client supports it.
- Public data only — tweet detail pages and public profiles render unauthenticated; replies,
  search, and following lists require login and are out of scope.
- Tool arguments are camelCase (`sessionId`, `proxyCountry`); `browser_close` rejects snake_case.
- For repeatable, schema-validated output, use the `nodejs/` or `python/` surfaces — they intercept
  the GraphQL responses directly. The MCP surface is best for ad-hoc, conversational scraping.
