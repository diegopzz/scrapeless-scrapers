# Depop data model

Three object kinds are emitted from this scraper.

- `scrape_product(product_url)` returns a single `Product`
- `scrape_search(query, max_pages)` returns a list of `SearchResult`
- `scrape_shop(username)` returns a `Shop` envelope

Fixtures live under [`results/`](results/) and are validated against the tables
below by [`tools/verify-fixtures.py`](../tools/verify-fixtures.py).

## Product

Lifted from a Depop product page (e.g. `https://www.depop.com/products/<slug>/`).
Depop is a Next.js app and the bulk of product data is available either through
the `<script id="__NEXT_DATA__">` blob or `application/ld+json` schema.org tags.

| Field           | Type            | Required | Notes                                                                  |
| --------------- | --------------- | -------- | ---------------------------------------------------------------------- |
| id              | string          | yes      | Product slug (`<username>-<slug>`) from the URL                        |
| url             | string          | yes      | Canonical product URL                                                  |
| title           | string          | yes      | Product title / description headline                                   |
| price           | string \| null  | no       | Current price display                                                  |
| currency        | string \| null  | no       | Currency code                                                          |
| brand           | string \| null  | no       | Brand attribute when present                                           |
| condition       | string \| null  | no       | Condition string (e.g. `"Used - Like new"`)                            |
| size            | string \| null  | no       | Size text when present                                                 |
| color           | string \| null  | no       | Colour text when present                                               |
| description     | string \| null  | no       | Long description                                                       |
| images          | string[]        | yes      | Image URLs harvested from gallery + og:image                           |
| seller          | string \| null  | no       | Seller username                                                        |
| sellerUrl       | string \| null  | no       | Seller storefront URL                                                  |
| hashtags        | string[]        | yes      | Hashtag list when present                                              |
| sold            | boolean         | yes      | True if the listing is marked `sold`                                   |

## SearchResult

Each card on `https://www.depop.com/search/?q=...`.

| Field        | Type            | Required | Notes                                                       |
| ------------ | --------------- | -------- | ----------------------------------------------------------- |
| id           | string          | yes      | Slug parsed from the card's link                            |
| title        | string          | yes      | Card title (alt text)                                       |
| url          | string          | yes      | Absolute card URL                                           |
| image        | string \| null  | no       | Card thumbnail URL                                          |
| price        | string \| null  | no       | Card price display                                          |
| originalPrice| string \| null  | no       | Strikethrough price (if discounted)                         |
| seller       | string \| null  | no       | Seller username extracted from the link                     |
| size         | string \| null  | no       | Size label (if shown)                                       |

## Shop

Top-level shop summary returned by `scrape_shop`.

| Field        | Type            | Required | Notes                                                       |
| ------------ | --------------- | -------- | ----------------------------------------------------------- |
| username     | string          | yes      | Shop username (path component)                              |
| url          | string          | yes      | Shop URL                                                    |
| displayName  | string \| null  | no       | Display name surfaced on the profile                        |
| bio          | string \| null  | no       | Profile bio text                                            |
| avatar       | string \| null  | no       | Avatar image URL                                            |
| location     | string \| null  | no       | Location text shown on the profile                          |
| followers    | number \| null  | no       | Follower count                                              |
| following    | number \| null  | no       | Following count                                             |
| reviews      | number \| null  | no       | Review count                                                |
| rating       | number \| null  | no       | Aggregate rating, 0-5                                       |
| listings     | array           | yes      | List of `SearchResult`-shaped objects from the shop page    |
