# YellowPages data model

YellowPages search results carry a JSON-LD `ItemList` (second `<script type="application/ld+json">` block on the page); business detail pages use CSS selectors throughout.

## SearchPage

Returned by `scrape_search(query, location, max_pages)` — one dict per page.

| Field       | Type | Required | Notes                                                            |
| ----------- | ---- | -------- | ---------------------------------------------------------------- |
| data        | list | yes      | Items from the page's JSON-LD `ItemList` (`itemListElement.item`). |
| total_pages | int  | no       | Parsed from the pagination footer (`of N`).                      |

Each `data` entry is a schema.org `LocalBusiness`-ish item — keys come directly from YellowPages' JSON-LD.

## BusinessPage

Returned by `scrape_pages(urls)` — one dict per URL.

| Field        | Type   | Required | Notes                                                                  |
| ------------ | ------ | -------- | ---------------------------------------------------------------------- |
| name         | string | yes      | `h1.business-name`                                                     |
| categories   | list   | no       | `.categories > a` text                                                 |
| rating       | string | no       | Class-derived rating, e.g. `"four half"`                               |
| ratingCount  | string | no       | `.ratings .count` text                                                 |
| phone        | string | no       | `.phone[href]` (tel: stripped)                                         |
| website      | string | no       | `.website-link[href]`                                                  |
| address      | string | no       | `.address` text                                                        |
| workingHours | object | no       | `{ "Mon": "08:00-17:00", ... }` from `.open-details tr time[datetime]` |
