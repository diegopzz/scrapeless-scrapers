# SeLoger data model

Single source of truth for the Python (cerberus) and Node (zod) schemas under [`python/`](python/) and [`nodejs/`](nodejs/). The Scrapeless implementation mirrors the field names emitted by  verbatim.

SeLoger is a French real estate portal. Two surfaces: search-results cards (DOM-extracted) and property detail (embedded JSON from `window.__UFRN_LIFECYCLE_SERVERREQUEST__`).

## SearchResult

Returned by `scrape_search(url, max_pages)` — one per card on the search page.

| Field          | Type             | Required | Notes                                                |
| -------------- | ---------------- | -------- | ---------------------------------------------------- |
| title          | string           | yes      | Card title from `card-mfe-covering-link-testid`      |
| url            | string           | yes      | Absolute property detail URL                         |
| images         | array of strings | yes      | Card carousel image URLs                             |
| price          | string           | yes      | Display string (e.g. `"245 000 EUR"`)                |
| price_per_m2   | string \| null   | no       | Price per square metre                                |
| property_facts | array of strings | yes      | Bullet facts (rooms, surface, etc.)                  |
| address        | string           | yes      | Full address text                                    |
| agency         | string \| null   | no       | Listing agency name                                  |

## PropertyResult

Returned by `scrape_property(urls)` — the decoded `classified` object from the page's bootstrap state. The the upstream reference scraper returns the raw nested dict — Scrapeless mirrors it; downstream consumers should treat the object as opaque JSON.

| Field      | Type   | Required | Notes                                                    |
| ---------- | ------ | -------- | -------------------------------------------------------- |
| classified | object | yes      | The `app_cldp.data.classified` blob from the page state  |
