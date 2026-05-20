# Glassdoor data model

## Job

Returned by `scrape_jobs(url, max_pages=...)` — one entry per `div.jobCard JobCard` on `/Jobs/...htm` pages.

| Field        | Type   | Required | Notes                                            |
| ------------ | ------ | -------- | ------------------------------------------------ |
| jobTitle     | string | yes      | Job title text                                   |
| jobLink      | string | no       | Job detail page URL                              |
| job_location | string | no       | `data-test="emp-location"` value (sic underscore)|
| jobSalary    | string | no       | `data-test="detailSalary"` value (may be null)   |
| jobDate      | string | no       | `data-test="job-age"` value                      |

## Review

Returned by `scrape_reviews(url, max_pages=...)` — list of review objects from Glassdoor's `/bff/employer-profile-mono/employer-reviews` API, mirroring `data.employerReviews.reviews`.

| Field                        | Type    | Required | Notes                                                   |
| ---------------------------- | ------- | -------- | ------------------------------------------------------- |
| reviewId                     | integer | yes      | Glassdoor review id                                     |
| ratingOverall                | integer | yes      | 1-5 overall rating                                      |
| ratingCeo                    | string  | no       | e.g. `"APPROVE"`                                        |
| ratingBusinessOutlook        | string  | no       |                                                         |
| ratingWorkLifeBalance        | integer | no       | 1-5                                                     |
| ratingCultureAndValues       | integer | no       |                                                         |
| ratingDiversityAndInclusion  | integer | no       |                                                         |
| ratingCareerOpportunities    | integer | no       |                                                         |
| ratingCompensationAndBenefits| integer | no       |                                                         |
| ratingSeniorLeadership       | integer | no       |                                                         |
| ratingRecommendToFriend      | string  | no       | e.g. `"POSITIVE"`                                       |
| reviewDateTime               | string  | yes      | ISO datetime                                            |
| isCurrentJob                 | boolean | no       |                                                         |
| lengthOfEmployment           | integer | no       | Years                                                   |
| employmentStatus             | string  | no       | e.g. `"REGULAR"`                                        |
| jobTitle                     | object  | no       | `{ text }`                                              |
| location                     | object  | no       | `{ name, type }`                                        |
| pros                         | string  | no       | Free text                                               |
| cons                         | string  | no       | Free text                                               |
| summary                      | string  | no       | Headline                                                |
| advice                       | string  | no       | Advice to management                                    |
| countHelpful                 | integer | no       |                                                         |
| countNotHelpful              | integer | no       |                                                         |
| ...                          | any     | no       | Other fields Glassdoor returns                          |

## Salary

`scrape_salaries(url, max_pages=...)` returns a dict shaped like Glassdoor's salaries payload:

| Field         | Type    | Required | Notes                                          |
| ------------- | ------- | -------- | ---------------------------------------------- |
| results       | list    | yes      | List of salary items (see below)               |
| numPages      | integer | yes      | Total pagination pages                         |
| salaryCount   | integer | yes      | Count of `results`                             |
| jobTitleCount | integer | yes      | Total job titles for this employer             |

## SalaryItem

Shape of each entry inside `Salary.results`. Nested keys are written with dot notation in the Notes column rather than as field names, since the offline validator parses field names literally.

| Field             | Type    | Required | Notes                                                                                       |
| ----------------- | ------- | -------- | ------------------------------------------------------------------------------------------- |
| jobTitle          | object  | yes      | `{ text: string }` — job title wrapper                                                      |
| salaryCount       | integer | yes      | `Salaries submitted` count for this title                                                   |
| basePayStatistics | object  | yes      | `{ percentiles: [{ ident: "min" \| "max", value: number }] }` — base pay percentile band    |

## FoundCompany

Returned by `find_companies(query)` — uses Glassdoor's `/autocomplete/employers` endpoint.

| Field      | Type    | Required | Notes                       |
| ---------- | ------- | -------- | --------------------------- |
| name       | string  | yes      | Display name                |
| id         | integer | yes      | Glassdoor employer id       |
| shortName  | string  | no       |                             |
| logoURL    | string  | no       |                             |
| websiteURL | string  | no       |                             |
