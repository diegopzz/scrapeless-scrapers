# SimilarWeb scraper

[similarweb.com](https://similarweb.com/) scraper powered by [Scrapeless](https://www.scrapeless.com/). Every surface drives a Scrapeless cloud [Scraping Browser](https://www.scrapeless.com/en/scraping-browser) and emits identical JSON shapes — see [`DATA_MODEL.md`](DATA_MODEL.md).

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
| `scrape_website` | `scrapeWebsite` |
| `scrape_website_compare` | `scrapeWebsiteCompare` |
| `scrape_sitemaps` | `scrapeSitemaps` |
| `scrape_trendings` | `scrapeTrendings` |

## Run

```bash
export SCRAPELESS_API_KEY=sk_...

# Python
cd browser/python && SAVE_TEST_RESULTS=true python run.py

# Node.js
cd browser/nodejs && SAVE_TEST_RESULTS=true node run.mjs

# CLI — copy the step-by-step commands from browser/cli/README.md
```

## Fixtures

- [`browser/nodejs/results/website.json`](browser/nodejs/results/website.json)
