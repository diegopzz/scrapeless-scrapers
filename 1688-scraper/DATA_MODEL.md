# 1688 data model

Two object kinds are emitted from this scraper.

- `scrape_product(product_id)` / `scrapeProduct(productId)` returns a single `Product`
- `scrape_search(query, max_pages)` / `scrapeSearch(query, maxPages)` returns a list of `SearchResult`

Fixtures live under [`results/`](results/) and are validated against the tables
below by [`tools/verify-fixtures.py`](../tools/verify-fixtures.py).

## Product

Lifted from the offer detail page at `https://detail.1688.com/offer/{id}.html`.

| Field           | Type            | Required | Notes                                                                  |
| --------------- | --------------- | -------- | ---------------------------------------------------------------------- |
| id              | string          | yes      | Offer / product id from URL                                            |
| url             | string          | yes      | Canonical detail URL                                                   |
| title           | string          | yes      | Offer title                                                            |
| price           | string \| null  | no       | First displayed price string (CNY)                                     |
| priceRange      | string \| null  | no       | Range string when the offer has volume-tier pricing                    |
| moq             | string \| null  | no       | Minimum order quantity display string (e.g. `"2 件"`)                  |
| images          | string[]        | yes      | Image URLs harvested from the gallery and JSON-LD                      |
| seller          | string \| null  | no       | Supplier company name                                                  |
| sellerUrl       | string \| null  | no       | Supplier storefront URL                                                |
| location        | string \| null  | no       | Supplier province / city string                                        |
| description     | string \| null  | no       | Short description / keywords meta                                      |
| categories      | string[]        | yes      | Breadcrumb category trail                                              |

## SearchResult

Each card on `s.1688.com/selloffer/offer_search.htm?keywords=...`.

| Field        | Type            | Required | Notes                                                       |
| ------------ | --------------- | -------- | ----------------------------------------------------------- |
| id           | string          | yes      | Offer id parsed from the card's link                        |
| title        | string          | yes      | Card title                                                  |
| url          | string          | yes      | Absolute card URL                                           |
| image        | string \| null  | no       | Card thumbnail URL                                          |
| price        | string \| null  | no       | Displayed price string                                      |
| moq          | string \| null  | no       | Minimum-order-quantity display string                       |
| seller       | string \| null  | no       | Supplier short name                                         |
| location     | string \| null  | no       | Supplier location                                           |
