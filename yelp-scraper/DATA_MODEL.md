# Yelp data model

## BusinessPage

Returned by `scrape_pages([url, ...])` — one dict per Yelp business profile URL.

| Field         | Type           | Required | Notes                                                              |
| ------------- | -------------- | -------- | ------------------------------------------------------------------ |
| name          | string         | yes      | `<h1>` text                                                        |
| website       | string         | no       | Business website link text (`""` if absent)                        |
| phone         | string         | no       | Display phone number (`""` if absent)                              |
| address       | string         | no       | Street address near "Get Directions" link                          |
| logo          | string         | no       | Business logo image URL                                            |
| claim_status  | string         | no       | Lowercased text like `"claimed"` / `"unclaimed"`                   |
| open_hours    | object<string> | yes      | Lower-cased weekday name -> display hours string (may be empty)    |

## Review

Returned by `scrape_reviews(url, max_reviews=...)` — list of reviews from Yelp's GraphQL `GetBusinessReviewFeed` endpoint. Field names mirror Yelp's payload verbatim via `jmespath`.

| Field                | Type    | Required | Notes                                                                                       |
| -------------------- | ------- | -------- | ------------------------------------------------------------------------------------------- |
| encid                | string  | yes      | Encoded review id                                                                            |
| text                 | object  | yes      | `{ full: string, language: string }`                                                         |
| rating               | integer | yes      | 1-5 stars                                                                                    |
| feedback             | object  | yes      | `{ coolCount: int, funnyCount: int, usefulCount: int }`                                      |
| author               | object  | yes      | `{ encid, displayName, displayLocation, reviewCount, friendCount, businessPhotoCount }`     |
| business             | object  | yes      | `{ encid, alias, name }`                                                                     |
| createdAt            | string  | yes      | ISO UTC datetime string (from `createdAt.utcDateTime`)                                       |
| businessPhotos       | list    | no       | `[{ encid, photoUrl, caption, helpfulCount }]`                                               |
| businessVideos       | list    | no       | Raw `businessVideos` array as Yelp returns it                                                |
| availableReactions   | list    | no       | `[{ displayText, reactionType, count }]`                                                     |

## SearchResult

Returned by `scrape_search(keyword, location, max_pages=...)` — raw `mainContentComponentsListProps` items from Yelp's `react-root-props` payload. Each entry has at least:

| Field                  | Type   | Required | Notes                                                  |
| ---------------------- | ------ | -------- | ------------------------------------------------------ |
| bizId                  | string | yes      | Encoded Yelp business id                               |
| searchResultBusiness   | object | yes      | Full business card payload (name, alias, rating, etc.) |
| ...                    | any    | no       | Additional fields Yelp ships in the search props       |
