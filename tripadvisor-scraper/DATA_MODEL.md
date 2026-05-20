# Tripadvisor data model

## LocationData

Returned by `scrape_location_data(query)` — typeahead autocomplete results from `https://www.tripadvisor.com/`.

| Field            | Type   | Required | Notes                                                              |
| ---------------- | ------ | -------- | ------------------------------------------------------------------ |
| localizedName    | string | yes      | Display name TripAdvisor uses for the place                        |
| url              | string | yes      | Canonical location URL                                             |
| HOTELS_URL       | string | no       | Hotels listing URL for this place                                  |
| ATTRACTIONS_URL  | string | no       | Attractions listing URL                                            |
| RESTAURANTS_URL  | string | no       | Restaurants listing URL                                            |
| placeType        | string | no       | e.g. `"CITY"`, `"REGION"`, `"COUNTRY"`                              |
| latitude         | number | no       |                                                                    |
| longitude        | number | no       |                                                                    |
| ...              | any    | no       | Other fields TripAdvisor returns in `Typeahead_autocomplete.results` |

## Preview (SearchResult)

Returned by `scrape_search(search_url, max_pages=...)` — one entry per hotel card on `/Hotels-g.../...html` listing pages.

| Field | Type   | Required | Notes                                            |
| ----- | ------ | -------- | ------------------------------------------------ |
| url   | string | yes      | Absolute hotel detail URL (query + fragment stripped) |
| name  | string | yes      | Hotel name                                       |

## Hotel

Returned by `scrape_hotel(url, max_review_pages=...)`.

| Field        | Type          | Required | Notes                                                                                                  |
| ------------ | ------------- | -------- | ------------------------------------------------------------------------------------------------------ |
| basic_data   | object        | yes      | Raw schema.org JSON-LD object containing `aggregateRating`, address, name, etc.                        |
| description  | string        | no       | Hotel description text                                                                                 |
| featues      | list<string>  | yes      | Amenities (mirrors the upstream reference's typo `featues`)                                                          |
| reviews      | list<Review>  | yes      | See below                                                                                              |

### Hotel.reviews item

| Field    | Type    | Required | Notes                                                       |
| -------- | ------- | -------- | ----------------------------------------------------------- |
| title    | string  | no       | Review title                                                |
| text     | string  | no       | Concatenated review body text                               |
| rate     | number  | no       | Bubble rating (1-5), parsed from `"X of 5 bubbles"` text    |
| tripDate | string  | no       | `Date of stay:` value                                       |
| tripType | string  | no       | `Trip type:` value                                          |
