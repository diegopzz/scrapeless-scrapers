# Grok scraper

[grok.com](https://grok.com/) scraper powered by [Scrapeless](https://www.scrapeless.com/). Every surface drives a Scrapeless cloud [Scraping Browser](https://www.scrapeless.com/en/scraping-browser) and emits identical JSON shapes — see [`DATA_MODEL.md`](DATA_MODEL.md).

Grok is xAI's AI assistant. Conversation sessions require login, but **shared conversations** at `grok.com/share/<id>` are publicly readable — they render the full message log without authentication. This scraper targets that public surface.

## Status

**VERIFIED** — `grok.com/share/<id>` shared conversation pages load and return the full conversation transcript without authentication. Live results are in [`browser/nodejs/results/`](browser/nodejs/results/) and [`browser/python/results/`](browser/python/results/).

Stable anchors: `data-testid="user-message"` and `data-testid="assistant-message"` elements; page title follows the pattern `{topic} | Shared Grok Conversation`; `<meta name="description">` holds the first user prompt snippet.

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
| `scrape_share` | `scrapeShare` |

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

- [`browser/nodejs/results/share.json`](browser/nodejs/results/share.json)
- [`browser/python/results/share.json`](browser/python/results/share.json)
