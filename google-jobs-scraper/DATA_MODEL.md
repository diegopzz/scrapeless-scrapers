# Google Jobs data model

One object kind is emitted:

- `jobs.json` → array of `JobListing`, parsed from the Google Jobs panel that appears in the SERP
  when a job-related query is made. The panel renders inside the standard search result page —
  no special `ibp=htl;jobs` endpoint is required. Data comes from the visible card text
  (title, company, location • via source, time ago, salary, job type).

## JobListing

| Field      | Type    | Required | Notes                                                                         |
| ---------- | ------- | -------- | ----------------------------------------------------------------------------- |
| title      | string  | yes      | Job title as shown in the card heading                                        |
| company    | string  | yes      | Employer name                                                                 |
| location   | string  | no       | City, State (e.g. "Austin, TX")                                               |
| source     | string  | no       | Job board / site name after "via" (e.g. "LinkedIn", "ZipRecruiter")          |
| posted_at  | string  | no       | Relative time string (e.g. "21 hours ago", "3 days ago")                     |
| salary     | string  | no       | Salary/rate string as shown (e.g. "70–75 an hour", "$120,000 a year")        |
| job_type   | string  | no       | Employment type (e.g. "Full-time", "Contractor", "Part-time")                |
| url        | string  | no       | Direct link to the posting when available (null if not exposed in the card)  |
