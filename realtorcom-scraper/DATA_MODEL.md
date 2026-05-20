# Realtorcom data model

Single source of truth for the Python (cerberus) and Node (zod) schemas under [`python/`](python/) and [`nodejs/`](nodejs/). Mirrors  verbatim.

Realtor.com embeds a `__NEXT_DATA__` script on both property and search pages. the upstream reference extracts the property page through a JMESPath reduction, projecting Realtor's verbose Redux store down to a flat dict. The search page returns an array of property cards plus the unreduced totals. There's also a sitemap-style atom feed parser that yields `{url -> last_modified}` pairs.

## Property

Output of the upstream reference's JMESPath projection (verbatim field names):

| Field                  | Type   | Required | Notes                                                |
| ---------------------- | ------ | -------- | ---------------------------------------------------- |
| id                     | string | yes      | `propertyDetails.listing_id`                         |
| slug                   | string | no       | URL slug                                             |
| url                    | string | yes      | `propertyDetails.href`                               |
| status                 | string | no       | e.g. `for_sale`, `sold`                              |
| tags                   | list   | no       |                                                      |
| sold_date              | string | no       | `propertyDetails.last_sold_date`                     |
| sold_price             | number | no       | `propertyDetails.last_sold_price`                    |
| list_date              | string | no       | `propertyDetails.list_date`                          |
| list_price             | number | no       | `propertyDetails.list_price`                         |
| list_price_last_change | number | no       | `propertyDetails.last_price_change_amount`           |
| details                | object | no       | `propertyDetails.description` (full block)           |
| flags                  | object | no       |                                                      |
| local                  | object | no       |                                                      |
| location               | object | no       | `propertyDetails.location`                           |
| agent                  | list   | no       | `propertyDetails.source.agents`                      |
| advertisers            | list   | no       |                                                      |
| tax_history            | list   | no       |                                                      |
| history                | list   | no       | `[ { date, event, price, price_sqft } ]`             |
| photos                 | list   | no       | `[ { url, tags: [label, ...] } ]`                    |
| phones                 | list   | no       | `[ { type, number } ]`                               |
| features               | object | no       | `{ <category>: <text> }` flattened from list         |

## SearchResult

Entry from `props.pageProps.properties` (or `props.pageProps.searchResults.home_search.results`). Realtor.com returns a wide schema — most stable keys:

| Field             | Type   | Required | Notes                                          |
| ----------------- | ------ | -------- | ---------------------------------------------- |
| property_id       | string | yes      | Realtor.com property id                        |
| listing_id        | string | no       |                                                |
| status            | string | no       | `for_sale`, `for_rent`, etc.                   |
| href              | string | no       | Canonical listing URL                          |
| list_price        | number | no       |                                                |
| list_price_min    | number | no       |                                                |
| list_price_max    | number | no       |                                                |
| price_reduced_amount | number | no   |                                                |
| description       | object | no       | `{ beds, baths, sqft, lot_sqft, type, ... }`   |
| location          | object | no       | `{ address, county, ... }`                     |
| photos            | list   | no       |                                                |
| primary_photo     | object | no       |                                                |
| flags             | object | no       |                                                |
| open_houses       | list   | no       |                                                |
| products          | object | no       |                                                |
| source            | object | no       |                                                |

## FeedEntry

Output of `scrape_feed(url)` — a single `{loc: lastmod}` mapping dict. Keys are sitemap `<loc>` URLs and values are ISO-8601 `<lastmod>` timestamps. There are no fixed field names; the dict's shape is purely dynamic.

| Field    | Type     | Required | Notes                                         |
| -------- | -------- | -------- | --------------------------------------------- |
| ...      | string   | no       | Map key is the sitemap `loc`, value is the parsed `lastmod` (ISO-8601). |
