# Priceline data model

Single source of truth for the Python (cerberus) and Node (zod) schemas under [`python/`](python/) and [`nodejs/`](nodejs/).

Priceline aggressively defends both its search results and its hotel detail pages. Search-result cards are rendered client-side via a GraphQL XHR (`/pws/v0/pcln-graph?gqlOp=...`), so the scraper intercepts those responses rather than parsing the SSR HTML (which is largely empty).

## Hotel

Returned by `scrape_hotel(hotel_id, checkin, checkout)` — one object per `/relax/at/<hotel_id>` page. Data is sourced from the `rtlHotelDetails` GraphQL response (captured live) plus the SSR `window.__PRELOADED_STATE__`.

| Field        | Type             | Required | Notes                                                |
| ------------ | ---------------- | -------- | ---------------------------------------------------- |
| id           | string           | yes      | Hotel id (path segment after `/relax/at/`)           |
| url          | string           | yes      | Canonical detail URL                                 |
| name         | string           | yes      | Hotel name (may be empty when Priceline blocks data) |
| address      | string \| null   | no       | Address line                                         |
| description  | string           | yes      | Property description (may be empty)                  |
| amenities    | array            | yes      | Amenity items (may be empty)                         |
| images       | array            | yes      | Image URLs                                           |
| latitude     | number \| null   | no       | `geoCoordinate.latitude`                             |
| longitude    | number \| null   | no       | `geoCoordinate.longitude`                            |
| starRating   | string \| null   | no       | Star-rating display string                           |
| policies     | array            | yes      | Property-policy items                                |
| pageTitle    | string \| null   | no       | HTML `<title>` (fallback identifier)                 |

## SearchResult

Returned by `scrape_search(city_id, checkin, checkout)` — one element per hotel from the listings GraphQL response. Returns an empty list when Priceline withholds the data (anti-bot interstitial); callers should treat zero results as a soft failure.

| Field        | Type             | Required | Notes                                                |
| ------------ | ---------------- | -------- | ---------------------------------------------------- |
| id           | string           | yes      | Hotel id                                             |
| name         | string           | yes      | Hotel name                                           |
| url          | string           | yes      | Detail URL                                           |
| price        | string \| null   | no       | Lowest-display price string                          |
| starRating   | number \| null   | no       | 1-5 star rating                                      |
| review       | number \| null   | no       | Review average score                                 |
| reviewCount  | integer \| null  | no       | Number of reviews                                    |
| image        | string \| null   | no       | Primary image URL                                    |
| neighborhood | string \| null   | no       | Neighborhood / area label                            |
