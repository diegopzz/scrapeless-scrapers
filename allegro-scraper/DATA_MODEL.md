# Allegro data model

Allegro embeds search/product state in `<script data-serialize-box-id="...">` JSON blobs (and `<script>` blocks containing `__listing_StoreState`). Polish characters are preserved verbatim.

## SearchPage

Returned by `scrape_search(query, max_pages=3, scrape_all_pages=False)`.

| Field          | Type             | Required | Notes                                           |
| -------------- | ---------------- | -------- | ----------------------------------------------- |
| products       | list[SearchItem] | yes      | Items from `__listing_StoreState.items.elements`. |
| scraped_pages  | int              | yes      | Number of pages actually fetched.               |
| products_count | int              | yes      | Length of `products`.                           |
| total_pages    | int              | no       | `props.searchMeta.lastAvailablePage`.           |
| total_count    | int              | no       | `props.searchMeta.totalCount`.                  |

## SearchItem

Element of `SearchPage.products`. Not a top-level fixture shape — listed here so the table is parsed as its own section.

| Field          | Type   | Required | Notes                                          |
| -------------- | ------ | -------- | ---------------------------------------------- |
| product_id     | string | yes      |                                                |
| offer_id       | string | yes      |                                                |
| title          | string | yes      |                                                |
| price          | object | no       | `{ amount, currency }`.                        |
| currency       | string | no       |                                                |
| url            | string | yes      |                                                |
| image          | string | no       |                                                |
| seller         | object | no       | Mirrors Allegro's seller sub-object.           |
| delivery_info  | object | no       |                                                |

## Product

Returned by `scrape_product(urls)` — one dict per URL.

| Field                | Type   | Required | Notes                                                 |
| -------------------- | ------ | -------- | ----------------------------------------------------- |
| title                | string | yes      |                                                       |
| price                | object | yes      | `{ formattedPrice, ... }` from the price box.         |
| images               | list   | no       | URLs from the gallery box.                            |
| shipping_info        | object | no       |                                                       |
| rating               | string | no       | `aggregateRating.ratingValue` from JSON-LD.           |
| specifications       | list   | no       | List of `{name, value}` rows.                         |
| seller               | object | no       | `{sellerName, ...}` from the seller box.              |
| reviews              | list   | no       | Extracted from the reviews box when present.          |
| allegro_smart_badge  | bool   | no       | True if the "Smart!" badge is present.                |
