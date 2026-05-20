# Zoopla data model

Single source of truth for the Python (cerberus) and Node (zod) schemas under [`python/`](python/) and [`nodejs/`](nodejs/). Mirrors  verbatim.

Zoopla's property pages don't expose a clean JSON cache; the upstream reference extracts data directly from the rendered DOM. Search pages embed totals inside `<script id="__ZAD_TARGETING__">` JSON.

## Property

Output of the upstream reference's `parse_property`. Verbatim keys:

| Field                  | Type   | Required | Notes                                                |
| ---------------------- | ------ | -------- | ---------------------------------------------------- |
| id                     | number | no       | Pulled from `og:url` path                            |
| url                    | string | yes      | `og:url`                                             |
| title                  | string | no       | `<title>` text                                       |
| address                | string | no       | `<address>` text                                     |
| price                  | object | no       | `{ amount: number, currency: "£" }`                  |
| gallery                | list   | no       | Image URLs from `[data-key=gallery] picture source`  |
| epcRating              | string | no       | EPC rating string                                    |
| floorArea              | string | no       | Floor area string (sq ft)                            |
| numOfReceptions        | number | no       |                                                      |
| numOfBathrooms         | number | no       |                                                      |
| numOfBedrooms          | number | no       |                                                      |
| propertyTags           | list   | no       |                                                      |
| propertyInfo           | list   | no       | `[ { title, value } ]` from the key-info section     |
| propertyDescription    | list   | no       | List of `<span>` texts inside `about` section        |
| coordinates            | object | no       | `{ googleMapeSource, latitude, longitude }` (sic — verbatim from the upstream reference) |
| nearby                 | list   | no       | `[ { title, distance, unit } ]`                      |
| agent                  | object | no       | `{ name, logo, url }`                                |

## SearchResult

Entry from `parse_search`. Verbatim keys:

| Field          | Type    | Required | Notes                                                   |
| -------------- | ------- | -------- | ------------------------------------------------------- |
| price          | number  | no       | Numeric £ amount                                         |
| priceCurrency  | string  | no       | Literal `"Sterling pound £"` (verbatim from the upstream reference)   |
| url            | string  | no       | Absolute URL                                            |
| image          | string  | no       | First photo URL                                          |
| address        | string  | no       |                                                          |
| squareFt       | number  | no       |                                                          |
| numBathrooms   | number  | no       |                                                          |
| numBedrooms    | number  | no       |                                                          |
| numLivingRoom  | number  | no       |                                                          |
| description    | string  | no       |                                                          |
| justAdded      | boolean | no       |                                                          |
| agency         | string  | no       | Logo alt text                                            |
