# MercadoLibre — MCP surface

Scrape MercadoLibre product and search pages conversationally from any MCP-capable AI agent or client using the
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
https://articulo.mercadolibre.com.mx/MLM-4493249540-tenis-adidas-casual-run-60s-40-hombre-negro-jr6622-_JM
with proxyCountry MX, wait for the page to fully load (use wait 6000), then return the Product
fields from ../../DATA_MODEL.md (id, name, brand, description, image, price, priceCurrency,
availability, ratingValue, reviewCount, url, breadcrumb) parsed from the schema.org Product and
BreadcrumbList ld+json blocks.
```

## 4. Scrape a search page

```
Using the scrapeless tools, open https://listado.mercadolibre.com.mx/tenis with proxyCountry MX,
wait 5000ms for the page to render, then return up to 10 SearchResult objects
{ id, name, url, image, price, priceCurrency } from the
li[class*="ui-search-layout__item"] cards — title from [class*="poly-component__title"],
url from a[href*="/MLM-"] (cleaned of query params), image from img src,
price from [class*="price__fraction"] text.
```

## 5. Notes

- MercadoLibre product pages go through a micro-landing redirect; always wait at least 5–6 seconds after navigation.
- Tool arguments are camelCase (`sessionId`, `proxyCountry`); `browser_close` rejects snake_case.
- Use `proxyCountry: MX` for `.com.mx` results, `AR` for `.com.ar`, etc.
- Sample payloads are in [`results/`](results/).
