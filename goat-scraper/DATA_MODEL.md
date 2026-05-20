# Goat data model

Two surfaces:

- `scrape_products(urls)` → list of `Product` (lifted from `__NEXT_DATA__.props.pageProps.productTemplate`, with `offers` attached)
- `scrape_search(query, max_pages)` → list of `SearchResult` (lifted from goat.com's `/web-api/consumer-search/get-product-search-results`)

## Product

| Field                    | Type    | Required | Notes                                          |
| ------------------------ | ------- | -------- | ---------------------------------------------- |
| id                       | integer | yes      |                                                |
| name                     | string  | yes      |                                                |
| brandName                | string  | yes      |                                                |
| color                    | string  | no       |                                                |
| designer                 | string  | no       |                                                |
| details                  | string  | no       |                                                |
| forAuction               | boolean \| null | no |                                              |
| internalShot             | string  | no       |                                                |
| maximumOfferCents        | integer | no       |                                                |
| midsole                  | string  | no       |                                                |
| minimumOfferCents        | integer | no       |                                                |
| productCategory          | string  | no       |                                                |
| productType              | string  | no       |                                                |
| silhouette               | string  | no       |                                                |
| sizeBrand                | string  | no       |                                                |
| sizeRange                | list    | no       | list of float                                  |
| sku                      | string  | yes      |                                                |
| slug                     | string  | yes      |                                                |
| specialDisplayPriceCents | integer | no       |                                                |
| specialType              | string  | no       |                                                |
| status                   | string  | no       |                                                |
| upperMaterial            | string  | no       |                                                |
| offers                   | any \| null | no   | `pageProps.offers.offerData` when present       |

## SearchResult

| Field                       | Type            | Required | Notes                                                                                     |
| --------------------------- | --------------- | -------- | ----------------------------------------------------------------------------------------- |
| id                          | string          | yes      |                                                                                           |
| status                      | string          | no       |                                                                                           |
| slug                        | string          | no       |                                                                                           |
| title                       | string          | no       |                                                                                           |
| pictureUrl                  | string          | no       |                                                                                           |
| inStock                     | boolean         | no       |                                                                                           |
| category                    | string          | no       |                                                                                           |
| productType                 | string          | no       |                                                                                           |
| brandName                   | string          | no       |                                                                                           |
| gender                      | string          | no       |                                                                                           |
| releaseDate                 | dict \| null    | no       | `{seconds, nanos}`                                                                        |
| localizedRetailPriceCents   | dict \| null    | no       | `{amountCents, currency}`                                                                 |
| variantsList                | list            | no       | Each item: `{productCondition, boxCondition, size: {gender, sizeUnit, size, displayName}, localizedLowestPriceCents: {amountCents, currency}}` |
