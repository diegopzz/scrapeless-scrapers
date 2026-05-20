# Nordstrom data model

Single source of truth for the Python (cerberus) and Node (zod) schemas under [`python/`](python/) and [`nodejs/`](nodejs/). Field names mirror the canonical  verbatim (folder name keeps upstream's `nordstorm` typo — the site itself is nordstrom.com).

## Product

Emitted by `scrape_products(urls)`. Projected from the React/Apollo cache's `stylesById.<styleId>` via `parse_product`.

| Field                | Type           | Required | Notes                                                              |
| -------------------- | -------------- | -------- | ------------------------------------------------------------------ |
| id                   | string         | yes      | Style id                                                           |
| title                | string         | yes      | From `productTitle`                                                |
| type                 | string         | no       | From `productTypeName` (e.g. `"Sneakers"`)                         |
| typeParent           | string         | no       | From `productTypeParentName`                                       |
| ageGroups            | list           | no       |                                                                    |
| reviewAverageRating  | number         | no       |                                                                    |
| numberOfReviews      | integer        | no       |                                                                    |
| brand                | object         | no       | `{brandName, brandId, ...}`                                        |
| description          | string         | no       | From `sellingStatement`                                            |
| features             | list           | no       |                                                                    |
| gender               | string         | no       |                                                                    |
| isAvailable          | boolean        | no       |                                                                    |
| media                | list           | yes      | `[{colorCode, colorName, urls[]}]` — one entry per color carousel  |
| variants             | object         | yes      | SKU id → `{id, sizeId, colorId, totalQuantityAvailable, price, color: {id, value, sizes, mediaIds, swatch}}` |

## SearchProduct

Emitted by `scrape_search(url, max_pages)`. Raw `productResults.productsById[<id>]` values — the upstream reference upstream returns these without projecting through `parse_product`, so every key Nordstrom ships is preserved.

| Field          | Type           | Required | Notes                                                          |
| -------------- | -------------- | -------- | -------------------------------------------------------------- |
| id             | integer        | yes      | Style id                                                       |
| productName    | string         | no       |                                                                |
| brandName      | string         | no       |                                                                |
| price          | object         | no       |                                                                |
| rmsImage       | object         | no       | Image asset map                                                |
| productPageUrl | string         | no       |                                                                |
