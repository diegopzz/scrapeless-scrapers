# Leboncoin data model

Single source of truth for the Python (cerberus) and Node (zod) schemas under [`python/`](python/) and [`nodejs/`](nodejs/). Field names mirror the canonical  verbatim.

Both surfaces emit raw entries from Leboncoin's NextJS cache (`props.pageProps.searchData.ads` and `props.pageProps.ad`) — fields are pass-through, so downstream consumers get every key Leboncoin ships, including category-specific attributes.

## Ad (full)

Emitted by `scrape_ad(url)`. Raw `props.pageProps.ad` from the ad page.

| Field          | Type          | Required | Notes                                                  |
| -------------- | ------------- | -------- | ------------------------------------------------------ |
| list_id        | integer       | yes      | Leboncoin ad id (numeric)                              |
| subject        | string        | yes      | Ad title                                               |
| body           | string\|null  | no       | Full description                                       |
| url            | string        | yes      | Canonical ad URL                                       |
| category_id    | string\|null  | no       |                                                        |
| category_name  | string\|null  | no       | e.g. `"Ventes immobilières"`                           |
| price          | list\|number  | no       | Often `[value]` array, currency separate               |
| images         | object\|null  | no       | `{nb_images, small_url, thumb_url, urls, urls_large}`  |
| attributes     | list\|null    | no       | List of `{key, value, value_label, ...}` (varies)      |
| location       | object\|null  | no       | `{city, zipcode, lat, lng, region_name, ...}`          |
| owner          | object\|null  | no       | `{type, user_id, name, no_salesmen, ...}`              |

## SearchAd

Emitted by each element of `scrape_search(url, scrape_all_pages, max_pages)`. Raw `props.pageProps.searchData.ads[i]` — same key namespace as `Ad`, fewer optional fields populated.

| Field          | Type          | Required | Notes                              |
| -------------- | ------------- | -------- | ---------------------------------- |
| list_id        | integer       | yes      |                                    |
| subject        | string        | yes      |                                    |
| url            | string        | yes      |                                    |
| category_id    | string\|null  | no       |                                    |
| category_name  | string\|null  | no       |                                    |
| price          | list\|number  | no       |                                    |
