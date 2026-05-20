# eBay data model

Two object kinds are emitted:

- `search.json` → list of `SearchResult`
- `product.json` → single `Product` object (with optional `variants` list)

## SearchResult

| Field        | Type    | Required | Notes                                                |
| ------------ | ------- | -------- | ---------------------------------------------------- |
| url          | string  | yes      | Canonical listing URL (`?…` stripped)                |
| title        | string  | no       | `.s-card__title span` text                           |
| price        | string  | no       | `.s-card__price` / `.s-item__price` text             |
| shipping     | string  | no       | Delivery line containing `delivery`                  |
| location     | string  | no       | Text after `Located in `                             |
| subtitles    | string  | no       | `.s-card__subtitle span` text                        |
| photo        | string  | no       | `<img data-src>` or `<img src>`                      |
| rating       | string  | no       | Percentage string like `"95%"`                       |
| rating_count | number  | no       | Integer count of feedback                            |

## Product

| Field             | Type    | Required | Notes                                                          |
| ----------------- | ------- | -------- | -------------------------------------------------------------- |
| url               | string  | yes      | `<link rel="canonical">`                                       |
| id                | string  | yes      | Item ID extracted from `/itm/<id>` portion of URL              |
| price_original    | string  | no       | `.x-price-primary > span` text                                 |
| price_converted   | string  | no       | `.x-price-approx__price` text (region currency conversion)     |
| name              | string  | no       | `<h1> span` text                                               |
| seller_name       | string  | no       | Seller display name                                            |
| seller_url        | string  | no       | Seller profile URL (query stripped)                            |
| photos            | array   | yes      | Carousel + main image URLs                                     |
| description_url   | string  | no       | `iframe#desc_ifr` src                                          |
| features          | object  | yes      | Key/value feature table from `.ux-layout-section--features`    |
| variants          | array   | yes      | List of `Variant` objects (may be empty)                       |

## Variant

| Field                     | Type    | Required | Notes                                                       |
| ------------------------- | ------- | -------- | ----------------------------------------------------------- |
| id                        | string  | yes      | Variant ID                                                  |
| price_original            | number  | no       | Original price value                                        |
| price_original_currency   | string  | no       | ISO currency, e.g. `"USD"`                                  |
| price_converted           | number  | no       | Converted price value                                       |
| price_converted_currency  | string  | no       | ISO currency, e.g. `"USD"`                                  |
| out_of_stock              | boolean | no       | From `quantity.outOfStock`                                  |

Additional keys named after selection labels (e.g. `Color`, `Model`) may appear with the option string value.
