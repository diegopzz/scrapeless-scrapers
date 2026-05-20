# Redfin data model

Single source of truth for the Python (cerberus) and Node (zod) schemas under [`python/`](python/) and [`nodejs/`](nodejs/). Mirrors  verbatim.

Redfin exposes three distinct shapes:

- **Search** — JSONP response from `https://www.redfin.com/stingray/api/gis?...` prefixed with `{}&&`. Once stripped, the body is `{payload: {homes: [...]}}` — we return `homes` directly.
- **Property for sale** — HTML page; the upstream reference parses the visible DOM (no clean JSON), so we mirror their DOM-derived shape verbatim.
- **Property for rent** — HTML page whose `og:image` carries the rental UUID; we then call `https://www.redfin.com/stingray/api/v1/rentals/{rental_id}/floorPlans` and return its JSON verbatim.

## SearchResult

Entry from `payload.homes` — Redfin returns a wide schema; the most stable fields:

| Field              | Type    | Required | Notes                                                |
| ------------------ | ------- | -------- | ---------------------------------------------------- |
| propertyId         | number  | yes      | Stable Redfin property id                            |
| listingId          | number  | no       |                                                      |
| mlsId              | object  | no       | `{ value: string, ... }`                             |
| url                | string  | yes      | Relative homepage URL                                |
| price              | object  | no       | `{ value, level }`                                   |
| beds               | number  | no       |                                                      |
| baths              | number  | no       |                                                      |
| sqFt               | object  | no       | `{ value, level }`                                   |
| streetLine         | object  | no       | `{ value, level }`                                   |
| city               | string  | no       |                                                      |
| state              | string  | no       |                                                      |
| zip                | string  | no       |                                                      |
| latLong            | object  | no       | `{ value: { latitude, longitude } }`                 |
| photos             | object  | no       | `{ items: [...] }` first photo URLs                  |
| timeOnRedfin       | object  | no       |                                                      |
| keyFacts           | array   | no       |                                                      |
| propertyType       | number  | no       |                                                      |

## PropertyForSale

| Field                 | Type   | Required | Notes                                                       |
| --------------------- | ------ | -------- | ----------------------------------------------------------- |
| address               | string | yes      | Street + city/state/zip concatenation                       |
| description           | string | no       | Marketing remarks                                           |
| price                 | string | no       | Display string, e.g. `"$750,000"`                           |
| estimatedMonthlyPrice | string | no       | Display string                                              |
| propertyUrl           | string | yes      | The page URL                                                |
| attachments           | list   | no       | Image URLs from `img.widenPhoto`                            |
| details               | list   | no       | Strings from `div.keyDetails-value`                         |
| features              | object | no       | `{ "<group title>": ["<feature>", ...] }`                   |

## PropertyForRent

Pass-through of Redfin's `/stingray/api/v1/rentals/{id}/floorPlans` JSON. Stable top-level keys:

| Field                | Type   | Required | Notes                                  |
| -------------------- | ------ | -------- | -------------------------------------- |
| rentalId             | string | yes      | UUID Redfin assigns to a rental        |
| name                 | string | no       | Building name                          |
| status               | string | no       |                                        |
| floorPlans           | array  | no       |                                        |
| units                | array  | no       |                                        |
| amenities            | array  | no       |                                        |
| photos               | array  | no       |                                        |
| location             | object | no       | `{ latitude, longitude, address, ... }`|
