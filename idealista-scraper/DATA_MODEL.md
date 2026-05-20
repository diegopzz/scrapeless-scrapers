# Idealista data model

Idealista is a Spanish real estate portal — listings are scraped via three distinct shapes: property detail pages, search result cards, and province → municipality URL lists.

## PropertyResult

Returned by `scrape_properties(urls)` — one per property detail page.

| Field         | Type                  | Required | Notes                                                         |
| ------------- | --------------------- | -------- | ------------------------------------------------------------- |
| url           | string                | yes      | Canonical property URL                                        |
| title         | string                | yes      | From `h1 .main-info__title-main`                              |
| location      | string                | yes      | From `.main-info__title-minor`                                |
| price         | integer               | yes      | Numeric price in listing currency (commas stripped)           |
| currency      | string                | yes      | Currency symbol (e.g. `"€"`)                                  |
| description   | string                | yes      | Concatenated paragraphs from `div.comment`                    |
| updated       | string                | no       | Last-update date string (after `" on "` from stats text)      |
| features      | object                | yes      | Mapping of feature heading → list of bullet strings           |
| images        | object                | yes      | Mapping of image tag → list of fullscreen image URLs          |
| plans         | array of strings      | yes      | Floor-plan URLs from the `isPlan: true` gallery entries       |

## SearchResult

Returned by `scrape_search(url, max_scrape_pages)` — one per card on the search list.

| Field                | Type             | Required | Notes                                              |
| -------------------- | ---------------- | -------- | -------------------------------------------------- |
| title                | string           | yes      | Card title                                         |
| link                 | string           | yes      | Absolute URL to property detail                    |
| picture              | string \| null   | no       | First-image URL                                    |
| price                | integer          | yes      | Numeric price                                      |
| currency             | string           | yes      | Currency symbol                                    |
| parking_included     | boolean          | yes      | Parking flag from the card                         |
| details              | array of strings | yes      | Spec bullets (rooms, m², floor, etc.)              |
| description          | string           | yes      | Truncated description shown on the card            |
| tags                 | array of strings | yes      | Coloured tag labels                                |
| listing_company      | string \| null   | no       | Agency/branded-owner name                          |
| listing_company_url  | string \| null   | no       | Agency profile URL                                 |

## ProvinceURL

Returned by `scrape_provinces(urls)` — flat list of municipality search URLs.

| Field | Type   | Required | Notes                                       |
| ----- | ------ | -------- | ------------------------------------------- |
| url   | string | yes      | Absolute municipality search-results URL    |
