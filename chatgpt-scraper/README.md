# ChatGPT scraper

[chatgpt.com](https://chatgpt.com/) scraper powered by [Scrapeless](https://www.scrapeless.com/). Every surface drives a Scrapeless cloud [Scraping Browser](https://www.scrapeless.com/en/scraping-browser) and emits identical JSON shapes — see [`DATA_MODEL.md`](DATA_MODEL.md).

## Surfaces

Available surfaces live under [`browser/`](browser/) — pick whichever fits your stack:

| Surface | Path | Built on |
| --- | --- | --- |
| Python | [`browser/python`](browser/python/) | official `scrapeless` SDK + Playwright over CDP |
| Node.js | [`browser/nodejs`](browser/nodejs/) | official `@scrapeless-ai/sdk` + puppeteer-core over CDP |

The `cli/` surface covers single-turn `conversation` by reading the rendered DOM; the SSE-backed multi-turn `conversations` flow needs the `nodejs/` or `python/` surfaces — see [`browser/cli/README.md`](browser/cli/README.md).

## Functions

| Python | Node.js |
| --- | --- |
| `scrape_conversation` | `scrapeConversation` |
| `scrape_conversations` | `scrapeConversations` |

## Run

```bash
export SCRAPELESS_API_KEY=sk_...

# Python
cd browser/python && SAVE_TEST_RESULTS=true python run.py

# Node.js
cd browser/nodejs && SAVE_TEST_RESULTS=true node run.mjs

```

## Fixtures

- [`browser/nodejs/results/conversation.md`](browser/nodejs/results/conversation.md)
- [`browser/nodejs/results/conversations.json`](browser/nodejs/results/conversations.json)
