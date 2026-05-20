# Vestiairecollective data model

Two surfaces:

- `scrape_products(urls)` → list of `Product` (lifted from `__NEXT_DATA__.props.pageProps.product` on each listing page)
- `scrape_search(url, max_pages)` → list of `SearchResult` (lifted from the in-page `/v1/product/search` XHR, then paginated via direct API calls)

## Product

Top-level keys covered by the upstream reference's validator:

| Field                | Type    | Required | Notes                                            |
| -------------------- | ------- | -------- | ------------------------------------------------ |
| id                   | string  | yes      |                                                  |
| type                 | string  | no       |                                                  |
| name                 | string  | yes      |                                                  |
| price                | dict    | no       | `{currency, cents, formatted}`                   |
| description          | string  | no       |                                                  |
| likeCount            | integer | no       |                                                  |
| path                 | string  | no       |                                                  |
| measurementFormatted | string  | no       |                                                  |
| unit                 | string  | no       |                                                  |
| metadata             | dict    | no       | `{title, description, keywords}`                 |
| warehouse            | dict    | no       | `{name, localizedName}`                          |
| brand                | dict    | no       | `{id, type, name, localizedName}`                |

## SearchResult

| Field        | Type    | Required | Notes                                                                            |
| ------------ | ------- | -------- | -------------------------------------------------------------------------------- |
| id           | integer | yes      |                                                                                  |
| name         | string  | no       |                                                                                  |
| description  | string  | no       |                                                                                  |
| country      | string  | no       |                                                                                  |
| likes        | integer | no       |                                                                                  |
| link         | string  | no       |                                                                                  |
| pictures     | list    | no       | list of string                                                                   |
| price        | dict    | no       | `{cents, currency}`                                                              |
| seller       | dict    | no       | `{id, firstname, badge, picture, isOfficialStore}`                               |
| sold         | boolean | no       |                                                                                  |
| stock        | boolean | no       |                                                                                  |
| shouldBeGone | boolean | no       |                                                                                  |
| createdAt    | integer | no       |                                                                                  |
| universeId   | integer | no       |                                                                                  |
| dutyFree     | boolean | no       |                                                                                  |
