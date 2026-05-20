# TikTok data model

Single source of truth for the Python (cerberus) and Node (zod) schemas. Field names mirror  verbatim.

> Public data only. TikTok aggressively fingerprints — the cloud browser session is proxied through AU by default and uses a longer `session_ttl` (300s) so scroll-triggered XHRs land before teardown.

## Post (`scrape_posts` items → `posts.json`)

| Field                 | Type        | Required | Notes                                                  |
| --------------------- | ----------- | -------- | ------------------------------------------------------ |
| id                    | string      | yes      |                                                        |
| desc                  | string      | yes      | caption                                                |
| createTime            | string      | yes      | Unix seconds as string (TikTok serialises it this way) |
| video                 | object      | yes      | `{duration, ratio, cover, playAddr, downloadAddr, bitrate}` |
| author                | object      | yes      | `{id, uniqueId, nickname, avatarLarger, signature, verified}` |
| stats                 | object      | yes      | `{diggCount, shareCount, commentCount, playCount, ...}` |
| locationCreated       | string\|null| no       |                                                        |
| diversificationLabels | list[string]\|null | no |                                                        |
| suggestedWords        | list[string]\|null | no |                                                        |
| contents              | list[object]| no       | each `{textExtra: [{hashtagName}]}`                    |

## Comment (`scrape_comments` items → `comments.json`)

| Field               | Type         | Required | Notes                       |
| ------------------- | ------------ | -------- | --------------------------- |
| text                | string       | yes      |                             |
| comment_language    | string\|null | no       |                             |
| digg_count          | int          | yes      |                             |
| reply_comment_total | int          | yes      |                             |
| author_pin          | bool\|null   | no       |                             |
| create_time         | int          | yes      |                             |
| cid                 | string       | yes      |                             |
| nickname            | string       | yes      | `user.nickname`             |
| unique_id           | string       | yes      | `user.unique_id`            |
| aweme_id            | string       | yes      |                             |

## Profile (`scrape_profiles` items → `profiles.json`)

Returned verbatim from `webapp.user-detail.userInfo` — keys: `user` (id, uniqueId, nickname, avatarLarger, signature, verified, ...) and `stats` (followingCount, followerCount, heartCount, videoCount, diggCount).

## SearchResult (`scrape_search` items → `search.json`)

| Field       | Type   | Required | Notes                  |
| ----------- | ------ | -------- | ---------------------- |
| id          | string | yes      |                        |
| desc        | string | yes      |                        |
| createTime  | string | yes      | Unix seconds as string |
| video       | object | yes      |                        |
| author      | object | yes      |                        |
| stats       | object | yes      |                        |
| authorStats | object | yes      |                        |
| type        | int    | yes      | 1 = video item         |

## ChannelPost (`scrape_channel` items → `channel.json`)

| Field      | Type         | Required | Notes                                          |
| ---------- | ------------ | -------- | ---------------------------------------------- |
| createTime | string       | yes      | Unix seconds as string                         |
| desc       | string       | yes      |                                                |
| id         | string       | yes      |                                                |
| stats      | object       | yes      |                                                |
| contents   | list[object] | no       | each `{desc, textExtra: [{hashtagName}]}`      |
