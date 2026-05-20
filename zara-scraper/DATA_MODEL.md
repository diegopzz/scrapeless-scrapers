# Zara data model

Two surfaces:

- `scrape_product(urls)` → list of `Product` (one per PDP URL)
- `scrape_search(url, max_pages)` → list of `SearchResult` (one per PLP card)

## Product

Lifted from the `application/ld+json` `Product` block on the Zara PDP; falls back to `og:` / Schema.org meta tags. Zara's id is the numeric product id from `-p<digits>.html`.

| Field         | Type            | Required | Notes                                                                |
| ------------- | --------------- | -------- | -------------------------------------------------------------------- |
| id            | string          | yes      | Product id from `-p<digits>.html` or JSON-LD `sku`                   |
| url           | string          | yes      | Original PDP URL                                                     |
| name          | string          | yes      | Product display name                                                 |
| brand         | string          | yes      | Usually `"ZARA"`                                                     |
| description   | string          | no       | Marketing description                                                |
| price         | number          | no       | Current selling price                                                |
| priceCurrency | string          | no       | ISO 4217 code (e.g. `"USD"`)                                         |
| availability  | string          | no       | Schema.org availability, last segment only                           |
| images        | array           | yes      | Image URLs from JSON-LD `image` or `og:image`                        |
| color         | string          | no       | Color label                                                          |
| category      | string          | no       | JSON-LD `category` when present                                      |

## SearchResult

Per-card result from the PLP's `application/ld+json` `ItemList`, with a DOM fallback that scans anchors matching `-p<digits>.html`.

| Field         | Type   | Required | Notes                                            |
| ------------- | ------ | -------- | ------------------------------------------------ |
| id            | string | yes      | Product id (digits)                              |
| url           | string | yes      | Absolute PDP URL                                 |
| name          | string | yes      | Product display name                             |
| image         | string | no       | Card thumbnail URL                               |
| price         | number | no       | Card price                                       |
| priceCurrency | string | no       | ISO 4217 code                                    |
