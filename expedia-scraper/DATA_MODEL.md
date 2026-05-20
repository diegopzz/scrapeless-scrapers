# Expedia data model

Single source of truth for the Python (cerberus) and Node (zod) schemas under [`python/`](python/) and [`nodejs/`](nodejs/).

Expedia ships its anti-bot ("Bot or Not?") interstitial on cold direct visits to `/Hotel-Search`. The scraper warms up on the homepage first to set session cookies, then navigates to the search URL. Property cards live under `[data-stid="lodging-card-responsive"]`.

## SearchResult

Returned by `scrape_search(destination, checkin, checkout, max_pages)` — one element per `[data-stid="lodging-card-responsive"]` card in `/Hotel-Search` results.

| Field        | Type             | Required | Notes                                                  |
| ------------ | ---------------- | -------- | ------------------------------------------------------ |
| id           | string           | yes      | Hotel id from the detail URL (`.h<id>.Hotel-Information`) |
| name         | string           | yes      | Hotel name (`<h3>` inside the card)                    |
| url          | string           | yes      | Absolute detail URL                                    |
| price        | string \| null   | no       | Headline nightly/total price (e.g. `"$254"`)           |
| review       | string \| null   | no       | Review summary string (e.g. `"1 out of 10"`)           |
| image        | string \| null   | no       | Primary card image URL                                 |

## Hotel

Returned by `scrape_hotel(hotel_url)` — one object per hotel detail page.

| Field       | Type             | Required | Notes                                              |
| ----------- | ---------------- | -------- | -------------------------------------------------- |
| id          | string           | yes      | Hotel id extracted from URL                        |
| url         | string           | yes      | Canonical detail URL                               |
| name        | string           | yes      | Hotel name                                         |
| address     | string \| null   | no       | Street address                                     |
| description | string           | yes      | About / overview body text                         |
| amenities   | array            | yes      | Amenity bullet text                                |
| images      | array            | yes      | Image URLs                                         |
| review      | string \| null   | no       | Review summary text                                |
| price       | string \| null   | no       | Headline price text                                |
