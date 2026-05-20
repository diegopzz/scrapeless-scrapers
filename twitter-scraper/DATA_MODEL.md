# Twitter (X.com) data model

Single source of truth for the Python (cerberus) and Node (zod) schemas. Field names mirror  verbatim.

> Public data only — tweet detail pages and public profiles. Replies, search, and following lists require login and are out of scope.

## Tweet (`scrape_tweet` → `tweet.json`)

| Field           | Type                | Required | Notes                                              |
| --------------- | ------------------- | -------- | -------------------------------------------------- |
| created_at      | string              | yes      | `legacy.created_at`                                |
| attached_urls   | list[string]        | no       | `legacy.entities.urls[].expanded_url`              |
| attached_urls2  | list[string]        | no       | `legacy.entities.url.urls[].expanded_url`          |
| attached_media  | list[string]        | no       | `legacy.entities.media[].media_url_https`          |
| tagged_users    | list[string]        | no       | `legacy.entities.user_mentions[].screen_name`      |
| tagged_hashtags | list[string]        | no       | `legacy.entities.hashtags[].text`                  |
| favorite_count  | int                 | yes      |                                                    |
| bookmark_count  | int\|null           | no       |                                                    |
| quote_count     | int                 | yes      |                                                    |
| reply_count     | int                 | yes      |                                                    |
| retweet_count   | int                 | yes      |                                                    |
| text            | string              | yes      | `legacy.full_text`                                 |
| is_quote        | bool                | yes      | `legacy.is_quote_status`                           |
| is_retweet      | bool                | yes      | `legacy.retweeted`                                 |
| language        | string              | yes      | `legacy.lang`                                      |
| user_id         | string              | yes      | `legacy.user_id_str`                               |
| id              | string              | yes      | `legacy.id_str`                                    |
| conversation_id | string              | yes      | `legacy.conversation_id_str`                       |
| source          | string\|null        | no       |                                                    |
| views           | string\|null        | no       | `views.count`                                      |
| poll            | object              | no       | flat dict, keys vary by card binding               |
| user            | Profile             | no       | embedded; same shape as `scrape_profile`           |

## Profile (`scrape_profile` → `profile.json`)

| Field    | Type   | Required | Notes                              |
| -------- | ------ | -------- | ---------------------------------- |
| id       | string | yes      |                                    |
| rest_id  | string | yes      |                                    |
| verified | bool   | yes      | `is_blue_verified`                 |
| **…**    | **…**  | **…**    | flat spread of `data.legacy` (`screen_name`, `name`, `description`, `followers_count`, `friends_count`, etc. — Twitter's UserLegacy shape) |
