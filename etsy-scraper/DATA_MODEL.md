# Etsy data model

Three surfaces:

- `scrape_search(url, max_pages)` → list of `SearchResult`
- `scrape_product(urls)` → list of `Product` (raw JSON-LD `Product` schema lifted from each listing page)
- `scrape_shop(urls)` → list of `Shop` (raw JSON-LD `ItemList` schema lifted from each shop page, plus `url`)

## SearchResult

Extracted per listing card on `/search?q=...`.

| Field            | Type            | Required | Notes                                                       |
| ---------------- | --------------- | -------- | ----------------------------------------------------------- |
| productLink      | string          | yes      | Absolute URL to the listing                                 |
| productTitle     | string          | yes      |                                                             |
| productImage     | string          | yes      | Card thumbnail URL                                          |
| seller           | string \| null  | no       | Shop name extracted from `"From shop X"` label              |
| listingType      | string          | yes      | `"paid"` for promoted listings, `"organic"` otherwise       |
| productRate      | float \| null   | no       | Aggregate star rating                                       |
| numberOfReviews  | integer \| null | no       | Review count                                                |
| freeShipping     | string          | yes      | `"yes"` / `"no"`                                            |
| productPrice     | float           | yes      | Numeric price (current)                                     |
| priceCurrency    | string          | yes      | Currency symbol from `<span class="currency-symbol">`       |
| originalPrice    | string          | no       | Pre-discount display string when on sale                    |
| discount         | string          | yes      | e.g. `"30% off"` or empty                                   |

## Product

Lifted verbatim from the `application/ld+json` `Product` block on the listing page. Fields below are the keys covered by the upstream reference's validator; additional keys are passed through.

| Field        | Type    | Required | Notes                                            |
| ------------ | ------- | -------- | ------------------------------------------------ |
| @type        | string  | yes      | `"Product"`                                      |
| @context     | string  | yes      | `"http://schema.org"`                            |
| url          | string  | yes      |                                                  |
| name         | string  | yes      |                                                  |
| sku          | string  | no       |                                                  |
| gtin         | string  | no       |                                                  |
| description  | string  | no       |                                                  |
| category     | string  | no       |                                                  |
| logo         | string  | no       |                                                  |
| material     | string  | no       |                                                  |
| reviews      | list    | no       | Each item has `@type`, `datePublished`, `reviewBody` |

## Shop

Lifted verbatim from the `application/ld+json` `ItemList` block on the shop page, plus a synthetic `url` we attach.

| Field            | Type    | Required | Notes                                           |
| ---------------- | ------- | -------- | ----------------------------------------------- |
| @type            | string  | yes      | `"ItemList"`                                    |
| @context         | string  | yes      | `"http://schema.org"`                           |
| url              | string  | yes      | Original shop URL we requested                  |
| itemListElement  | list    | yes      | Per-item dicts with `@type`, `image`, `name`, `url`, `brand` (`@type`, `name`), `offers` (`@type`, `price`, `priceCurrency`), `position` |
