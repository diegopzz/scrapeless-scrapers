# Big Lots data model

Two surfaces:

- `scrape_product(urls)` → list of `Product` (one per `/product/<slug>/` PDP URL)
- `scrape_search(category_url, max_pages)` → list of `SearchResult` (one per `/product-category/<slug>/` card)

`product.json` is a list of `Product` objects, `search.json` is a list of `SearchResult` objects.

## Product

Lifted from the WooCommerce-emitted `application/ld+json` `Product` block on the PDP. The id is the integer SKU (`schema.org/Product.sku`).

| Field         | Type    | Required | Notes                                                                       |
| ------------- | ------- | -------- | --------------------------------------------------------------------------- |
| id            | string  | yes      | Numeric SKU from JSON-LD `sku` (stringified)                                 |
| url           | string  | yes      | Canonical PDP URL                                                            |
| name          | string  | yes      | Product display name                                                         |
| description   | string  | no       | JSON-LD `description` when populated                                         |
| price         | number  | no       | First offer's `price` / `priceSpecification[].price`                          |
| priceCurrency | string  | no       | ISO 4217 (`USD`)                                                             |
| availability  | string  | no       | Schema.org availability, last segment only (`InStock` / `OutOfStock`)        |
| images        | array   | yes      | Image URLs from JSON-LD `image` or DOM gallery                               |
| categories    | array   | no       | Breadcrumb / category names                                                  |
| sellerName    | string  | no       | `offers[0].seller.name` (usually `"Big Lots"`)                                |

## SearchResult

Per-card result extracted from the `/product-category/<slug>/` listing. Each WooCommerce post anchor links to a `/product/<slug>/` PDP. The id is the WordPress post id parsed from the card's `class="post-<id>"`.

| Field         | Type    | Required | Notes                                                          |
| ------------- | ------- | -------- | -------------------------------------------------------------- |
| id            | string  | yes      | WordPress post id from the card's `post-<id>` class            |
| url           | string  | yes      | Absolute PDP URL                                               |
| name          | string  | yes      | Card title                                                     |
| image         | string  | no       | Thumbnail URL                                                  |
| price         | number  | no       | Numeric price parsed from the WooCommerce price block          |
| priceCurrency | string  | no       | `"USD"` when the price text contains `$`                       |
| category      | string  | no       | Category label printed on the card (e.g. `"Pets"`)             |
