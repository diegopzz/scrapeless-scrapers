# Redbubble data model

Two surfaces:

- `scrape_product(urls)` → list of `Product` (one per `/i/<medium>/.../<workId>/<token>` PDP URL)
- `scrape_search(query, max_pages)` → list of `SearchResult` (one per `/shop/<query>` card)

`product.json` is a list of `Product` objects, `search.json` is a list of `SearchResult` objects.

## Product

Lifted from the `application/ld+json` `Product` block on the PDP, with extras pulled from the page's `__NEXT_DATA__` (`pageProps.initialInventoryItem` + `pageProps.reviewSummary`). The Redbubble id format is the numeric `workId` from the URL (`/i/<medium>/.../<workId>/<token>`).

| Field         | Type    | Required | Notes                                                                       |
| ------------- | ------- | -------- | --------------------------------------------------------------------------- |
| id            | string  | yes      | Numeric workId parsed from `/i/<medium>/<slug>/<workId>/<token>`            |
| url           | string  | yes      | Original PDP URL                                                            |
| name          | string  | yes      | Product display name from JSON-LD `name`                                    |
| description   | string  | no       | JSON-LD `description` (medium-specific blurb)                                |
| medium        | string  | no       | Slug from PDP URL after `/i/` (e.g. `sticker`, `t-shirt`, `mug`)            |
| artist        | string  | no       | Artist username from PDP URL (`-by-<artist>` segment)                       |
| price         | number  | no       | Numeric price from JSON-LD `offers.price`                                    |
| priceCurrency | string  | no       | ISO 4217 code from `offers.priceCurrency`                                    |
| availability  | string  | no       | Schema.org availability, last segment only (`InStock` / `OutOfStock`)       |
| images        | array   | yes      | List of preview image URLs from JSON-LD `image`                              |
| rating        | number  | no       | `aggregateRating.ratingValue` or `reviewSummary.rating`                      |
| reviewCount   | integer | no       | `aggregateRating.ratingCount` or `reviewSummary.count`                       |

## SearchResult

Per-card result extracted from the search page's `__NEXT_DATA__` (`pageProps.results[].inventoryItem`), with a DOM fallback to anchor + price selectors. The `id` is the numeric `workId`.

| Field         | Type    | Required | Notes                                                          |
| ------------- | ------- | -------- | -------------------------------------------------------------- |
| id            | string  | yes      | Numeric workId (matches the PDP id)                            |
| url           | string  | yes      | Absolute PDP URL                                               |
| name          | string  | yes      | Work title from `inventoryItem.work.title`                     |
| artist        | string  | no       | Artist username                                                 |
| medium        | string  | no       | Product slug (e.g. `sticker`, `t-shirt`, `mug`)                |
| image         | string  | no       | Preview image URL                                              |
| price         | number  | no       | Numeric price                                                  |
| priceCurrency | string  | no       | ISO 4217 code; `"USD"` for US locale                            |
