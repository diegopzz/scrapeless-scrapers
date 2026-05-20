# Lazada data model

Two object kinds are emitted from this scraper.

- `scrape_product(product_url)` returns a single `Product`
- `scrape_search(query, max_pages)` returns a list of `SearchResult`

Fixtures live under [`results/`](results/) and are validated against the tables
below by [`tools/verify-fixtures.py`](../tools/verify-fixtures.py).

## Product

Lifted from a Lazada listing page (e.g. `https://www.lazada.sg/products/...`).
Lazada renders the bulk of product fields into an inline `window.__moduleData__`
JSON blob; we read both that blob and the rendered DOM as fallbacks.

| Field           | Type            | Required | Notes                                                                  |
| --------------- | --------------- | -------- | ---------------------------------------------------------------------- |
| id              | string          | yes      | Product id parsed from URL path (`-i<id>` or `-s<id>`)                 |
| url             | string          | yes      | Canonical product URL                                                  |
| title           | string          | yes      | Product title                                                          |
| brand           | string \| null  | no       | Brand display string                                                   |
| price           | string \| null  | no       | Current price display string                                           |
| originalPrice   | string \| null  | no       | Pre-discount price string                                              |
| discount        | string \| null  | no       | Discount display (e.g. `"-30%"`)                                       |
| currency        | string \| null  | no       | Currency code or symbol                                                |
| rating          | number \| null  | no       | Aggregate rating (float, 0-5)                                          |
| reviews         | number \| null  | no       | Total review count                                                     |
| images          | string[]        | yes      | Image URLs harvested from the gallery / og:image                       |
| seller          | string \| null  | no       | Seller / shop name                                                     |
| sellerUrl       | string \| null  | no       | Seller storefront URL                                                  |
| availability    | string \| null  | no       | Stock state string when surfaced                                       |
| description     | string \| null  | no       | Meta description                                                       |
| categories      | string[]        | yes      | Breadcrumb category trail                                              |

## SearchResult

Each card on `https://www.lazada.sg/catalog/?q=...`.

| Field        | Type            | Required | Notes                                                       |
| ------------ | --------------- | -------- | ----------------------------------------------------------- |
| id           | string          | yes      | Item id parsed from the card's link                         |
| title        | string          | yes      | Card title                                                  |
| url          | string          | yes      | Absolute card URL                                           |
| image        | string \| null  | no       | Card thumbnail URL                                          |
| price        | string \| null  | no       | Card price display                                          |
| originalPrice| string \| null  | no       | Pre-discount price display                                  |
| discount     | string \| null  | no       | Discount display string                                     |
| rating       | number \| null  | no       | Star rating (float)                                         |
| reviews      | number \| null  | no       | Review count                                                |
| location     | string \| null  | no       | Card location text                                          |
