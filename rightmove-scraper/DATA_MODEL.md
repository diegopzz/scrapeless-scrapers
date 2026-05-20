# Rightmove data model

Single source of truth for the Python (cerberus) and Node (zod) schemas under [`python/`](python/) and [`nodejs/`](nodejs/). Mirrors  verbatim.

Rightmove embeds the property cache inside a `window.PAGE_MODEL = { propertyData: {...} }` JS variable. the upstream reference walks the script with a small `find_json_objects` decoder and pulls the first object; its `propertyData` is then reduced via JMESPath. The search side calls a clean JSON endpoint (`/api/property-search/listing/search`) and the typeahead endpoint (`/los.rightmove.co.uk/typeahead`).

## Property

Output of the upstream reference's `parse_property` — JMESPath-reduced. Verbatim keys:

| Field                | Type    | Required | Notes                                                                |
| -------------------- | ------- | -------- | -------------------------------------------------------------------- |
| id                   | string  | yes      | Rightmove property id                                                |
| available            | boolean | no       | `status.published`                                                   |
| archived             | boolean | no       | `status.archived`                                                    |
| phone                | string  | no       | `contactInfo.telephoneNumbers.localNumber`                           |
| bedrooms             | number  | no       |                                                                      |
| bathrooms            | number  | no       |                                                                      |
| type                 | string  | no       | `transactionType` (`BUY`/`RENT`)                                     |
| property_type        | string  | no       | `propertySubType`                                                    |
| tags                 | list    | no       |                                                                      |
| description          | string  | no       | `text.description`                                                   |
| title                | string  | no       | `text.pageTitle`                                                     |
| subtitle             | string  | no       | `text.propertyPhrase`                                                |
| price                | string  | no       | `prices.primaryPrice` — already includes the currency symbol         |
| price_sqft           | string  | no       | `prices.pricePerSqFt`                                                |
| address              | object  | no       |                                                                      |
| latitude             | number  | no       | `location.latitude`                                                  |
| longitude            | number  | no       | `location.longitude`                                                 |
| features             | list    | no       | `keyFeatures`                                                        |
| history              | object  | no       | `listingHistory`                                                     |
| photos               | list    | no       | `[ { url, caption } ]`                                               |
| floorplans           | list    | no       | `[ { url, caption } ]`                                               |
| agency               | object  | no       | `{ id, branch, company, address, commercial, buildToRent, isNew }`   |
| industryAffiliations | list    | no       |                                                                      |
| nearest_airports     | list    | no       | `[ { name, distance } ]`                                             |
| nearest_stations     | list    | no       | `[ { name, distance } ]`                                             |
| sizings              | list    | no       | `[ { unit, min, max } ]`                                             |
| brochures            | list    | no       |                                                                      |

## SearchResult

Entry from the search API's `properties` array. Rightmove returns a wide schema; stable fields:

| Field                  | Type    | Required | Notes                                       |
| ---------------------- | ------- | -------- | ------------------------------------------- |
| id                     | number  | yes      |                                             |
| bedrooms               | number  | no       |                                             |
| bathrooms              | number  | no       |                                             |
| numberOfImages         | number  | no       |                                             |
| numberOfFloorplans     | number  | no       |                                             |
| numberOfVirtualTours   | number  | no       |                                             |
| summary                | string  | no       |                                             |
| displayAddress         | string  | no       |                                             |
| countryCode            | string  | no       |                                             |
| location               | object  | no       | `{ latitude, longitude }`                   |
| propertyImages         | object  | no       | `{ images, mainImageSrc, ... }`             |
| propertySubType        | string  | no       |                                             |
| listingUpdate          | object  | no       |                                             |
| premiumListing         | boolean | no       |                                             |
| price                  | object  | no       | `{ amount, currencyCode, ... }`             |
| customer               | object  | no       | Agent info                                  |
| transactionType        | string  | no       | `BUY` / `RENT`                              |
| propertyUrl            | string  | no       |                                             |

## LocationMatch

Output of `find_locations(query)` — strings of the form `"<type>^<id>"`, e.g. `"REGION^61294"`. Used as `location_id` for `scrape_search`.
