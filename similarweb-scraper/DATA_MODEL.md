# Similarweb data model

Single source of truth for the Python (cerberus) and Node (zod) schemas under [`python/`](python/) and [`nodejs/`](nodejs/). Mirrors field names from  verbatim.

Similarweb is a React SPA. The richest data lives in a hidden `window.__APP_DATA__` script tag — easier and more stable to extract than the rendered DOM. All targets use `client.browser.create(...)` + Playwright/Puppeteer over CDP, then a regex / JMESPath pass over the embedded JSON.

## Website — emitted by `scrape_website` (one per domain)

`scrape_website` returns `data["layout"]["data"]` straight from the embedded payload. Top-level fields available on Similarweb's website overview page include:

| Field          | Type   | Required | Notes                                                              |
| -------------- | ------ | -------- | ------------------------------------------------------------------ |
| overview       | object | yes      | Domain, global rank, monthly visits, bounce rate, avg duration     |
| traffic        | object | no       | Time-series traffic and engagement metrics                         |
| trafficSources | object | no       | Breakdown across direct, search, social, referrals, mail, ads       |
| ranking        | object | no       | Global + country + category ranks                                  |
| demographics   | object | no       | Audience age/gender splits                                         |
| geography      | object | no       | Top countries by share of traffic                                  |
| competitors    | object | no       | Top similar / competing sites                                      |
| keywords       | object | no       | Top organic + paid keyword sets                                    |

Fields are mirrored verbatim from Similarweb's payload. Downstream code should rely on whichever subset is present for a given domain.

## CompareResult — emitted by `scrape_website_compare`

Returns `{ [first_domain]: WebsiteSubset, [second_domain]: WebsiteSubset }` where each value is the JMESPath-extracted subset:

| Field          | Type   | Required | Notes                       |
| -------------- | ------ | -------- | --------------------------- |
| overview       | object | yes      |                             |
| traffic        | object | no       |                             |
| trafficSources | object | no       |                             |
| ranking        | object | no       |                             |
| demographics   | object | no       |                             |
| geography      | object | no       |                             |

## Sitemaps — emitted by `scrape_sitemaps`

Returns `string[]` — the list of URLs extracted from `//url/loc/text()` after gunzip-decoding the sitemap.

## Trending — emitted by `scrape_trendings` (one per category URL)

Extracted from `script#dataset-json-ld` JSON-LD blocks.

| Field | Type    | Required | Notes                                                                       |
| ----- | ------- | -------- | --------------------------------------------------------------------------- |
| name  | string  | yes      | `mainEntity.name` — category label                                          |
| url   | string  | yes      | Category page URL                                                           |
| list  | object[]| yes      | `mainEntity.itemListElement` — top sites in the category, ranked            |
