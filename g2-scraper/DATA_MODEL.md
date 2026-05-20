# G2 data model

## SearchResult

Returned by `scrape_search(url, max_scrape_pages=...)` — one entry per product card on `/search?query=...` pages.

| Field         | Type           | Required | Notes                                             |
| ------------- | -------------- | -------- | ------------------------------------------------- |
| name          | string         | yes      | Product name                                      |
| link          | string         | yes      | Absolute link to product page on g2.com           |
| image         | string         | no       | Product avatar image URL                          |
| rate          | number         | no       | 0-5 average rating                                |
| reviewsNumber | integer        | no       | Total reviews count                               |
| description   | string         | no       | Short product description                         |
| categories    | list<string>   | yes      | Category tags shown on the card                   |

## Review

Returned by `scrape_reviews(url, max_review_pages=...)`. Each entry has two sub-objects: `author` and `review`.

### Review.author

| Field             | Type   | Required | Notes                                           |
| ----------------- | ------ | -------- | ----------------------------------------------- |
| authorName        | string | no       | Reviewer display name                           |
| authorProfile     | string | no       | Link to reviewer's G2 profile                   |
| authorPosition    | string | no       | Job title                                       |
| authorCompanySize | string | no       | e.g. `"51-200 emp."`                            |

### Review.review

| Field          | Type         | Required | Notes                                          |
| -------------- | ------------ | -------- | ---------------------------------------------- |
| reviewTags     | list<string> | yes      | Reviewer-applied tags                          |
| reviewData     | string       | no       | ISO date string from `meta[itemprop=datePublished]` (mirrors the upstream reference's typo `reviewData`) |
| reviewRate     | number       | no       | 1-5                                            |
| reviewTitle    | string       | no       | Review title with surrounding quotes stripped  |
| reviewLikes    | string       | no       | "What do you like best?" answer text           |
| reviewDislikes | string       | no       | "What do you dislike?" answer text             |

## Alternative

Returned by `scrape_alternatives(product, alternatives="")` — items from `/products/<slug>/competitors/alternatives/<segment>` pages.

| Field            | Type   | Required | Notes                                                  |
| ---------------- | ------ | -------- | ------------------------------------------------------ |
| name             | string | yes      | Product name                                           |
| link             | string | yes      | Absolute g2.com product link                           |
| ranking          | integer| no       | Position in the alternatives list                      |
| numberOfReviews  | integer| no       | Reviews count                                          |
| rate             | number | no       | 0-5 average rating                                     |
| description      | string | no       | Short description                                      |
