# Immobilienscout24 data model

Single source of truth for the Python (cerberus) and Node (zod) schemas under [`python/`](python/) and [`nodejs/`](nodejs/). The Scrapeless implementation mirrors the field names emitted by  verbatim.

Immobilienscout24 is a German real estate portal. Both `scrape_properties()` and `scrape_search()` emit the same per-listing shape (the search variant scrapes detail pages discovered via the search results).

## PropertyResult

Returned by `scrape_properties(urls)` and per-item by `scrape_search(url, scrape_all_pages, max_scrape_pages)`.

| Field         | Type           | Required | Notes                                                                |
| ------------- | -------------- | -------- | -------------------------------------------------------------------- |
| id            | string         | yes      | Listing ID from canonical URL                                        |
| title         | string         | yes      | `h1#expose-title`                                                    |
| description   | string         | no       | Meta description                                                     |
| address       | string         | no       | From `.address-block` span                                           |
| propertyLlink | string         | yes      | Canonical URL (typo verbatim from the upstream reference)                          |
| propertySepcs | object         | yes      | Spec dict (typo verbatim from the upstream reference)                              |
| price         | object         | yes      | Price components, see below                                          |
| building      | object         | yes      | Building info (year, energy)                                         |
| attachments   | object         | yes      | Images + video flag                                                  |
| agencyName    | string \| null | no       | `[data-qa='companyName']`                                            |
| agencyAddress | string \| null | no       | Agency address line                                                  |

### propertySepcs (nested)

| Field                  | Type           | Notes                                            |
| ---------------------- | -------------- | ------------------------------------------------ |
| floorsNumber           | string \| null | `.etage`                                         |
| livingSpace            | string \| null | `.wohnflaeche`                                   |
| livingSpaceUnit        | string \| null | Unit token (e.g. `"m²"`)                         |
| vacantFrom             | string \| null | `.bezugsfrei`                                    |
| numberOfRooms          | string \| null | `.zimmer`                                        |
| Garage/parking space   | string \| null | `.garage-stellplatz` (key verbatim from the upstream reference)|
| additionalSpecs        | array          | Any extra spec rows                              |
| internetAvailable      | boolean        | From `.mediaavailcheck`                          |

### price (nested)

| Field                | Type           | Notes                                       |
| -------------------- | -------------- | ------------------------------------------- |
| priceWithoutHeadting | string \| null | `.kaltmiete` (typo verbatim from the upstream reference)  |
| priceperMeter        | string \| null | Price per m² (typo verbatim from the upstream reference)  |
| additionalCosts      | string \| null |                                             |
| heatingCosts         | string \| null |                                             |
| totalRent            | string \| null |                                             |
| basisRent            | string \| null |                                             |
| deposit              | string \| null |                                             |
| garage/parkingRent   | string \| null | (key verbatim from the upstream reference)                |
| priceCurrency        | string \| null | Currency extracted from price text          |

### building (nested)

| Field                      | Type           | Notes                                                |
| -------------------------- | -------------- | ---------------------------------------------------- |
| constructionYear           | string \| null | `.baujahr`                                           |
| energySources              | string \| null |                                                      |
| energyCertificate          | string \| null | `.energieausweis`                                    |
| energyCertificateType      | string \| null |                                                      |
| energyCertificateDate      | string \| null |                                                      |
| finalEnergyRrequirement    | string \| null | `.endenergiebedarf` (typo verbatim from the upstream reference)    |

### attachments (nested)

| Field          | Type             | Notes                                  |
| -------------- | ---------------- | -------------------------------------- |
| propertyImages | array of strings | Gallery `data-src` values              |
| videoAvailable | boolean          | True if `.sp-video` present            |
