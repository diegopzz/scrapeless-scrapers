# Domain.com.au data model

Single source of truth for the Python (cerberus) and Node (zod) schemas under [`python/`](python/) and [`nodejs/`](nodejs/). Field names mirror the canonical  verbatim.

Domain.com.au emits two distinct property shapes depending on the URL:

- **Listed properties** (e.g. `/<address>-<id>`) → `componentProps` shape, projected by `parse_component_props`
- **Sold / property-profile pages** (e.g. `/property-profile/<address>`) → `__APOLLO_STATE__` shape, projected by `parse_page_props`

`scrape_properties(urls)` auto-detects the page type and emits the matching shape; both end up with a `url` field added.

## Property (listed)

| Field                 | Type           | Required | Notes                                            |
| --------------------- | -------------- | -------- | ------------------------------------------------ |
| listingId             | int            | yes      | Numeric Domain listing id                        |
| listingUrl            | string         | no       |                                                  |
| unitNumber            | string \| null | no       |                                                  |
| streetNumber          | string \| null | no       |                                                  |
| street                | string \| null | no       |                                                  |
| suburb                | string         | no       |                                                  |
| postcode              | string         | no       |                                                  |
| createdOn             | string         | no       | ISO timestamp                                    |
| propertyType          | string         | no       |                                                  |
| beds                  | number         | no       |                                                  |
| phone                 | string \| null | no       |                                                  |
| agencyName            | string         | no       |                                                  |
| propertyDeveloperName | string \| null | no       |                                                  |
| agencyProfileUrl      | string \| null | no       |                                                  |
| propertyDeveloperUrl  | string \| null | no       |                                                  |
| description           | array          | no       | Paragraph list extracted from the listing body   |
| loanfinder            | object \| null | no       |                                                  |
| schools               | list           | no       | `schoolCatchment.schools`                        |
| suburbInsights        | object         | no       |                                                  |
| gallery               | list           | no       |                                                  |
| listingSummary        | object         | no       | price, status, listing dates                     |
| agents                | list           | no       |                                                  |
| features              | list           | no       |                                                  |
| structuredFeatures    | list           | no       |                                                  |
| faqs                  | list           | no       |                                                  |
| url                   | string         | yes      | URL passed to `scrape_properties` (added post)   |

## PropertyProfile

Sold / profile-page shape. Emitted when the URL is a `/property-profile/<address>` page.

| Field        | Type         | Required | Notes                                |
| ------------ | ------------ | -------- | ------------------------------------ |
| propertyId   | string       | no       | Only present for property-profile pages |
| unitNumber   | string\|null | no       | `address.unitNumber`                 |
| streetNumber | string\|null | no       | `address.streetNumber`               |
| suburb       | string       | no       | `address.suburb`                     |
| postcode     | string       | no       | `address.postcode`                   |
| gallery      | list[string] | no       | URLs from `media(...)` keys          |
| url          | string       | yes      | URL passed in (added post)           |

## SearchItem

| Field         | Type           | Required | Notes                                                                |
| ------------- | -------------- | -------- | -------------------------------------------------------------------- |
| id            | int            | yes      | Domain listing/project id (numeric)                                  |
| listingType   | string         | no       | e.g. `"listing"`, `"project"`                                        |
| listingModel  | object         | no       | Card-level model (`skeletonImages` is stripped per the upstream reference upstream) |
