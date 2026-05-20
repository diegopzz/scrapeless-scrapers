# Trivago data model

Single source of truth for the Python (cerberus) and Node (zod) schemas under [`python/`](python/) and [`nodejs/`](nodejs/).

Trivago renders its accommodation list into a `<script type="application/ld+json">` `ItemList` block as well as into `[data-testid="accommodation-list-element"]` DOM cards. The scraper parses the JSON-LD block (server-side rendered, no JS-only fields) and falls back to the DOM when needed.

## SearchResult

Returned by `scrape_search(destination_url, max_pages)` — one element per `ItemList.itemListElement[].item` of `@type: Hotel`.

| Field           | Type             | Required | Notes                                              |
| --------------- | ---------------- | -------- | -------------------------------------------------- |
| position        | integer          | yes      | 1-indexed position in the result list              |
| name            | string           | yes      | Hotel name                                         |
| url             | string           | yes      | Trivago detail/redirect URL                        |
| address         | string \| null   | no       | Short address / distance string (e.g. `"1.2 mi"`)  |
| image           | string \| null   | no       | Primary image URL                                  |
| description     | string \| null   | no       | Description text (often blank on Trivago JSON-LD)  |
| priceRange      | string \| null   | no       | Price range from JSON-LD (often blank)             |
| ratingValue     | number \| null   | no       | `aggregateRating.ratingValue` (0-10 scale)         |
| reviewCount     | integer \| null  | no       | `aggregateRating.reviewCount`                      |
| bestRating      | number \| null   | no       | `aggregateRating.bestRating` (usually 10)          |
| worstRating     | number \| null   | no       | `aggregateRating.worstRating`                      |

## Destination

Returned by `scrape_destination(destination_url)` — one object summarising the destination page (FAQ + breadcrumb context that Trivago renders alongside the result list).

| Field          | Type                          | Required | Notes                                                 |
| -------------- | ----------------------------- | -------- | ----------------------------------------------------- |
| url            | string                        | yes      | Canonical destination URL                             |
| name           | string                        | yes      | Destination display name (from breadcrumb / title)    |
| breadcrumbs    | array                         | yes      | Crumb labels in display order                         |
| totalHotels    | integer \| null               | no       | Result count when present                             |
| faq            | array                         | yes      | List of `{question, answer}` items from JSON-LD FAQ   |
| topHotels      | array                         | yes      | Top hotels from JSON-LD ItemList (mirrors SearchResult)|
