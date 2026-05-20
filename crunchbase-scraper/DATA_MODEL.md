# Crunchbase data model

Single source of truth for the Python (cerberus) and Node (zod) schemas under [`python/`](python/) and [`nodejs/`](nodejs/). Mirrors field names from  verbatim.

Crunchbase is an Angular app. State arrives as JSON inside `<script id="ng-state">` (newer pages) or `<script id="client-app-state">` (legacy). All parsers target that embedded payload — the rendered DOM is unstable. All targets use `client.browser.create(...)` + Playwright/Puppeteer over CDP.

## CompanyData — emitted by `scrape_company` (one per `/organization/<slug>/...` URL)

| Field        | Type     | Required | Notes                                                        |
| ------------ | -------- | -------- | ------------------------------------------------------------ |
| organization | object   | yes      | Reduced organization dataset (see fields below)              |
| employees    | object[] | yes      | Employee/contact rows scraped from the People tab            |

### `organization` fields

`id`, `name`, `logo`, `description`, `linkedin`, `facebook`, `twitter`, `email`, `phone`, `website`, `ipo_status`, `rank_org_company`, `semrush_global_rank`, `semrush_visits_latest_month`, `semrush_id`, `categories`, `legal_name`, `operating_status`, `last_funding_type`, `founded_on`, `location_groups`, `trademarks`, `trademark_popular_class`, `patents`, `patent_popular_category`, `investments`, `investors`, `acquisitions`, `contacts`, `funding_total_usd`, `stock_symbol`, `exits`, `similar_orgs`, `current_positions`, `investors_lead`, `investments_lead`, `funding_rounds`, `event_appearances`, `advisors`, `buildwith_tech_used`, `timeline`, `events`, `similar`.

Nested shapes mirror Crunchbase's payload verbatim — for example `investments[]` carries `raised_usd`, `name`, `organization`, `announced_on`, `is_lead_investor`; `funding_rounds[]` carries `announced_on`, `raised_usd`, `investors`, `lead_investors[]`; `timeline[]` carries `title`, `author`, `publisher`, `url`, `thumb`, `date`, `type`.

### `employees[]` fields

`name`, `linkedin`, `job_levels`, `job_departments`.

## PersonData — emitted by `scrape_person` (one per `/person/<slug>` URL)

Top-level keys: `name`, `title`, `description`, `type`, `gender`, `location_groups`, `location`, `current_jobs`, `past_jobs`, `linkedin`, `twitter`, `facebook`, `current_advisor_jobs`, `founded_orgs`, `portfolio_orgs`, `rank_principal_investor`.

Nested shapes:

- `education[]` → `school`, `type`
- `timeline[]`
- `investments[].identifier`, `investments[].organization_identifier`, `investments[].funding_round_identifier` — each carrying `uuid`, `value`, `permalink`, `entity_def_id`
- `exits[]` → `name`, `short_description`
