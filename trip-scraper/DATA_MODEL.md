# Trip.com data model

Single source of truth for the Python (cerberus) and Node (zod) schemas under [`python/`](python/) and [`nodejs/`](nodejs/).

Trip.com surfaces two primary shapes — hotel cards on a city list page and a hotel detail page with longer copy + amenities.

## SearchResult

Returned by `scrape_search(city_id, checkin, checkout, max_pages)` — one element per `div.hotel-card` on a Trip.com city search page.

| Field        | Type             | Required | Notes                                                  |
| ------------ | ---------------- | -------- | ------------------------------------------------------ |
| id           | string           | yes      | Master hotel id from `div.hotel-card[id]`              |
| name         | string           | yes      | Hotel display name (`.hotel-title`)                    |
| url          | string           | yes      | Built from masterhotelid (detail URL)                  |
| score        | string \| null   | no       | Numeric rating, e.g. `"9.4"` (`.score`)                |
| reviewWord   | string \| null   | no       | Word-form rating, e.g. `"Outstanding"`                 |
| reviewCount  | integer \| null  | no       | Total reviews                                          |
| price        | string \| null   | no       | Nightly price string (e.g. `"US$57"`)                  |
| totalPrice   | string \| null   | no       | Total incl. taxes (`.price-explain`)                   |
| tags         | array            | yes      | Promo / amenity tags (`.hotel-tag`)                    |
| location     | string \| null   | no       | First location/landmark line                           |
| image        | string \| null   | no       | First hotel image URL                                  |

## Hotel

Returned by `scrape_hotel(hotel_id, checkin, checkout)` — one object per hotel detail page.

| Field        | Type             | Required | Notes                                                |
| ------------ | ---------------- | -------- | ---------------------------------------------------- |
| id           | string           | yes      | Master hotel id                                      |
| url          | string           | yes      | Canonical detail URL                                 |
| name         | string           | yes      | Hotel display name                                   |
| address      | string \| null   | no       | Address line                                         |
| score        | string \| null   | no       | Numeric rating                                       |
| reviewCount  | integer \| null  | no       | Total reviews                                        |
| description  | string           | yes      | Concatenated description / introduction text        |
| amenities    | array            | yes      | Listed amenities / facilities                        |
| images       | array            | yes      | Image URLs                                           |
| price        | string \| null   | no       | Lowest displayed nightly price                       |
