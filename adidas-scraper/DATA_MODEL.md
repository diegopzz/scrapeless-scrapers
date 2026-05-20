# Adidas data model

Two surfaces:

- `scrape_product(urls)` → list of `Product` (one per PDP URL)
- `scrape_search(url, max_pages)` → list of `SearchResult` (one per PLP card)

`product.json` is a list of `Product` objects, `search.json` is a list of `SearchResult` objects.

## Product

Lifted from the `application/ld+json` `Product` block on the adidas.com PDP, plus a DOM fallback for `name` / `description` / `images` when JSON-LD is partial. Adidas's id format is the 4–6 char article number (`B75806`, `IF8819`, etc.) appearing at the end of the PDP URL.

| Field         | Type            | Required | Notes                                                                       |
| ------------- | --------------- | -------- | --------------------------------------------------------------------------- |
| id            | string          | yes      | adidas article number from `/<slug>/<ID>.html` or JSON-LD `sku`             |
| url           | string          | yes      | Original PDP URL                                                            |
| name          | string          | yes      | Product display name                                                        |
| brand         | string          | yes      | Usually `"adidas"`                                                          |
| description   | string          | no       | Long-form description; falls back to `meta[name="description"]`             |
| price         | number          | no       | Current selling price (number; currency in `priceCurrency`)                 |
| priceCurrency | string          | no       | ISO 4217 code (e.g. `"USD"`)                                                |
| availability  | string          | no       | Schema.org availability, last segment only (`InStock` / `OutOfStock`)       |
| images        | array           | yes      | List of image URLs from JSON-LD `image` or `og:image`                       |
| rating        | number          | no       | `aggregateRating.ratingValue` (float)                                       |
| reviewCount   | integer         | no       | `aggregateRating.reviewCount`                                               |
| category      | string          | no       | JSON-LD `category` when present                                             |
| color         | string          | no       | JSON-LD `color` when present                                                |

## SearchResult

Per-card result extracted from the PLP's `application/ld+json` `ItemList` block, with a DOM fallback to `[data-testid="plp-product-card"]`.

| Field         | Type            | Required | Notes                                                          |
| ------------- | --------------- | -------- | -------------------------------------------------------------- |
| id            | string          | yes      | adidas article number (parsed from card URL)                   |
| url           | string          | yes      | Absolute PDP URL                                               |
| name          | string          | yes      | Product display name                                           |
| image         | string          | no       | Card thumbnail URL                                              |
| price         | number          | no       | Card price (number)                                            |
| priceCurrency | string          | no       | ISO 4217 code; `"USD"` when card price text contains `$`        |
