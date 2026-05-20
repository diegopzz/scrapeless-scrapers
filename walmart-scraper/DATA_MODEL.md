# Walmart data model

Both surfaces extract data from the `__NEXT_DATA__` script blob on Walmart pages — no DOM scraping is required. The `Product` and `SearchResult` shapes therefore pass-through whatever Walmart's React data layer exposes (free-form objects); validators below only assert the **filtered top-level keys** the upstream reference emits.

## Product

Each item in `products.json` is a wrapper object with two top-level keys.

| Field    | Type   | Required | Notes                                                                 |
| -------- | ------ | -------- | --------------------------------------------------------------------- |
| product  | object | yes      | Filtered product object (see fields below)                            |
| reviews  | object | yes      | Raw `initialData.data.reviews` blob (free-form)                       |

`product` is filtered to these keys (from `wanted_product_keys` in upstream):

| Key                  | Type    | Notes                                       |
| -------------------- | ------- | ------------------------------------------- |
| availabilityStatus   | string  | e.g. `"IN_STOCK"`                           |
| averageRating        | number  | e.g. `4.5`                                  |
| brand                | string  | Brand display name                          |
| id                   | string  | Walmart product ID                          |
| imageInfo            | object  | Image URLs blob                             |
| manufacturerName     | string  | May be null                                 |
| name                 | string  | Display title                               |
| orderLimit           | number  | Per-order limit                             |
| orderMinLimit        | number  | Per-order minimum                           |
| priceInfo            | object  | Current price + linePrice blob              |
| shortDescription     | string  | HTML/text snippet                           |
| type                 | string  | Walmart product type taxonomy node          |

## SearchResult

Items in `search.json` come from `searchResult.itemStacks[0].items` — verbatim Walmart objects. Common keys include `id`, `usItemId`, `name`, `priceInfo`, `imageInfo`, `averageRating`, `numberOfReviews`, `canonicalUrl`. The validator only enforces presence of a string `id` because Walmart varies the shape per item type (sponsored, banner, grid, etc.).

| Field | Type   | Required | Notes                                  |
| ----- | ------ | -------- | -------------------------------------- |
| id    | string | no       | Walmart product / item ID (absent on ad/banner placeholders) |
| name  | string | no       | Display title                          |
