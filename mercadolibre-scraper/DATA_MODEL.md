# MercadoLibre data model

Two object kinds are emitted:

- `product.json` → single `Product`, parsed from the schema.org `ld+json` Product blob on `articulo.mercadolibre.com.mx/MLM-<id>` detail pages.
- `search.json` → array of `SearchResult` objects parsed from listing cards on `listado.mercadolibre.com.mx/<query>` pages.

## Product

| Field         | Type    | Required | Notes                                                                         |
| ------------- | ------- | -------- | ----------------------------------------------------------------------------- |
| id            | string  | yes      | MercadoLibre item ID (e.g. `MLM4493249540`) from `ld+json` `sku`             |
| name          | string  | yes      | `ld+json` `name`                                                              |
| brand         | string  | no       | `ld+json` `brand` (string value)                                              |
| description   | string  | no       | `ld+json` `description` (may be empty on some listings)                      |
| image         | string  | no       | First image URL from `ld+json` `image`                                        |
| price         | number  | no       | Numeric offer price from `ld+json` `offers.price`                             |
| priceCurrency | string  | no       | ISO currency code from `ld+json` `offers.priceCurrency` (e.g. `MXN`)        |
| availability  | string  | no       | Schema.org availability URL from `ld+json` `offers.availability`              |
| ratingValue   | number  | no       | `ld+json` `aggregateRating.ratingValue`                                       |
| reviewCount   | number  | no       | `ld+json` `aggregateRating.reviewCount`                                       |
| url           | string  | yes      | Canonical product URL                                                         |
| breadcrumb    | array   | yes      | List of `{name, url, position}` from the BreadcrumbList `ld+json`             |

## SearchResult

| Field  | Type   | Required | Notes                                                                              |
| ------ | ------ | -------- | ---------------------------------------------------------------------------------- |
| id     | string | no       | MLM item ID extracted from the product URL                                         |
| name   | string | yes      | Product title from the listing card `[class*="poly-component__title"]`             |
| url    | string | no       | Absolute product URL (cleaned of tracking params)                                  |
| image  | string | no       | Thumbnail image `src` from the card `img` element                                  |
| price  | number | no       | Numeric price parsed from `[class*="price__fraction"]` text                        |
| priceCurrency | string | no | Always `MXN` for `.com.mx` results                                           |
