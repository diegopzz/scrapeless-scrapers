# Google Play — MCP surface

Scrape Google Play app detail pages conversationally from any MCP-capable AI agent or client — no code. The LLM drives a Scrapeless cloud browser through MCP tools and you
ask for the fields described in [`../../DATA_MODEL.md`](../../DATA_MODEL.md).

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

## 3. Scrape an app detail page

Once the server is connected, ask in plain language. Start with an app detail page:

```
Using the scrapeless tools, open
https://play.google.com/store/apps/details?id=com.spotify.music&hl=en_US&gl=US
and return the App fields from ../../DATA_MODEL.md (id, name, developer, rating,
rating_count, price, installs, description, categories, latest_update,
screenshots, icon, url).
```

## 4. Scrape another app

```
Open the Google Play listing for com.instagram.android with the scrapeless
browser and pull the SoftwareApplication JSON-LD blob plus the install band.
```

## 5. Output shape

The MCP surface emits whatever shape you ask for. To stay aligned with the `cli/`, `nodejs/`, and
`python/` surfaces, ask for the `App` fields documented in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in [`results/`](results/).

## 6. Notes

- Tool arguments are camelCase (`sessionId`, `proxyCountry`); `browser_close` rejects snake_case.
- The cleanest fields come from the embedded `application/ld+json` `SoftwareApplication` blob —
  wait for the `script[type='application/ld+json']` tag before reading the HTML.
- For repeatable, schema-validated output, use the `cli/`, `nodejs/`, or `python/` surfaces — the
  MCP surface is best for ad-hoc, conversational scraping.
