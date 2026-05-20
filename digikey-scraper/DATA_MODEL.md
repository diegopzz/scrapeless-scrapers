# Digi-Key data model

Two object kinds are emitted:

- `product.json` → single `Product` (one Digi-Key part)
- `search.json` → list of `SearchResult` (category groupings returned by the keyword search page; Digi-Key's keyword search returns categories, not individual parts)

All payloads are parsed from the page's `#__NEXT_DATA__` script (`props.pageProps.envelope.data`).

## Product

| Field                  | Type    | Required | Notes                                                                              |
| ---------------------- | ------- | -------- | ---------------------------------------------------------------------------------- |
| digikeyPartNumber      | string  | yes      | e.g. `296-1395-5-ND`                                                               |
| manufacturerPartNumber | string  | yes      | e.g. `LM358P`                                                                      |
| manufacturer           | string  | yes      | e.g. `Texas Instruments`                                                           |
| title                  | string  | yes      | Product title shown on detail page                                                 |
| description            | string  | no       | Short description                                                                  |
| detailedDescription    | string  | no       | Long-form description                                                              |
| datasheetUrl           | string  | no       | URL to the manufacturer datasheet                                                  |
| productUrl             | string  | yes      | Canonical detail-page URL                                                          |
| imageUrl               | string  | no       | First image in the carousel                                                        |
| media                  | array   | yes      | List of media URLs from the carousel                                               |
| breadcrumb             | array   | yes      | List of `{label, url}` breadcrumb entries                                          |
| attributes             | array   | yes      | List of `{label, value}` attribute rows                                            |
| pricing                | array   | yes      | List of `{breakQuantity, unitPrice, extendedPrice}` price-break rows               |
| stock                  | object  | yes      | `{quantityAvailable, hasLeadTime, leadTime, minimumOrderQuantity, packaging}`      |
| isActive               | boolean | yes      | True when part status reads `Active`                                               |
| isUnavailable          | boolean | yes      | Mirrors envelope `isUnavailable`                                                   |

## SearchResult

Each result is a category grouping. Digi-Key returns categories rather than parts on the keyword search page.

| Field          | Type   | Required | Notes                                                  |
| -------------- | ------ | -------- | ------------------------------------------------------ |
| id             | string | yes      | Category id                                            |
| categoryName   | string | yes      | Leaf category name                                     |
| parentCategory | string | no       | Parent category name                                   |
| productCount   | string | yes      | Total parts in that category for the query             |
| categoryUrl    | string | yes      | Path under `/en/products/filter/...`                   |
| imageUrl       | string | no       | Thumbnail for the category                             |
