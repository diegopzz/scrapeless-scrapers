# Google data model

Single source of truth for the Python (cerberus) and Node (zod) schemas under [`python/`](python/) and [`nodejs/`](nodejs/). Mirrors field names from  verbatim.

This site uses **two** Scrapeless surfaces:

- `client.deepserp.scrape({ actor: "scraper.google.search", ... })` for `scrape_serp` and `scrape_keywords` (no anti-bot worry).
- `client.browser.create(...)` + Playwright/Puppeteer for `scrape_google_map_places` (Maps requires a real browser to render the place panel).

## SerpResult — emitted by `scrape_serp`

| Field       | Type   | Required | Notes                                                   |
| ----------- | ------ | -------- | ------------------------------------------------------- |
| position    | int    | yes      | 1-indexed global position across all paginated results  |
| title       | string | yes      | Headline of the organic result                          |
| url         | string | yes      | Destination URL                                         |
| origin      | string | no       | Source label rendered in the cite block                 |
| domain      | string | yes      | Hostname stripped of scheme + leading `www.`            |
| description | string | no       | Snippet text                                            |
| date        | string | no       | Date stamp rendered next to the snippet, when present   |

## Keywords — emitted by `scrape_keywords`

| Field          | Type     | Required | Notes                                                                    |
| -------------- | -------- | -------- | ------------------------------------------------------------------------ |
| related_search | string[] | yes      | "Searches related to …" suggestions                                      |
| people_ask_for | string[] | yes      | "People also ask" question texts                                         |

## Place — emitted by `scrape_google_map_places` (one per URL)

| Field        | Type   | Required | Notes                                                          |
| ------------ | ------ | -------- | -------------------------------------------------------------- |
| name         | string | yes      | `h1` text on the place panel                                   |
| category     | string | no       | Primary category button label                                  |
| address      | string | no       | From `aria-label` starting with `Address:`                     |
| website      | string | no       | From `aria-label` starting with `Website:`                     |
| phone        | string | no       | From `aria-label` starting with `Phone:`                       |
| review_count | string | no       | From `aria-label` containing ` reviews`                        |
| stars        | string | no       | From `aria-label` containing ` stars`                          |
| 5_stars      | string | no       | Review count for the 5-star bucket                             |
| 4_stars      | string | no       | Review count for the 4-star bucket                             |
| 3_stars      | string | no       | Review count for the 3-star bucket                             |
| 2_stars      | string | no       | Review count for the 2-star bucket                             |
| 1_stars      | string | no       | Review count for the 1-star bucket                             |
