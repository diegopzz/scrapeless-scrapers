# Instagram data model

Single source of truth for the Python (cerberus) and Node (zod) schemas under [`python/`](python/) and [`nodejs/`](nodejs/). Field names mirror  verbatim.

> Public data only. Anything behind Instagram's login wall is out of scope.

## User (`scrape_user` → `user.json`)

| Field             | Type            | Required | Notes                                                |
| ----------------- | --------------- | -------- | ---------------------------------------------------- |
| name              | string          | yes      | `full_name`                                          |
| username          | string          | yes      |                                                      |
| id                | string          | yes      |                                                      |
| category          | string\|null    | no       | `category_name`                                      |
| business_category | string\|null    | no       | `business_category_name`                             |
| phone             | string\|null    | no       | `business_phone_number`                              |
| email             | string\|null    | no       | `business_email`                                     |
| bio               | string\|null    | no       | `biography`                                          |
| bio_links         | list[string]    | no       | bio_links[].url                                      |
| homepage          | string\|null    | no       | `external_url`                                       |
| followers         | int             | yes      | `edge_followed_by.count`                             |
| follows           | int             | yes      | `edge_follow.count`                                  |
| facebook_id       | string\|null    | no       | `fbid`                                               |
| is_private        | bool            | yes      |                                                      |
| is_verified       | bool            | yes      |                                                      |
| profile_image     | string          | yes      | `profile_pic_url_hd`                                 |
| video_count       | int             | yes      | `edge_felix_video_timeline.count`                    |
| videos            | list[VideoNode] | no       | one per `edge_felix_video_timeline.edges[].node`     |
| image_count       | int             | yes      | `edge_owner_to_timeline_media.count`                 |
| images            | list[ImageNode] | no       | same source edges as `videos`                        |
| saved_count       | int\|null       | no       | `edge_saved_media.count`                             |
| collections_count | int\|null       | no       | `edge_saved_media.count`                             |
| related_profiles  | list[string]    | no       | `edge_related_profiles.edges[].node.username`        |

## Post (`scrape_post` → `video-post.json`, `multi-image-post.json`)

| Field              | Type              | Required | Notes                                                  |
| ------------------ | ----------------- | -------- | ------------------------------------------------------ |
| id                 | string            | yes      |                                                        |
| shortcode          | string            | yes      |                                                        |
| dimensions         | object            | no       |                                                        |
| src                | string            | yes      | `display_url`                                          |
| thumbnail_src      | string\|null      | no       |                                                        |
| media_preview      | string\|null      | no       |                                                        |
| video_url          | string\|null      | no       |                                                        |
| views              | int\|null         | no       | `video_view_count`                                     |
| likes              | int               | yes      | `edge_media_preview_like.count`                        |
| location           | string\|null      | no       | `location.name`                                        |
| taken_at           | int               | yes      | `taken_at_timestamp`                                   |
| related            | list[string]      | no       | shortcodes from `edge_web_media_to_related_media`      |
| type               | string\|null      | no       | `product_type`                                         |
| video_duration     | float\|null       | no       |                                                        |
| music              | object\|null      | no       | `clips_music_attribution_info`                         |
| is_video           | bool              | yes      |                                                        |
| tagged_users       | list[string]      | no       | `edge_media_to_tagged_user.edges[].node.user.username` |
| captions           | list[string]      | no       | `edge_media_to_caption.edges[].node.text`              |
| related_profiles   | list[string]      | no       |                                                        |
| comments_count     | int               | yes      | from `edge_media_to_comment.count`                     |
| comments_disabled  | bool              | yes      |                                                        |
| comments_next_page | string\|null      | no       | `end_cursor`                                           |
| comments           | list[CommentNode] | no       | embedded inline                                        |

## UserPost (`scrape_user_posts` items → `all-user-posts.json`)

| Field            | Type           | Required | Notes      |
| ---------------- | -------------- | -------- | ---------- |
| id               | string         | yes      |            |
| shortcode        | string         | yes      | `code`     |
| caption          | object\|null   | no       |            |
| taken_at         | int            | yes      |            |
| video_versions   | list\|null     | no       |            |
| image_versions2  | object\|null   | no       |            |
| original_height  | int\|null      | no       |            |
| original_width   | int\|null      | no       |            |
| link             | string\|null   | no       |            |
| title            | string\|null   | no       |            |
| comment_count    | int            | yes      |            |
| top_likers       | list\|null     | no       |            |
| like_count       | int            | yes      |            |
| usertags         | object\|null   | no       |            |
| clips_metadata   | object\|null   | no       |            |
| comments         | list           | no       |            |

## PostComment (`scrape_post_comments` items → `post-comments.json`)

| Field             | Type         | Required | Notes                       |
| ----------------- | ------------ | -------- | --------------------------- |
| id                | string       | yes      | `pk`                        |
| text              | string       | yes      |                             |
| created_at        | int          | yes      |                             |
| owner             | string       | yes      | `user.username`             |
| owner_id          | string       | yes      | `user.id`                   |
| owner_verified    | bool         | yes      | `user.is_verified`          |
| owner_profile_pic | string\|null | no       | `user.profile_pic_url`      |
| likes             | int          | yes      | `comment_like_count`        |
| replies_count     | int          | yes      | `child_comment_count`       |
| parent_comment_id | string\|null | no       |                             |
