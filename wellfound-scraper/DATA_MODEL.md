# Wellfound data model

Wellfound (formerly AngelList) is a Next.js/Apollo app. Public company and search data is hydrated into `<script id="__NEXT_DATA__">` under `props.pageProps.apolloState.data`. the upstream reference walks the Apollo graph and emits each company node verbatim — same keys, same casing (including `remtoe` from the upstream graph).

## JobData

Sub-object embedded under `CompanyData.highlightedJobListings`.

| Field            | Type   | Required | Notes                                         |
| ---------------- | ------ | -------- | --------------------------------------------- |
| id               | string | yes      |                                               |
| title            | string | yes      |                                               |
| slug             | string | yes      |                                               |
| remtoe           | bool   | no       | the upstream reference-upstream typo of `remote`; preserved |
| primaryRoleTitle | string | no       |                                               |
| locationNames    | object | no       |                                               |
| liveStartAt      | int    | no       | Unix seconds.                                 |
| jobType          | string | no       |                                               |
| description      | string | no       |                                               |

## CompanyData

Returned by `scrape_search(role, location, max_pages)` and `scrape_companies(urls)` (one dict per URL).

| Field                  | Type        | Required | Notes                                |
| ---------------------- | ----------- | -------- | ------------------------------------ |
| id                     | string      | yes      | Apollo node id.                      |
| name                   | string      | yes      |                                      |
| slug                   | string      | yes      |                                      |
| badges                 | list        | no       |                                      |
| companySize            | string      | no       |                                      |
| highConcept            | string      | no       | One-liner tagline.                   |
| logoUrl                | string      | no       |                                      |
| highlightedJobListings | list[Job]   | no       | Each entry follows the JobData table.|

Additional Apollo fields surface verbatim when present (the upstream reference notes "there are more fields, but these are basic ones").
