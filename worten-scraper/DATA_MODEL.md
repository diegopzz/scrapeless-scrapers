# Worten data model

Two object kinds are emitted:

- `product.json` → single `Product`, parsed from the schema.org `ld+json` Product blob on the `/produtos/<slug>-<id>` detail page.
- `category.json` → single `Category`, parsed from a category landing page (`/promocoes/...`, `/informatica-e-acessorios/...`, etc.). Category result tiles are rendered client-side behind a Turnstile gate; the breadcrumb / meta / heading are reliable signals served in the SSR HTML.

## Product

| Field         | Type    | Required | Notes                                                                |
| ------------- | ------- | -------- | -------------------------------------------------------------------- |
| sku           | string  | yes      | Numeric Worten SKU (trailing `-NNNNNNN` in the URL slug)             |
| name          | string  | yes      | `ld+json` `name`                                                     |
| brand         | string  | no       | `ld+json` `brand.name`                                               |
| description   | string  | no       | `ld+json` `description` (raw HTML allowed)                           |
| image         | string  | no       | First image URL (`/i/<hash>` paths are returned absolute)            |
| price         | string  | no       | Offer price (string)                                                 |
| priceCurrency | string  | no       | ISO currency, normally `EUR`                                         |
| availability  | string  | no       | `ld+json` offer `availability` URL                                   |
| ratingValue   | number  | no       | `ld+json` `aggregateRating.ratingValue`                              |
| reviewCount   | number  | no       | `ld+json` `aggregateRating.reviewCount`                              |
| url           | string  | yes      | Canonical product URL                                                |
| breadcrumb    | array   | yes      | List of `{name, url, position}` from the BreadcrumbList `ld+json`    |

## Category

| Field       | Type   | Required | Notes                                                                              |
| ----------- | ------ | -------- | ---------------------------------------------------------------------------------- |
| name        | string | yes      | Category heading (`<h1>`)                                                          |
| title       | string | no       | `<title>` text                                                                     |
| description | string | no       | `meta[name=description]` content                                                   |
| url         | string | yes      | Canonical category URL                                                             |
| breadcrumb  | array  | yes      | List of `{name, url, position}` from the BreadcrumbList `ld+json` (may be empty)   |
