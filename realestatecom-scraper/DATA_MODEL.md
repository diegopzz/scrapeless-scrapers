# Realestate.com.au data model

Single source of truth for the Python (cerberus) and Node (zod) schemas under [`python/`](python/) and [`nodejs/`](nodejs/). Field names mirror the canonical  verbatim.

Both `scrape_properties` and `scrape_search` emit the same `Property` shape (search items go through the same `parse_property_data` projection).

## Property

| Field             | Type             | Required | Notes                                                                                       |
| ----------------- | ---------------- | -------- | ------------------------------------------------------------------------------------------- |
| id                | string           | yes      | realestate.com.au listing id                                                                |
| propertyType      | string \| null   | no       | From `propertyType.display`                                                                 |
| description       | string \| null   | no       |                                                                                             |
| propertyLink      | string \| null   | no       | From `_links.canonical.href`                                                                |
| address           | object \| null   | no       | Raw address object (suburb, postcode, state, display)                                       |
| propertySizes     | object \| null   | no       | Land / building size with units                                                             |
| generalFeatures   | object \| null   | no       | beds, baths, parking, studies, etc.                                                         |
| propertyFeatures  | list \| null     | no       | List of `{featureName, value}` (renamed from `displayLabel`)                                |
| images            | list[string]     | no       | `media.images[].templatedUrl` — substitute `{size}` segment for resolution                  |
| videos            | any \| null      | no       | Raw                                                                                         |
| floorplans        | any \| null      | no       | Raw                                                                                         |
| listingCompany    | object \| null   | no       | `{name, id, companyLink, phoneNumber, address, ratingsReviews, description}`                |
| listers           | list \| null     | no       | Agent objects                                                                               |
| auction           | any \| null      | no       | Auction details if listing is for auction                                                   |

## SearchResult

Same shape as `Property` — `scrape_search` projects each `results.exact.items[].listing` through `parse_property_data`.
