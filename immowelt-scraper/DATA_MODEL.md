# Immowelt data model

Single source of truth for the Python (cerberus) and Node (zod) schemas under [`python/`](python/) and [`nodejs/`](nodejs/). The Scrapeless implementation mirrors the field names emitted by  verbatim.

Immowelt.de is a German real estate portal. Two surfaces, both extracting embedded Next.js / UFRN bootstrap state.

## SearchResult

Returned per-item by `scrape_search(url, max_scrape_pages)` — entries from `pageProps.classifiedsData` (LZ-String + Base64 decoded). The shape is upstream-defined; common keys include `id`, `title`, `prices`, `attributes`, `pictures`, `address`, etc. Treat the per-item dict as opaque JSON keyed off Immowelt's internal API.

| Field | Type   | Required | Notes                                            |
| ----- | ------ | -------- | ------------------------------------------------ |
| ...   | ...    | ...      | All keys from one entry of `classifiedsData`     |

## PropertyResult

Returned per-item by `scrape_properties(urls)` — filtered subset of the `__UFRN_LIFECYCLE_SERVERREQUEST__` payload (the upstream reference's `sections`, `id`, `brand`, `tags`, `contactSections` keys).

| Field            | Type   | Required | Notes                                                                              |
| ---------------- | ------ | -------- | ---------------------------------------------------------------------------------- |
| sections         | object | yes      | Detail page sections keyed by section id (description, specs, etc.)                |
| id               | string | yes      | Listing ID                                                                         |
| brand            | string | no       | Listing brand identifier                                                           |
| tags             | object | no       | Listing tags keyed by tag id                                                       |
| contactSections  | object | no       | Agency / contact info                                                              |
