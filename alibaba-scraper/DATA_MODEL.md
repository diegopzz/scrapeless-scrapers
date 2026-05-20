# Alibaba data model

Two object kinds are emitted from this scraper.

- `scrape_product(product_url)` returns a single `Product`
- `scrape_search(query, max_pages)` returns a list of `SearchResult`

Fixtures live under [`results/`](results/) and are validated against the tables
below by [`tools/verify-fixtures.py`](../tools/verify-fixtures.py).

## Product

Lifted from a global B2B product page on `alibaba.com`.

| Field           | Type            | Required | Notes                                                                  |
| --------------- | --------------- | -------- | ---------------------------------------------------------------------- |
| id              | string          | yes      | Product id parsed from the URL                                         |
| url             | string          | yes      | Canonical product URL                                                  |
| title           | string          | yes      | Product title                                                          |
| price           | string \| null  | no       | First displayed price string (USD by default)                          |
| priceRange      | string \| null  | no       | Range string when tiered pricing exists                                |
| moq             | string \| null  | no       | Minimum order quantity display string                                  |
| images          | string[]        | yes      | Image URLs harvested from the gallery / og:image                       |
| supplier        | string \| null  | no       | Supplier company name                                                  |
| supplierUrl     | string \| null  | no       | Supplier storefront URL                                                |
| supplierYears   | string \| null  | no       | Verified-years display string                                          |
| location        | string \| null  | no       | Supplier country / region                                              |
| rating          | string \| null  | no       | Supplier or product star rating display string                         |
| description     | string \| null  | no       | Meta description                                                       |
| categories      | string[]        | yes      | Breadcrumb category trail                                              |

## SearchResult

Each card on `https://www.alibaba.com/trade/search?SearchText=...`.

| Field        | Type            | Required | Notes                                                       |
| ------------ | --------------- | -------- | ----------------------------------------------------------- |
| id           | string          | yes      | Product id parsed from the card's link                      |
| title        | string          | yes      | Card title                                                  |
| url          | string          | yes      | Absolute card URL                                           |
| image        | string \| null  | no       | Card thumbnail URL                                          |
| price        | string \| null  | no       | Displayed price string                                      |
| moq          | string \| null  | no       | Minimum-order-quantity display string                       |
| supplier     | string \| null  | no       | Supplier company short name                                 |
| location     | string \| null  | no       | Supplier country / region                                   |
