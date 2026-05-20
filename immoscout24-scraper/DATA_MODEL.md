# Immoscout24 data model

Single source of truth for the Python (cerberus) and Node (zod) schemas under [`python/`](python/) and [`nodejs/`](nodejs/). The Scrapeless implementation mirrors the field names emitted by  verbatim.

Immoscout24.ch is a Swiss real estate portal. Both extraction paths read from the Vue.js `window.__PINIA_INITIAL_STATE__` bootstrap state — the upstream reference returns the nested objects raw, so Scrapeless mirrors them. Treat the inner shape as opaque JSON keyed off Immoscout24's API; only the wrapper is contracted.

## Listing

Returned per-item by `scrape_properties(urls)` — the contents of `data["listing"]["listing"]` from the page's Pinia state. Top-level keys typically include (subject to upstream change):

| Field             | Type            | Required | Notes                                              |
| ----------------- | --------------- | -------- | -------------------------------------------------- |
| id                | integer/string  | yes      | Immoscout24 listing ID                             |
| address           | object          | no       | Nested address (city, postal code, street, geo)    |
| characteristics   | object          | no       | Rooms, surface, floor, etc.                        |
| prices            | object          | no       | Gross/net rent, currency                           |
| descriptions      | object          | no       | Per-locale text                                    |
| platforms         | object          | no       | Cross-portal flags                                 |
| meta              | object          | no       | Publish/refresh timestamps                         |
| ...               | ...             | ...      | All other keys from `state.listing.listing`        |

## SearchResultEntry

Returned per-item by `scrape_search(url, scrape_all_pages, max_scrape_pages)` — entries from `state.resultList.search.fullSearch.result.listings`. Each entry typically contains:

| Field               | Type   | Required | Notes                                            |
| ------------------- | ------ | -------- | ------------------------------------------------ |
| listing             | object | no       | The listing summary object                       |
| ...                 | ...    | ...      | Any sibling keys from the result-list payload    |
