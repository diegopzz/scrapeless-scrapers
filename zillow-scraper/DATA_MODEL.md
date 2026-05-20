# Zillow data model

Zillow embeds two flavours of JSON in property pages — modern listings expose `__NEXT_DATA__` containing a `gdpClientCache` blob, while legacy ones expose `hdpApolloPreloadedData`. Both unwrap to the same `property` object. Search results come from the `/async-create-search-page-state` PUT endpoint, which returns a `cat1.searchResults.listResults` array. Field names below are verbatim from those payloads.

## SearchResult

One entry from `cat1.searchResults.listResults`. Zillow returns a wide schema; only the most common fields are listed — additional keys are passed through.

| Field             | Type    | Required | Notes                                                |
| ----------------- | ------- | -------- | ---------------------------------------------------- |
| zpid              | string  | yes      | Stable Zillow property id                            |
| id                | string  | no       | Alternate listing id                                 |
| detailUrl         | string  | yes      | Relative URL to the homedetails page                 |
| statusType        | string  | no       | `FOR_SALE`, `FOR_RENT`, `SOLD`, etc.                 |
| statusText        | string  | no       | Human label for the status badge                     |
| price             | string  | no       | Display string, e.g. `"$1,295,000"`                  |
| unformattedPrice  | number  | no       | Numeric price                                        |
| address           | string  | no       | Full street address                                  |
| addressStreet     | string  | no       | Street component                                     |
| addressCity       | string  | no       |                                                      |
| addressState      | string  | no       |                                                      |
| addressZipcode    | string  | no       |                                                      |
| beds              | number  | no       | Bedroom count                                        |
| baths             | number  | no       | Bathroom count                                       |
| area              | number  | no       | Living area in square feet                           |
| latLong           | object  | no       | `{ latitude, longitude }`                            |
| imgSrc            | string  | no       | Primary photo URL                                    |
| hasImage          | boolean | no       |                                                      |
| brokerName        | string  | no       | Listing brokerage                                    |
| listingType       | string  | no       |                                                      |
| isFeaturedListing | boolean | no       |                                                      |

## Property

Single property object — the value of `props.pageProps.componentProps.gdpClientCache[<key>].property` (modern) or the matching `ForSale.*.property` entry under `hdpApolloPreloadedData.apiCache` (legacy). Verbatim Zillow fields:

| Field                | Type   | Required | Notes                                              |
| -------------------- | ------ | -------- | -------------------------------------------------- |
| zpid                 | number | yes      | Numeric Zillow property id                         |
| streetAddress        | string | no       |                                                    |
| city                 | string | no       |                                                    |
| state                | string | no       |                                                    |
| zipcode              | string | no       |                                                    |
| country              | string | no       |                                                    |
| latitude             | number | no       |                                                    |
| longitude            | number | no       |                                                    |
| price                | number | no       | Numeric                                            |
| homeStatus           | string | no       | `FOR_SALE`, `RECENTLY_SOLD`, etc.                  |
| homeType             | string | no       | `SINGLE_FAMILY`, `CONDO`, …                        |
| bedrooms             | number | no       |                                                    |
| bathrooms            | number | no       |                                                    |
| livingArea           | number | no       | Square feet                                        |
| lotSize              | number | no       |                                                    |
| yearBuilt            | number | no       |                                                    |
| description          | string | no       |                                                    |
| hdpUrl               | string | no       | Canonical detail page path                         |
| photos               | list   | no       | List of `{ url, width, height, caption }`          |
| zestimate            | number | no       |                                                    |
| rentZestimate        | number | no       |                                                    |
| taxAssessedValue     | number | no       |                                                    |
| priceHistory         | list   | no       | Historical price events                            |
| schools              | list   | no       | Nearby schools                                     |
| attributionInfo      | object | no       | Agent + brokerage attribution                      |
| resoFacts            | object | no       | Bulky structured facts block                       |
| nearbyHomes          | list   | no       |                                                    |
