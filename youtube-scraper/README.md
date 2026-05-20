# YouTube scraper

[youtube.com](https://youtube.com/) scraper powered by [Scrapeless](https://www.scrapeless.com/). Every surface drives a Scrapeless cloud [Scraping Browser](https://www.scrapeless.com/en/scraping-browser) and emits identical JSON shapes — see [`DATA_MODEL.md`](DATA_MODEL.md).

## Surfaces

Available surfaces live under [`browser/`](browser/) — pick whichever fits your stack:

| Surface | Path | Built on |
| --- | --- | --- |
| Python | [`browser/python`](browser/python/) | official `scrapeless` SDK + Playwright over CDP |
| Node.js | [`browser/nodejs`](browser/nodejs/) | official `@scrapeless-ai/sdk` + puppeteer-core over CDP |
| CLI | [`browser/cli`](browser/cli/) | `scrapeless-scraping-browser` CLI + in-page `eval` |
| MCP | [`browser/mcp`](browser/mcp/) | Scrapeless MCP server — conversational, no code |

The CLI surface covers `video`; `comments`, `channel`, `channel_videos`, `search`, and `shorts` use YouTube's internal `youtubei/v1` endpoints and are available on the `nodejs/` and `python/` surfaces.

## Functions

| Python | Node.js |
| --- | --- |
| `scrape_video` | `scrapeVideo` |
| `scrape_comments` | `scrapeComments` |
| `scrape_channel` | `scrapeChannel` |
| `scrape_channel_videos` | `scrapeChannelVideos` |
| `scrape_search` | `scrapeSearch` |
| `scrape_shorts` | `scrapeShorts` |

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

- [`browser/nodejs/results/video.json`](browser/nodejs/results/video.json)
