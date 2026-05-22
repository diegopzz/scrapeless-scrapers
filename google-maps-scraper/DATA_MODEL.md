# Google Maps data model

Two object kinds are emitted:

- `places.json` → array of `Place` summaries, parsed from the search-results feed (`[role='feed'] [role='article']`) on a `/maps/search/<query>` page.
- `place.json` → single `Place` detail, parsed from the place panel (`h1`, `aria-label` anchors) on a `/maps/place/<slug>/<coords>` page.

Both kinds share the same `Place` shape; the list kind populates fewer optional fields.

## Place

| Field        | Type    | Required | Notes                                                                         |
| ------------ | ------- | -------- | ----------------------------------------------------------------------------- |
| name         | string  | yes      | Place name from `h1` (detail) or card heading (list)                          |
| category     | string  | no       | Primary category — `button.DkEaL` text (detail) or card text line            |
| address      | string  | no       | Street address from `[aria-label^="Address: "]`                               |
| phone        | string  | no       | Phone from `[aria-label^="Phone: "]`                                          |
| website      | string  | no       | Website from `[aria-label^="Website: "]`                                      |
| rating       | number  | no       | Numeric star rating (e.g. 4.5) — parsed from `div.F7nice` text or card text  |
| review_count | integer | no       | Review count — parsed from `[aria-label*="reviews"]`                          |
| price_level  | string  | no       | Price tier string (e.g. "$1–10") parsed from card or body text                |
| description  | string  | no       | Short editorial description, when present in the body text                    |
| url          | string  | yes      | Canonical Google Maps place URL                                               |
