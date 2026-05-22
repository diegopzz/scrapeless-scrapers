# Flipkart scraper

[flipkart.com](https://www.flipkart.com/) scraper powered by [Scrapeless](https://www.scrapeless.com/). Every surface drives a Scrapeless cloud [Scraping Browser](https://www.scrapeless.com/en/scraping-browser) and emits identical JSON shapes — see [`DATA_MODEL.md`](DATA_MODEL.md).

## Surfaces

Available surfaces live under [`browser/`](browser/) — pick whichever fits your stack:

| Surface | Path | Built on |
| --- | --- | --- |
| Python | [`browser/python`](browser/python/) | official `scrapeless` SDK + Playwright over CDP |
| Node.js | [`browser/nodejs`](browser/nodejs/) | official `@scrapeless-ai/sdk` + puppeteer-core over CDP |
| CLI | [`browser/cli`](browser/cli/) | `scrapeless-scraping-browser` CLI + in-page `eval` |
| MCP | [`browser/mcp`](browser/mcp/) | Scrapeless MCP server — conversational, no code |

## Functions

| Python | Node.js |
| --- | --- |
| `scrape_product` | `scrapeProduct` |
| `scrape_search` | `scrapeSearch` |

## Run

```bash
export SCRAPELESS_API_KEY=sk_...

# Python
cd browser/python && SAVE_TEST_RESULTS=true python run.py

# Node.js
cd browser/nodejs && SAVE_TEST_RESULTS=true node run.mjs

# CLI — copy the step-by-step commands from browser/cli/README.md
```

## Notes

- Use `proxyCountry: IN` for Flipkart India pricing in INR.
- Product pages require **12 seconds** of settle time after navigation for Flipkart's JavaScript to hydrate and inject the `ld+json` Product block.
- The `ld+json` block is a top-level JSON **array** (`[{...Product...}]`), not a bare object.
- Search result cards use obfuscated CSS class names; the stable anchors are the `[data-id]` attribute on card containers and `a[href*="/p/"]` for product links.

## Fixtures

- [`browser/nodejs/results/product.json`](browser/nodejs/results/product.json)
- [`browser/nodejs/results/search.json`](browser/nodejs/results/search.json)
