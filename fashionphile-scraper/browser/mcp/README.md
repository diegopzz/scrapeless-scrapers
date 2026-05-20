# Fashionphile — MCP surface

Scrape Fashionphile conversationally from any MCP-capable AI agent or client —
no code. The [Scrapeless MCP server](https://github.com/scrapeless-ai/scrapeless-mcp-server) drives
a Scrapeless cloud browser through MCP tools and you ask for the fields described in
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

## 3. Scrape a product page

Once the server is connected, ask in plain language. Fashionphile exposes the storefront's own JSON
at `/products/<slug>.json` — point the LLM at that endpoint rather than the rendered `/p/<slug>`
page:

```
Using the scrapeless tools, open
https://www.fashionphile.com/products/louis-vuitton-ostrich-lizard-majestueux-tote-mm-navy-1247825.json
and return the `product` object from the JSON body verbatim (see
../../DATA_MODEL.md — id, title, handle, vendor, brand, variants, images, tags).
```

## 4. Output shape

The MCP surface emits whatever shape you ask for. To stay aligned with the `cli/`, `nodejs/`, and
`python/` surfaces, ask for the `Product` fields documented in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in [`results/`](results/).

## 5. Notes

- Tool arguments are camelCase (`sessionId`, `proxyCountry`); `browser_close` rejects snake_case.
- Fashionphile exposes the storefront's own JSON at `/products/<slug>.json` — point the LLM at that
  endpoint rather than scraping the rendered `/p/<slug>` page.
- For repeatable, schema-validated output, use the `cli/`, `nodejs/`, or `python/` surfaces — the
  MCP surface is best for ad-hoc, conversational scraping.
