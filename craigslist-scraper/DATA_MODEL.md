# Craigslist data model

Single source of truth for the Python (cerberus) and Node (zod) schemas under [`python/`](python/) and [`nodejs/`](nodejs/).

Craigslist surfaces two primary shapes — search-result cards on city/category pages and standalone listing detail pages.

## SearchResult

Returned by `scrape_search(city, category, query, max_pages)` — one element per `.cl-search-result[data-pid]` gallery card.

| Field    | Type            | Required | Notes                                              |
| -------- | --------------- | -------- | -------------------------------------------------- |
| id       | string          | yes      | `data-pid` posting id                              |
| title    | string          | yes      | Posting title (`a.posting-title span.label`)       |
| url      | string          | yes      | Absolute listing URL                               |
| price    | string \| null  | no       | Display string, e.g. `"$139"`                      |
| location | string \| null  | no       | Neighborhood / area label                          |
| postedAt | string \| null  | no       | Human-readable freshness (e.g. `"<1hr ago"`)       |
| image    | string \| null  | no       | First thumbnail URL                                |

## Listing

Returned by `scrape_listing(url)` — one object per Craigslist listing detail page.

| Field       | Type             | Required | Notes                                                       |
| ----------- | ---------------- | -------- | ----------------------------------------------------------- |
| id          | string           | yes      | Numeric posting id from the URL                             |
| url         | string           | yes      | Canonical listing URL                                       |
| title       | string           | yes      | `#titletextonly` text                                       |
| price       | string \| null   | no       | `span.price` text (e.g. `"$139"`)                           |
| location    | string \| null   | no       | Parenthetical location after the title                      |
| postedAt    | string \| null   | no       | Posting timestamp from `time.date.timeago[datetime]`        |
| description | string           | yes      | `#postingbody` plain-text body                              |
| attributes  | array of strings | yes      | Bullet items from `p.attrgroup span`                        |
| images      | array of strings | yes      | `#thumbs a[href]` gallery URLs                              |
| latitude    | string \| null   | no       | `div#map[data-latitude]`                                    |
| longitude   | string \| null   | no       | `div#map[data-longitude]`                                   |
| section     | string \| null   | no       | Crumb section (e.g. `"for sale"`)                           |
| category    | string \| null   | no       | Crumb category (e.g. `"bicycles - by owner"`)               |
