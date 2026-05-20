# Worten — MCP surface

Scrape Worten product and category pages conversationally from any MCP-capable AI agent or client using the
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

## 3. Scrape a product page

Once the server is connected, ask in plain language. Worten exposes a schema.org `ld+json` Product
blob plus a BreadcrumbList blob, so the model just reads those `<script type="application/ld+json">`
tags. Start with a product page:

```
Using the scrapeless tools, open
https://www.worten.pt/produtos/iphone-15-pro-max-apple-6-7-256-gb-titanio-branco-7851167 and return
the Product fields from ../../DATA_MODEL.md (sku, name, brand, description, image, price,
priceCurrency, availability, ratingValue, reviewCount, url, breadcrumb) parsed from the
schema.org Product and BreadcrumbList ld+json blocks.
```

## 4. Scrape a category page

Category result tiles render client-side behind a Turnstile gate, so ask only for the SSR signals —
the heading, page meta, and breadcrumb:

```
Using the scrapeless tools, open https://www.worten.pt/promocoes/pequenos-eletrodomesticos and
return a Category { name, title, description, url, breadcrumb } (name from the <h1>, title from
<title>, description from meta[name=description], breadcrumb from the BreadcrumbList ld+json).
```

## 5. Output shape

The MCP surface emits whatever shape you ask for. To stay aligned with the `cli/`, `nodejs/`, and
`python/` surfaces, ask for the `Product` and `Category` fields documented in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md). Sample payloads are in [`results/`](results/).

## 6. Notes

- Tool arguments are camelCase (`sessionId`, `proxyCountry`); `browser_close` rejects snake_case.
- Per-call `proxyCountry` may be ignored — set the country at session creation. Worten is a
  Portuguese retailer; a PT/EU egress returns the cleanest pages.
- For repeatable, schema-validated output, use the `cli/`, `nodejs/`, or `python/` surfaces — the
  MCP surface is best for ad-hoc, conversational scraping.
