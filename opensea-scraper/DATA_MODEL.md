# OpenSea data model

Single source of truth for the Python (cerberus) and Node (zod) schemas under [`python/`](python/) and [`nodejs/`](nodejs/).

OpenSea ships its data inside Next.js + urql hydration blobs embedded as `(window[Symbol.for("urql_transport")] ??= []).push({...})` script blocks. The scraper renders the page in Scrapeless's [Scraping Browser](https://www.scrapeless.com/en/scraping-browser), extracts every `urql_transport` payload, and folds the GraphQL responses into the shapes below.

## Collection — emitted by `scrape_collection`

| Field             | Type     | Required | Notes                                                              |
| ----------------- | -------- | -------- | ------------------------------------------------------------------ |
| slug              | string   | yes      | URL slug (e.g. `"boredapeyachtclub"`)                              |
| name              | string   | yes      | Display name                                                       |
| description       | string   | no       | Marketing description                                              |
| chain             | string   | no       | Chain identifier (`"ethereum"`, `"matic"`, …)                      |
| total_supply      | int      | no       | Total items in the collection                                      |
| floor_price       | float    | no       | Floor price in the collection's native unit                        |
| floor_currency    | string   | no       | Native unit symbol (`"ETH"`, `"MATIC"`, …)                         |
| floor_price_usd   | float    | no       | USD value of the floor at parse time                               |
| volume_native     | float    | no       | All-time volume in the collection's native unit                    |
| volume_usd        | float    | no       | All-time volume USD                                                |
| image             | string   | no       | Hero/featured image URL                                            |
| url               | string   | yes      | Canonical collection URL                                           |

## Asset — emitted by `scrape_asset`

| Field           | Type      | Required | Notes                                                  |
| --------------- | --------- | -------- | ------------------------------------------------------ |
| chain           | string    | yes      | Chain identifier                                       |
| contract        | string    | yes      | Contract address                                       |
| token_id        | string    | yes      | Token id                                               |
| name            | string    | yes      | Item name (e.g. `"#1"` or a custom item title)        |
| collection_slug | string    | no       | Slug of the parent collection                          |
| collection_name | string    | no       | Display name of the parent collection                  |
| owner           | string    | no       | Display name of the current owner                      |
| owner_address   | string    | no       | Owner wallet address                                   |
| rarity_rank     | int       | no       | Rarity rank within the collection                      |
| image           | string    | no       | Item image URL                                         |
| traits          | object[]  | no       | `{ trait_type, value }` pairs                          |
| best_offer      | float     | no       | Best bid in native token units                         |
| best_offer_currency | string | no      | Native token symbol (`"WETH"`, `"ETH"`, …)             |
| url             | string    | yes      | Canonical item URL                                     |
