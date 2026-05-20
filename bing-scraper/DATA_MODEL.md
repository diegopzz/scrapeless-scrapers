# Bing data model

Single source of truth for the Python (cerberus) and Node (zod) schemas under [`python/`](python/) and [`nodejs/`](nodejs/). Mirrors field names from  verbatim.

Both targets render through `client.browser.create(...)` + Playwright/Puppeteer over CDP against `https://www.bing.com/search?q=…`. Bing does not currently have a dedicated Scrapeless Deep SerpApi actor, so the browser pattern is the supported path.

## SearchResult — emitted by `scrape_search`

| Field       | Type   | Required | Notes                                                       |
| ----------- | ------ | -------- | ----------------------------------------------------------- |
| position    | int    | yes      | 1-indexed global position across all paginated results      |
| title       | string | yes      | Headline of the organic result                              |
| url         | string | yes      | Destination URL                                             |
| origin      | string | no       | Source label rendered in the cite block                     |
| domain      | string | yes      | Hostname stripped of scheme + leading `www.`                |
| description | string | no       | Snippet text                                                |
| date        | string | no       | Date stamp rendered next to the snippet, when present       |

## Keywords — emitted by `scrape_keywords`

Returns `string[]` — the related-keyword suggestions Bing surfaces in the `b_ans` answer block.
