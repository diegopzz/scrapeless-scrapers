# Fashionphile data model

Two surfaces:

- `scrape_search(url, max_pages)` → list of `SearchResult` (parsed from `.fp-algolia-product-card` cards)
- `scrape_products(urls)` → list of `Product` (lifted from Fashionphile's `/products/<slug>.json` endpoint)

## SearchResult

| Field            | Type    | Required | Notes                                                          |
| ---------------- | ------- | -------- | -------------------------------------------------------------- |
| brand_name       | string  | yes      | Vendor / brand from `.fp-card__vendor`                         |
| product_name     | string  | yes      | Listing title from `.fp-card__link__product-name`              |
| condition        | string  | yes      | e.g. `"Excellent"` from `.fp-condition`                        |
| discounted_price | integer | yes      | Regular - sale (USD, whole dollars). `0` if no sale            |
| price            | integer | yes      | Final price (sale if present, else regular). USD whole dollars |
| id               | integer | yes      | `data-product-id` attribute on the card                        |

## Product

Lifted verbatim from `/products/<slug>.json` — Fashionphile exposes the same JSON the storefront consumes. Top-level keys covered by the upstream reference's validator:

| Field              | Type            | Required | Notes                                                                          |
| ------------------ | --------------- | -------- | ------------------------------------------------------------------------------ |
| id                 | integer         | yes      |                                                                                |
| title              | string          | yes      |                                                                                |
| handle             | string          | no       | URL slug (Shopify field name — equivalent to `slug`)                           |
| sku                | string          | no       | Not present at top-level; per-variant under `variants[].sku`                   |
| price              | integer         | no       | Not present at top-level; per-variant under `variants[].price` as string       |
| renewDays          | integer         | no       |                                                                                |
| discountedPrice    | integer         | no       |                                                                                |
| discountEnabled    | integer         | no       | 0/1 toggle                                                                     |
| discountedTier     | integer         | no       |                                                                                |
| madeAvailableAt    | string          | no       | ISO timestamp                                                                  |
| approvedAt         | string          | no       | ISO timestamp                                                                  |
| madeAvailableAtUTC | string          | no       | ISO timestamp                                                                  |
| year               | integer \| null | no       |                                                                                |
| condition          | string          | no       | Surfaced inside `tags`/`body_html`; not a top-level Shopify field              |
| authenticCta       | string          | no       |                                                                                |
| brand              | list            | no       | List of `{id, name, slug, type, description, title}`                           |
| vendor             | string          | no       | Shopify vendor (brand display name)                                            |
| body_html          | string          | no       | Description HTML                                                               |
| variants           | array           | no       | Shopify variants — each has `id`, `sku`, `price`, `compare_at_price`, etc.     |
| images             | array           | no       | Shopify images                                                                 |
| tags               | string          | no       | Comma-separated Shopify tag string                                             |
