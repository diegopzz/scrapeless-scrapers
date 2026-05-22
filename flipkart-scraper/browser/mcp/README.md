# Flipkart — MCP surface

Scrape Flipkart product and search pages conversationally from any MCP-capable AI agent or client using the
[Scrapeless MCP server](https://github.com/scrapeless-ai/scrapeless-mcp-server). No code — the LLM
drives a Scrapeless cloud browser through MCP tools and you ask for the fields described in
[`../../DATA_MODEL.md`](../../DATA_MODEL.md).

## 1. Install the scrapeless-mcp-server

Add the config from [`mcp.json`](mcp.json) to your MCP client:

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

## 2. Set your API key

Use the key from [app.scrapeless.com](https://app.scrapeless.com) as `SCRAPELESS_KEY`.

## 3. Scrape a product page

```
Using the scrapeless tools, open
https://www.flipkart.com/apple-iphone-16-white-128-gb/p/itm7c0281cd247be
with proxyCountry IN, wait 12000ms for the page to fully hydrate (Flipkart injects ld+json
after JS execution), then return the Product fields from ../../DATA_MODEL.md
(id, name, brand, description, image, price, priceCurrency, availability, ratingValue,
reviewCount, url, breadcrumb) parsed from the schema.org Product ld+json array block.
The ld+json is a top-level JSON array containing a single Product object — extract
id from sku, brand from brand.name, price from offers.price, ratingValue from
aggregateRating.ratingValue, reviewCount from aggregateRating.reviewCount.
breadcrumb is always [].
```

## 4. Scrape a search page

```
Using the scrapeless tools, open
https://www.flipkart.com/search?q=iphone+16&marketplace=FLIPKART
with proxyCountry IN, wait 6000ms for the page to render, then return up to 10
SearchResult objects { id, name, url, image, price, priceCurrency, ratingValue } from
the [data-id] cards — id from the data-id attribute, name from .RG5Slk text (img alt
as fallback), url from a[href*="/p/"] cleaned of query params with https://www.flipkart.com
prepended, price from .hZ3P6w text (strip ₹ and commas), ratingValue from .MKiFS6 text.
```

## 5. Notes

- Use `proxyCountry: IN` for Flipkart India pricing.
- Flipkart product pages require ~12 seconds of settle time for JS hydration to inject the ld+json block.
- Tool arguments are camelCase (`sessionId`, `proxyCountry`); `browser_close` rejects snake_case.
- The ld+json block is a JSON array `[{...Product...}]`, not a bare object.
- Sample payloads are in [`results/`](results/).
