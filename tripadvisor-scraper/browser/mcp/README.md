# TripAdvisor — MCP surface

Scrape TripAdvisor conversationally from any MCP-capable AI agent or client —
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

## 3. Scrape a hotels listing page

Once the server is connected, ask in plain language. Start with a hotels listing page:

```
Using the scrapeless tools, open
https://www.tripadvisor.com/Hotels-g60763-New_York_City_New_York-Hotels.html
and return each hotel card as { url, name }.
```

## 4. Scrape a hotel review page

```
Open a TripAdvisor Hotel_Review page with the scrapeless browser and extract
the Hotel fields from ../../DATA_MODEL.md (basic_data from the JSON-LD block,
description, featues, reviews).
```

## 5. Output shape

The MCP surface emits whatever shape you ask for. To stay aligned with the `cli/`, `nodejs/`, and
`python/` surfaces, ask for the `Preview` and `Hotel` fields documented in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in [`results/`](results/).

## 6. Notes

- Tool arguments are camelCase (`sessionId`, `proxyCountry`); `browser_close` rejects snake_case.
- TripAdvisor shows a "Pardon Our Interruption" / Captcha shell to fresh proxies — warm up on
  `tripadvisor.com` first, or retry with a new session if the page looks blocked.
- The hotel `basic_data` lives in a `<script type="application/ld+json">` LodgingBusiness block —
  ask the model to read that rather than the rendered DOM.
- For repeatable, schema-validated output, use the `cli/`, `nodejs/`, or `python/` surfaces — the
  MCP surface is best for ad-hoc, conversational scraping.
