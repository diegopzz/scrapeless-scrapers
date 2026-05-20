# G2 scraper

[g2.com](https://g2.com/) scraper powered by [Scrapeless](https://www.scrapeless.com/). Every surface drives a Scrapeless cloud [Scraping Browser](https://www.scrapeless.com/en/scraping-browser) and emits identical JSON shapes — see [`DATA_MODEL.md`](DATA_MODEL.md).

## Surfaces

Available surfaces live under [`browser/`](browser/) — pick whichever fits your stack:

| Surface | Path | Built on |
| --- | --- | --- |
| Python | [`browser/python`](browser/python/) | official `scrapeless` SDK + Playwright over CDP |
| Node.js | [`browser/nodejs`](browser/nodejs/) | official `@scrapeless-ai/sdk` + puppeteer-core over CDP |
| MCP | [`browser/mcp`](browser/mcp/) | Scrapeless MCP server — conversational, no code |

## Functions

| Python | Node.js |
| --- | --- |
| `scrape_search` | `scrapeSearch` |
| `scrape_reviews` | `scrapeReviews` |
| `scrape_alternatives` | `scrapeAlternatives` |

## Run

```bash
export SCRAPELESS_API_KEY=sk_...

# Python
cd browser/python && SAVE_TEST_RESULTS=true python run.py

# Node.js
cd browser/nodejs && SAVE_TEST_RESULTS=true node run.mjs

```

## Fixtures

- [`browser/nodejs/results/alternatives.json`](browser/nodejs/results/alternatives.json)
- [`browser/nodejs/results/reviews.json`](browser/nodejs/results/reviews.json)
- [`browser/nodejs/results/search.json`](browser/nodejs/results/search.json)
