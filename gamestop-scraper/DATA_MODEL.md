# GameStop data model

Two object kinds are emitted:

- `product.json` → single `Product` parsed from the schema.org Product `ld+json` blob (plus the BreadcrumbList ld+json) on a `/video-games/.../products/<slug>/<pid>.html` page.
- `search.json` → list of `SearchResult` parsed from each `.product-tile` card on a category or search page. The card's `data-gtmdata` attribute carries the full structured payload.

## Product

| Field         | Type    | Required | Notes                                                              |
| ------------- | ------- | -------- | ------------------------------------------------------------------ |
| id            | string  | yes      | `data-pid` / canonical product ID                                  |
| name          | string  | yes      | `ld+json` Product `name`                                           |
| brand         | string  | no       | `ld+json` Product `brand`                                          |
| description   | string  | no       | `ld+json` Product `description`                                    |
| platform      | string  | no       | `ld+json` Product `gamePlatform`                                   |
| category      | string  | no       | `ld+json` Product `category`                                       |
| genre         | string  | no       | `ld+json` Product `genre`                                          |
| contentRating | string  | no       | `ld+json` Product `contentRating` (e.g. `Everyone`)                |
| producer      | string  | no       | `ld+json` Product `producer`                                       |
| publisher     | string  | no       | `ld+json` Product `publisher`                                      |
| image         | string  | no       | `ld+json` Product `image`                                          |
| url           | string  | yes      | Canonical product URL                                              |
| price         | string  | no       | First offer `price`                                                |
| priceCurrency | string  | no       | First offer `priceCurrency`                                        |
| availability  | string  | no       | First offer `availability`                                         |
| offers        | array   | yes      | Full list of `{name, sku, price, priceCurrency, availability}`     |
| breadcrumb    | array   | yes      | `BreadcrumbList` `{name, url, position}` items                     |

## SearchResult

Each tile carries a `data-gtmdata` JSON blob; we surface a normalized subset.

| Field         | Type    | Required | Notes                                                                  |
| ------------- | ------- | -------- | ---------------------------------------------------------------------- |
| id            | string  | yes      | `data-pid`                                                             |
| name          | string  | yes      | Tile `name`                                                            |
| url           | string  | yes      | Absolute product URL                                                   |
| price         | string  | no       | `price.base`                                                           |
| salePrice     | string  | no       | `price.sale`                                                           |
| platform      | string  | no       | First entry in `productPlatform` (where present)                       |
| image         | string  | no       | `image.base`                                                           |
| ratingPercent | string  | no       | `ratings.percentage`                                                   |
| ratingCount   | string  | no       | `ratings.count`                                                        |
| available     | boolean | no       | `availability.available`                                               |
| isDigital     | boolean | no       | `availability.isDigitalProduct`                                        |
