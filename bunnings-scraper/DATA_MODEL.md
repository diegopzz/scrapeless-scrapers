# Bunnings data model

Two object kinds are emitted:

- `product.json` → single `Product` parsed from the schema.org `ld+json` Product blob plus the breadcrumb `ld+json`.
- `search.json` → list of `SearchResult` parsed from the rendered Coveo result tiles (`[data-testid="productTileContainer"]`).

## Product

| Field        | Type    | Required | Notes                                                                |
| ------------ | ------- | -------- | -------------------------------------------------------------------- |
| sku          | string  | yes      | Bunnings SKU, e.g. `0299323` (also the `pXXXXXXX` URL slug)          |
| name         | string  | yes      | `ld+json` `name`                                                     |
| brand        | string  | no       | `ld+json` `brand.name`                                               |
| brandLogo    | string  | no       | `ld+json` `brand.logo`                                               |
| description  | string  | no       | `ld+json` `description`                                              |
| category     | string  | no       | `ld+json` `category` (top-level Bunnings category)                   |
| image        | string  | no       | `ld+json` `image`                                                    |
| price        | string  | no       | Offer price as string (e.g. `"89.98"`)                               |
| priceCurrency| string  | no       | Offer currency code, normally `"AUD"`                                |
| url          | string  | yes      | Canonical product URL                                                |
| warranty     | string  | no       | From `additionalProperty.WarrantyInfo` when present                  |
| breadcrumb   | array   | yes      | List of `{name, url, position}` from the BreadcrumbList `ld+json`    |

## SearchResult

| Field   | Type    | Required | Notes                                                  |
| ------- | ------- | -------- | ------------------------------------------------------ |
| sku     | string  | yes      | Extracted from the tile `href` (`_p<sku>` suffix)      |
| title   | string  | yes      | Product title                                          |
| url     | string  | yes      | Absolute product URL                                   |
| price   | string  | no       | Display price string (e.g. `"$89.98"`)                 |
| image   | string  | no       | Tile image URL                                         |
| rating  | string  | no       | Aria-label rating text (e.g. `"Rating: 4.33 out of 5 stars"`) |
