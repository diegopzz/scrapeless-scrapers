# Threads.net data model

Single source of truth for the Python (cerberus) and Node (zod) schemas. Field names mirror  verbatim.

> Public data only. Threads is not available in Europe, so the scraper proxies through US by default. Non-public surfaces (DMs, follows, settings) require login and are out of scope.

## ThreadPost (`parse_thread` element)

Inner shape — one of these per parent thread or reply.

| Field         | Type         | Required | Notes                                                      |
| ------------- | ------------ | -------- | ---------------------------------------------------------- |
| text          | string\|null | no       | `post.caption.text`                                        |
| published_on  | int          | yes      | `post.taken_at`                                            |
| id            | string       | yes      | `post.id`                                                  |
| pk            | string       | yes      | `post.pk`                                                  |
| code          | string       | yes      | `post.code`                                                |
| username      | string       | yes      | `post.user.username`                                       |
| user_pic      | string       | yes      | `post.user.profile_pic_url`                                |
| user_verified | bool         | yes      | `post.user.is_verified`                                    |
| user_pk       | string       | yes      | `post.user.pk`                                             |
| user_id       | string       | yes      | `post.user.id`                                             |
| has_audio     | bool\|null   | no       |                                                            |
| reply_count   | int          | yes      | `post.text_post_app_info.direct_reply_count`               |
| like_count    | int          | yes      |                                                            |
| images        | list[string] | no       | second-candidate image url per carousel item              |
| image_count   | int          | yes      | length of `images`                                         |
| videos        | list[string] | no       | unique `post.video_versions[].url`                         |
| url           | string       | yes      | `https://www.threads.net/@{username}/post/{code}`          |

## UserProfile (`parse_profile` element)

Inner shape for the profile object.

| Field       | Type         | Required | Notes                                       |
| ----------- | ------------ | -------- | ------------------------------------------- |
| is_private  | bool         | yes      | `text_post_app_is_private`                  |
| is_verified | bool         | yes      |                                             |
| profile_pic | string       | yes      | last `hd_profile_pic_versions[].url`        |
| username    | string       | yes      |                                             |
| full_name   | string       | yes      |                                             |
| bio         | string\|null | no       | `biography`                                 |
| bio_links   | list[string] | no       |                                             |
| followers   | int          | yes      | `follower_count`                            |
| url         | string       | yes      | `https://www.threads.net/@{username}`       |

## Thread (`scrape_thread` output)

Top-level envelope returned by `scrape_thread(url)`.

| Field   | Type         | Required | Notes                          |
| ------- | ------------ | -------- | ------------------------------ |
| thread  | object       | yes      | Parent ThreadPost              |
| replies | array        | no       | Replies in canonical order (list of ThreadPost) |

## Profile (`scrape_profile` output)

Top-level envelope returned by `scrape_profile(url)`.

| Field   | Type         | Required | Notes                          |
| ------- | ------------ | -------- | ------------------------------ |
| user    | object       | yes      | UserProfile metadata           |
| threads | array        | no       | Latest threads on the profile feed (list of ThreadPost) |
