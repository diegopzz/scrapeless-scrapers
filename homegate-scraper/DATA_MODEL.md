# Homegate data model

Single source of truth for the Python (cerberus) and Node (zod) schemas under [`python/`](python/) and [`nodejs/`](nodejs/). The Scrapeless implementation mirrors the field names emitted by  verbatim.

Homegate.ch is a Swiss real estate portal. Both extraction paths read embedded bootstrap state — the upstream reference returns the nested objects raw, so Scrapeless mirrors them. Treat the inner shape as opaque JSON keyed off Homegate's internal API.

## Listing

Returned per-item by `scrape_properties(urls)` — the contents of `data["listing"]["listing"]` from the `window.__PINIA_INITIAL_STATE__` payload. Top-level keys typically include:

| Field             | Type            | Required | Notes                                              |
| ----------------- | --------------- | -------- | -------------------------------------------------- |
| id                | integer/string  | yes      | Homegate listing ID                                |
| address           | object          | no       | Nested address                                     |
| characteristics   | object          | no       | Rooms, surface, floor                              |
| prices            | object          | no       | Rent/buy components                                |
| descriptions      | object          | no       | Per-locale text                                    |
| ...               | ...             | ...      | All other keys from `state.listing.listing`        |

## SearchResultEntry

Returned per-item by `scrape_search(url, scrape_all_pages, max_scrape_pages)` — entries from `state.resultList.search.fullSearch.result.listings` extracted from `window.__INITIAL_STATE__`.

| Field   | Type   | Required | Notes                                            |
| ------- | ------ | -------- | ------------------------------------------------ |
| listing | object | yes      | The listing summary object                       |
| ...     | ...    | ...      | Any sibling keys from the result-list payload    |
