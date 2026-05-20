# Xbox data model

Two object kinds are emitted:

- `product.json` → single `Product` parsed from the schema.org `@graph` Product/VideoGame node in the `/games/store/<slug>/<storeId>` page's `ld+json`.
- `search.json` → list of `SearchResult` parsed from the rendered tiles on `/games/all-games` (and other discovery pages). Tiles expose a stable `<a href="/games/store/<slug>/<id>">` with an inner image + title.

## Product

| Field         | Type    | Required | Notes                                                                  |
| ------------- | ------- | -------- | ---------------------------------------------------------------------- |
| id            | string  | yes      | Microsoft Store product ID (last URL segment, e.g. `9N8PMW7QMD3D`)     |
| name          | string  | yes      | `ld+json` Product `name`                                               |
| description   | string  | no       | `ld+json` Product `description`                                        |
| url           | string  | yes      | Canonical product URL                                                  |
| image         | string  | no       | First image URL                                                        |
| publisher     | string  | no       | `ld+json` Product `publisher.name`                                     |
| developer     | string  | no       | `ld+json` Product `creator.name`                                       |
| brand         | string  | no       | `ld+json` Product `brand.name`                                         |
| genre         | array   | yes      | `ld+json` Product `genre` (list of strings)                            |
| platforms     | array   | yes      | `ld+json` Product `gamePlatform`                                       |
| contentRating | string  | no       | `ld+json` Product `contentRating` (e.g. `ESRB TEEN`)                   |
| releaseDate   | string  | no       | `ld+json` Product `datePublished`                                      |
| ratingValue   | number  | no       | `ld+json` `aggregateRating.ratingValue`                                |
| ratingCount   | number  | no       | `ld+json` `aggregateRating.ratingCount`                                |
| price         | string  | no       | First offer `price`                                                    |
| priceCurrency | string  | no       | First offer `priceCurrency`                                            |
| availability  | string  | no       | First offer `availability`                                             |
| isFree        | boolean | no       | `ld+json` Product `isAccessibleForFree`                                |
| featureList   | string  | no       | `ld+json` Product `featureList` (comma-separated)                      |
| videos        | array   | yes      | Trailer entries `{name, thumbnailUrl, contentUrl}` (may be empty)      |

## SearchResult

| Field   | Type   | Required | Notes                                                  |
| ------- | ------ | -------- | ------------------------------------------------------ |
| id      | string | yes      | Microsoft Store product ID                             |
| slug    | string | yes      | URL slug                                               |
| name    | string | yes      | Tile title (`aria-label` first sentence + inner text)  |
| url     | string | yes      | Absolute product URL                                   |
| image   | string | no       | Tile artwork URL                                       |
| badge   | string | no       | Tile badge text (e.g. `AVAILABLE WITH GAME PASS`)      |
