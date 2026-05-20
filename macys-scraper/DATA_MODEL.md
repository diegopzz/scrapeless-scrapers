# Macy's data model

Two surfaces:

- `scrape_product(urls)` → list of `Product` (one per `/shop/product/...?ID=<n>` PDP URL)
- `scrape_search(category_url, max_pages)` → list of `SearchResult` (one per `/shop/...` listing card)

`product.json` is a list of `Product` objects, `search.json` is a list of `SearchResult` objects.

## Product

Macy's PDPs emit a JSON-LD `Product` block. The id is the numeric `ID=` query param. We prefer JSON-LD; fall back to DOM (`h1`, `[data-auto="product-name"]`, `meta[property="og:image"]`) when JSON-LD is absent.

| Field         | Type    | Required | Notes                                                                       |
| ------------- | ------- | -------- | --------------------------------------------------------------------------- |
| id            | string  | yes      | Numeric product ID from `ID=` query param or JSON-LD `productID`             |
| url           | string  | yes      | Canonical PDP URL                                                            |
| name          | string  | yes      | Product display name                                                         |
| brand         | string  | no       | JSON-LD `brand.name`                                                         |
| description   | string  | no       | JSON-LD `description`                                                        |
| price         | number  | no       | Current selling price from `offers.price`                                    |
| priceCurrency | string  | no       | ISO 4217 (`USD`)                                                             |
| availability  | string  | no       | Schema.org availability, last segment only (`InStock` / `OutOfStock`)        |
| images        | array   | yes      | Image URLs from JSON-LD `image` or `og:image`                                |
| rating        | number  | no       | `aggregateRating.ratingValue`                                                |
| reviewCount   | integer | no       | `aggregateRating.reviewCount`                                                |
| sku           | string  | no       | JSON-LD `sku` when distinct from the product ID                              |

## SearchResult

Per-card result from a Macy's category / search results page (`/shop/...`). PLP tiles render anchors of the form `/shop/product/...?ID=<n>`.

| Field         | Type    | Required | Notes                                                          |
| ------------- | ------- | -------- | -------------------------------------------------------------- |
| id            | string  | yes      | Numeric product ID from anchor's `ID=` query param             |
| url           | string  | yes      | Absolute PDP URL                                               |
| name          | string  | yes      | Tile title                                                     |
| brand         | string  | no       | Brand name when rendered on the card                           |
| image         | string  | no       | Tile image URL                                                 |
| price         | number  | no       | Numeric price parsed from the tile price block                 |
| priceCurrency | string  | no       | `"USD"` when the price text contains `$`                       |
