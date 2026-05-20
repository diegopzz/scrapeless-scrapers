# AliExpress data model

Four object kinds are emitted:

- `search.json` → list of search-result items (free-form from `_init_data_.data.root.fields.mods.itemList.content`)
- `category_products.json` → list of category-page items (same shape as search)
- `product.json` → single `Product` wrapper with `info / pricing / specifications / delivery / faqs`
- `reviews.json` → `Reviews` wrapper with `reviews / evaluation_stats`

## Product

| Field          | Type    | Required | Notes                                                                  |
| -------------- | ------- | -------- | ---------------------------------------------------------------------- |
| info           | object  | yes      | Product metadata (see `Info` below)                                    |
| pricing        | object  | yes      | Pricing (see `Pricing` below)                                          |
| specifications | array   | yes      | List of `{name, value}` rows                                           |
| delivery       | string  | no       | Delivery date string from `.dynamic-shipping`                          |
| faqs           | array   | yes      | List of `{question, answer}`                                           |

## Info

| Field          | Type    | Required | Notes                                              |
| -------------- | ------- | -------- | -------------------------------------------------- |
| name           | string  | yes      | From `<h1 data-pl>`                                |
| productId      | number  | yes      | Int parsed from `/item/<id>.html`                  |
| link           | string  | yes      | Canonical product URL                              |
| media          | array   | yes      | Image URLs from slider                             |
| rate           | number  | no       | Star rating count (filled stars)                   |
| reviews        | number  | no       | Review count                                       |
| soldCount      | number  | yes      | Total sold count (int)                             |
| availableCount | number  | yes      | Available stock count (int)                        |

## Pricing

| Field         | Type   | Required | Notes                                            |
| ------------- | ------ | -------- | ------------------------------------------------ |
| priceCurrency | string | yes      | e.g. `"USD $"` for US localization               |
| price         | number | no       | Current price value                              |
| originalPrice | mixed  | no       | Original price number, or `"No discount"`        |
| discount      | string | yes      | Discount string, or `"No discount"`              |

## Reviews

| Field            | Type   | Required | Notes                                          |
| ---------------- | ------ | -------- | ---------------------------------------------- |
| reviews          | array  | yes      | List of `evaViewList` review objects           |
| evaluation_stats | object | yes      | `productEvaluationStatistic` blob              |

## SearchResult

Free-form objects from AliExpress's `itemList.content` (free-form keys: `productId`, `title`, `images`, `prices`, `trace`, etc.). Validator only checks that an object is present.

| Field     | Type   | Required | Notes                          |
| --------- | ------ | -------- | ------------------------------ |
| productId | mixed  | no       | Product ID (string or int)     |
