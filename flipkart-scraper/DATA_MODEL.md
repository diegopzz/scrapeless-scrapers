# Flipkart data model

Two object kinds are emitted:

- `product.json` → single `Product`, parsed from the schema.org `ld+json` Product array on `www.flipkart.com/<slug>/p/<id>` detail pages.
- `search.json` → array of `SearchResult` objects parsed from `[data-id]` cards on `www.flipkart.com/search?q=<query>` pages.

## Product

| Field         | Type    | Required | Notes                                                                                 |
| ------------- | ------- | -------- | ------------------------------------------------------------------------------------- |
| id            | string  | yes      | Flipkart product SKU (e.g. `MOBH4DQF849HCG6G`) from `ld+json` `sku`                  |
| name          | string  | yes      | `ld+json` `name`                                                                      |
| brand         | string  | no       | `ld+json` `brand.name`                                                                |
| description   | string  | no       | `ld+json` `description`                                                               |
| image         | string  | no       | First image URL from `ld+json` `image` array                                          |
| price         | number  | no       | Numeric offer price from `ld+json` `offers.price`                                     |
| priceCurrency | string  | no       | ISO currency code from `ld+json` `offers.priceCurrency` (always `INR`)                |
| availability  | string  | no       | Schema.org availability URL from `ld+json` `offers.availability`                      |
| ratingValue   | number  | no       | `ld+json` `aggregateRating.ratingValue`                                               |
| reviewCount   | number  | no       | `ld+json` `aggregateRating.reviewCount` (editorial reviews count)                     |
| url           | string  | yes      | Canonical product URL                                                                  |
| breadcrumb    | array   | yes      | Always `[]` — Flipkart does not include a BreadcrumbList in `ld+json`                 |

## SearchResult

| Field         | Type   | Required | Notes                                                                                  |
| ------------- | ------ | -------- | -------------------------------------------------------------------------------------- |
| id            | string | no       | Flipkart product SKU from the `data-id` attribute on card elements                     |
| name          | string | yes      | Product title from `.RG5Slk` or `img[alt]` fallback                                   |
| url           | string | no       | Absolute product URL from `a[href*="/p/"]`, cleaned of tracking params                 |
| image         | string | no       | Thumbnail image `src` from the card `img` element                                      |
| price         | number | no       | Numeric price from `.hZ3P6w` text (e.g. `69900`)                                      |
| priceCurrency | string | no       | Always `INR`                                                                           |
| ratingValue   | number | no       | Rating from `.MKiFS6` text (e.g. `4.6`)                                               |
