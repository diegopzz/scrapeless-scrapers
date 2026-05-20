# LinkedIn data model

**Public profiles only.** LinkedIn requires authentication for almost everything; this scraper covers the unauthenticated surfaces only (profile slugs, company pages, the jobs guest API, articles on `/pulse/`).

LinkedIn delivers most of its public data via JSON-LD (`<script type="application/ld+json">`); the company-life and jobs-list surfaces use plain HTML. the upstream reference keeps the JSON-LD schema.org keys untouched and adds a few extracted fields on top — we mirror that exactly.

## Profile

Returned by `scrape_profile(urls)` — one dict per URL.

| Field   | Type   | Required | Notes                                                                 |
| ------- | ------ | -------- | --------------------------------------------------------------------- |
| profile | object | yes      | schema.org `Person` from the JSON-LD `@graph` (name, worksFor, etc.). |
| posts   | list   | no       | schema.org `Article` objects from the same `@graph` when present.     |

## CompanyOverview

Returned by `scrape_company(urls)` — one dict per URL.

| Field             | Type   | Required | Notes                                                                       |
| ----------------- | ------ | -------- | --------------------------------------------------------------------------- |
| name              | string | yes      | From JSON-LD `Organization`.                                                |
| url               | string | yes      |                                                                             |
| mainAddress       | object | no       |                                                                             |
| description       | string | no       |                                                                             |
| numberOfEmployees | object | no       |                                                                             |
| logo              | object | no       | schema.org `ImageObject` (`contentUrl`, `description`, `@type`).            |
| ...               | mixed  | no       | Dynamic keys lifted from the about-us panel (Industry, Company size, etc.). |

## CompanyLife

Merged into the CompanyOverview dict when the `/life` variant is scraped.

| Field            | Type | Required | Notes                                                          |
| ---------------- | ---- | -------- | -------------------------------------------------------------- |
| leaders          | list | no       | `[{name, linkedinProfileLink}, ...]`                           |
| affiliatedPages  | list | no       | `[{name, industry, address, linkeinUrl}, ...]` (the upstream reference typo) |
| similarPages     | list | no       | `[{name, industry, address, linkeinUrl}, ...]`                 |

## JobSearch

Returned by `scrape_job_search(keyword, location, max_pages=None)`.

| Field         | Type | Required | Notes                                                                                              |
| ------------- | ---- | -------- | -------------------------------------------------------------------------------------------------- |
| data          | list | yes      | `[{title, company, address, timeAdded, jobUrl, companyUrl}, ...]`                                  |
| total_results | int  | no       | Total job count from the results-list header.                                                      |

## JobPage

Returned by `scrape_jobs(urls)` — one dict per URL.

| Field          | Type  | Required | Notes                                              |
| -------------- | ----- | -------- | -------------------------------------------------- |
| ...            | mixed | no       | schema.org `JobPosting` keys from JSON-LD (dynamic). |
| jobDescription | list  | no       | Cleaned `<ul>/<li>` text from the show-more panel. |

## Article

Returned by `scrape_articles(urls)` — one dict per URL.

| Field       | Type   | Required | Notes                                                       |
| ----------- | ------ | -------- | ----------------------------------------------------------- |
| ...         | mixed  | no       | schema.org `Article` keys from JSON-LD (dynamic).           |
| articleBody | string | no       | Concatenated paragraph text from `article-content-blocks`.  |
