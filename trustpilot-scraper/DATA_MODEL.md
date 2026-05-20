# Trustpilot data model

Every shape below comes straight from Trustpilot's Next.js hydration payload (`__NEXT_DATA__.props.pageProps`), so any field Trustpilot ships is passed through unchanged.

## Company

Returned by `scrape_company([url, ...])` — one entry per `/review/<domain>` page.

| Field           | Type   | Required | Notes                                                            |
| --------------- | ------ | -------- | ---------------------------------------------------------------- |
| pageUrl         | string | yes      | Canonical page URL from `pageProps.pageUrl`                       |
| companyDetails  | object | yes      | Trustpilot's `businessUnit` object (id, displayName, stars, etc.) |
| reviews         | list   | yes      | First page of company reviews as Trustpilot emits them            |

## SearchResult (Business)

Returned by `scrape_search(url, max_pages=...)` — one entry per business card from `pageProps.businessUnits.businesses` on `/categories/<slug>` pages.

| Field                | Type   | Required | Notes                                                                   |
| -------------------- | ------ | -------- | ----------------------------------------------------------------------- |
| identifyingName      | string | yes      | Trustpilot identifier slug                                              |
| displayName          | string | yes      | Display business name                                                   |
| trustScore           | number | no       | 0-5 score                                                               |
| numberOfReviews      | object | no       | `{ total, oneStar, twoStars, threeStars, fourStars, fiveStars }`        |
| stars                | number | no       | Star rating 1-5                                                         |
| ...                  | any    | no       | Other fields Trustpilot ships in the businesses array                   |

## Review

Returned by `scrape_reviews(url, max_pages=...)` — paginated reviews from Trustpilot's Next.js data API (`/_next/data/<buildId>/review/<host>.json`).

| Field            | Type   | Required | Notes                                                                            |
| ---------------- | ------ | -------- | -------------------------------------------------------------------------------- |
| id               | string | yes      | Review id                                                                        |
| consumer         | object | yes      | `{ id, displayName, countryCode, numberOfReviews, ... }`                          |
| rating           | number | yes      | 1-5                                                                              |
| title            | string | no       |                                                                                  |
| text             | string | no       | Body text                                                                        |
| labels           | object | no       | Trustpilot label flags                                                           |
| dates            | object | yes      | `{ experiencedDate, publishedDate, updatedDate }`                                |
| reportData       | object | no       |                                                                                  |
| language         | string | no       | ISO code                                                                         |
| location         | object | no       |                                                                                  |
| ...              | any    | no       | Trustpilot may add new fields; passthrough                                       |
