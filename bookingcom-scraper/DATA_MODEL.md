# Booking.com data model

Booking.com surfaces three primary shapes — location autocomplete results, full hotel detail pages, and per-property review cards.

## Location

Returned inside `LocationSuggestions.results` by `search_location_suggestions(query)` — one element per autocomplete match. | Field                          | Type             | Required | Notes                                                |
| ------------------------------ | ---------------- | -------- | ---------------------------------------------------- |
| dest_id                        | string           | yes      | Booking destination id (feeds search)                |
| dest_type                      | string           | yes      | e.g. `"city"`, `"region"`, `"hotel"`                 |
| value                          | string           | yes      | Free-text destination value to put back into `ss`    |
| label                          | string           | no       | Display label                                        |
| label1                         | string           | no       | First-line label                                     |
| label2                         | string           | no       | Second-line label                                    |
| labels                         | list             | no       | Structured display labels                            |
| cc1                            | string           | no       | Country code                                         |
| latitude                       | number           | no       | Lat                                                  |
| longitude                      | number           | no       | Lng                                                  |
| nr_homes                       | integer          | no       | Vacation-home count                                  |
| nr_hotels                      | integer          | no       | Hotel count                                          |
| nr_hotels_25                   | integer          | no       | Hotel count within 25 km                             |
| photo_uri                      | string           | no       | Thumbnail URL                                        |
| b_show_entire_homes_checkbox   | boolean          | no       | Affects search UI                                    |
| b_max_los_data                 | object           | no       | Max length-of-stay metadata                          |
| cjk                            | boolean          | no       | CJK locale flag                                      |
| lc                             | string           | no       | Locale code                                          |
| roundtrip                      | string           | no       | Round-trip metadata                                  |
| rtl                            | boolean          | no       | RTL flag                                             |

## SearchResult

Returned by `scrape_search(query, checkin, checkout, number_of_rooms, max_pages)` — one element per property card. Field names mirror Booking's `SearchResultProperty` GraphQL fragment that the upstream reference's parser emits.

| Field                                          | Type            | Required | Notes                                          |
| ---------------------------------------------- | --------------- | -------- | ---------------------------------------------- |
| displayName                                    | object          | yes      | Wraps `text` (property name)                   |
| basicPropertyData                              | object          | yes      | Wraps `pageName`, `location`, `reviewScore`, `starRating`, `photos` |
| location                                       | object          | yes      | Wraps `displayLocation` and `mainDistance`     |
| priceDisplayInfoIrene                          | object          | no       | Wraps `displayPrice.amountPerStay.amount`      |
| policies                                       | object          | yes      | Wraps `showFreeCancellation`                   |
| displayName.text                               | string          | no       | Property name                                  |
| basicPropertyData.pageName                     | string          | no       | Detail-page slug / link                        |
| basicPropertyData.location.address             | string \| null  | no       | Address line                                   |
| basicPropertyData.reviewScore.score            | string \| null  | no       | Numeric score as printed (e.g. `"8.7"`)        |
| basicPropertyData.reviewScore.reviewCount      | integer \| null | no       | Total review count                             |
| basicPropertyData.reviewScore.totalScoreTextTag.translation | string \| null | no | Word-form score (e.g. `"Very good"`) |
| basicPropertyData.starRating.value             | integer \| null | no       | Star rating (1–5)                              |
| basicPropertyData.photos.main.highResUrl.relativeUrl | string \| null | no | Primary photo URL                              |
| location.displayLocation                       | string \| null  | no       | Display locality                               |
| location.mainDistance                          | string \| null  | no       | Distance from search anchor                    |
| priceDisplayInfoIrene.displayPrice.amountPerStay.amount | string \| null | no | Total price for stay as displayed              |
| policies.showFreeCancellation                  | boolean         | no       | True if the card shows the free-cancel badge   |

## PriceData

One element of `Hotel.price[]`. | Field             | Type    | Required | Notes                                          |
| ----------------- | ------- | -------- | ---------------------------------------------- |
| checkin           | string  | yes      | YYYY-MM-DD                                     |
| minLengthOfStay   | integer | yes      | Minimum length of stay for that night          |
| avgPriceFormatted | string  | no       | Pre-formatted price (currency-localised)       |
| available         | boolean | yes      | Whether the night is bookable                  |

## Hotel

Returned by `scrape_hotel(url, checkin, price_n_days)`. | Field        | Type                          | Required | Notes                                          |
| ------------ | ----------------------------- | -------- | ---------------------------------------------- |
| url          | string                        | yes      | Hotel canonical URL                            |
| id           | string \| null                | no       | `b_hotel_id` (numeric ID)                      |
| title        | string \| null                | no       | `h2` heading text                              |
| description  | string                        | yes      | Concatenated property description              |
| address      | string \| null                | no       | Address line from the desktop header           |
| images       | array of strings              | yes      | Photo URLs from `#photo_wrapper img`           |
| lat          | string                        | yes      | Latitude (from `data-atlas-latlng`)            |
| lng          | string                        | yes      | Longitude (from `data-atlas-latlng`)           |
| features     | object (map of string→array)  | yes      | Map of facility heading → bullet list          |
| price        | array of PriceData            | yes      | 61-day pricing calendar by default             |

## Review

Returned by `scrape_hotel_reviews(url, max_pages)` — one element per `reviewCard` from Booking's `reviewListFrontend` GraphQL. The shape is whatever Booking returns inside `reviewCard`; common keys include:

| Field                  | Type             | Required | Notes                                          |
| ---------------------- | ---------------- | -------- | ---------------------------------------------- |
| guestName              | string \| null   | no       | Guest display name                             |
| reviewScore            | number \| null   | no       | Numeric review score                           |
| reviewTitle            | string \| null   | no       | Review headline                                |
| textDetails.positiveText | string \| null | no       | "What I liked" text                            |
| textDetails.negativeText | string \| null | no       | "What I didn't like" text                      |
| stayDate               | string \| null   | no       | Stay date string                               |
| createdDateTime        | string \| null   | no       | Review post timestamp                          |
| countryCode            | string \| null   | no       | Reviewer country                               |

(Other fields surface as-is from Booking's GraphQL — schemas allow unknown keys.)
