# Indeed data model

Indeed embeds two large JSON blobs in every page:

- Search pages — `window.mosaic.providerData["mosaic-provider-jobcards"]` (job card cards plus tier summaries).
- Job pages — `_initialData={...};` (a rich Indeed-internal nested model).

Both blobs are extracted with regex and surfaced **without renaming** so consumers see the same nested keys the upstream reference produces.

## SearchPage

Returned by `scrape_search()` — a flat list of Indeed's raw `JobCardModel` dicts (the upstream reference's `scrape_search` extends `results` across pages and returns the merged list verbatim; the intermediate `{results, meta}` wrapper is internal to `parse_search_page`).

Each list entry is one job card. Indeed's model is wide and A/B-tested, so only the universally-present keys are pinned; everything else is passed through.

| Field                 | Type    | Required | Notes                                                                                       |
| --------------------- | ------- | -------- | ------------------------------------------------------------------------------------------- |
| jobkey                | string  | no       | Indeed job key (used to build `/viewjob?jk=…`)                                              |
| title                 | string  | no       | Job title                                                                                   |
| displayTitle          | string  | no       | Display variant of title                                                                    |
| company               | string  | no       | Employer name (when not gated behind `companyBrandingAttributes`)                           |
| formattedLocation     | string  | no       | Display location                                                                            |
| formattedRelativeTime | string  | no       | e.g. `"5 days ago"`                                                                         |
| salarySnippet         | object  | no       | `{ text, currency, source }` — surfaced salary text                                         |
| extractedSalary       | object  | no       | `{ min, max, type }` parsed pay band                                                        |
| snippet               | string  | no       | HTML description preview                                                                    |
| jobTypes              | array   | no       | e.g. `["Full-time"]`                                                                        |
| link                  | string  | no       | Relative job link                                                                           |

## JobPage

Returned by `scrape_jobs()` — one entry per `job_key`. the upstream reference merges three sibling sub-models (`jobMetadataHeaderModel`, `jobTagModel`, `jobInfoHeaderModel`) into the top level alongside the `description`. Because Indeed A/B-tests the underlying models heavily, fields are pinned as optional and the merged dict is passed through verbatim.

| Field               | Type    | Required | Notes                                                                                       |
| ------------------- | ------- | -------- | ------------------------------------------------------------------------------------------- |
| description         | string  | no       | `jobInfoWrapperModel.jobInfoModel.sanitizedJobDescription` (HTML)                           |
| jobType             | string  | no       | From `jobMetadataHeaderModel`                                                               |
| jobNormTitle        | string  | no       | From `jobMetadataHeaderModel`                                                               |
| companyName         | string  | no       | From `jobInfoHeaderModel`                                                                   |
| formattedLocation   | string  | no       | From `jobInfoHeaderModel`                                                                   |
| jobTitle            | string  | no       | From `jobInfoHeaderModel`                                                                   |
| companyOverviewLink | string  | no       | From `jobInfoHeaderModel`                                                                   |
