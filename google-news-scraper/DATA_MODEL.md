# GoogleNews data model

Single source of truth for the Python (cerberus) and Node (zod) schemas under [`python/`](python/) and [`nodejs/`](nodejs/).

The scraper drives `https://news.google.com/search?q=<query>&hl=en` (and topic pages of the same shape) through Scrapeless's [Scraping Browser](https://www.scrapeless.com/en/scraping-browser) and extracts the article cards rendered inside each `<article>` tag.

## Article — emitted by `scrape_news`

| Field      | Type   | Required | Notes                                                                                          |
| ---------- | ------ | -------- | ---------------------------------------------------------------------------------------------- |
| position   | int    | yes      | 1-indexed position in the result list                                                          |
| title      | string | yes      | Headline text                                                                                  |
| url        | string | yes      | Absolute Google News article URL (Google's internal `./read/CBM…` redirect resolved to `https`) |
| source     | string | no       | Publication name shown in the card                                                             |
| time       | string | no       | Relative time stamp rendered next to the source (e.g. `"3 hours ago"`)                          |
| thumbnail  | string | no       | Cover image URL when present                                                                   |
