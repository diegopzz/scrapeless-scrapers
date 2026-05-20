# Reddit data model

Single source of truth for the Python (cerberus) and Node (zod) schemas. Field names mirror  verbatim.

## SubredditPost (`scrape_subreddit` → `subreddit_data["posts"][i]`)

| Field          | Type          | Required | Notes                                            |
| -------------- | ------------- | -------- | ------------------------------------------------ |
| authorProfile  | string\|null  | no       | `https://www.reddit.com/user/{author}`           |
| authorId       | string\|null  | no       | `shreddit-post[author-id]`                       |
| title          | string\|null  | no       | `<article aria-label>`                           |
| link           | string\|null  | no       | absolute permalink                               |
| publishingDate | string\|null  | no       | ISO timestamp                                    |
| postId         | string\|null  | no       | `shreddit-post[id]`                              |
| postLabel      | string\|null  | no       | e.g. "Discussion"                                |
| postUpvotes    | int\|null     | no       | `score`                                          |
| commentCount   | int\|null     | no       | `comment-count`                                  |
| attachmentType | string\|null  | no       | `image`/`video`/`gallery`/`link`/…               |
| attachmentLink | string\|null  | no       |                                                  |

## SubredditInfo (`scrape_subreddit` → `subreddit_data["info"]`)

| Field       | Type            | Required | Notes                                      |
| ----------- | --------------- | -------- | ------------------------------------------ |
| id          | string          | yes      | trailing segment of URL                    |
| description | string\|null    | no       |                                            |
| rank        | string\|null    | no       |                                            |
| members     | int\|null       | no       | falls back to weekly-active                |
| bookmarks   | object[str,str] | no       | community menu links                       |
| url         | string          | yes      |                                            |

## PostInfo (`scrape_post` → `post_data["info"]`)

| Field          | Type          | Required | Notes                          |
| -------------- | ------------- | -------- | ------------------------------ |
| authorId       | string\|null  | no       |                                |
| author         | string\|null  | no       |                                |
| authorProfile  | string\|null  | no       |                                |
| subreddit      | string        | yes      | with `r/` prefix stripped      |
| postId         | string\|null  | no       |                                |
| postLabel      | string\|null  | no       |                                |
| publishingDate | string\|null  | no       |                                |
| postTitle      | string\|null  | no       |                                |
| postLink       | string\|null  | no       | canonical URL                  |
| commentCount   | int\|null     | no       |                                |
| upvoteCount    | int\|null     | no       |                                |
| attachmentType | string\|null  | no       |                                |
| attachmentLink | string\|null  | no       |                                |

## PostComment (`scrape_post` → `post_data["comments"][i]` and recursive `.replies`)

| Field          | Type          | Required | Notes                          |
| -------------- | ------------- | -------- | ------------------------------ |
| authorId       | string\|null  | no       | `data-author-fullname`         |
| author         | string\|null  | no       |                                |
| authorProfile  | string\|null  | no       |                                |
| commentId      | string\|null  | no       | `data-fullname`                |
| link           | string\|null  | no       | absolute permalink             |
| publishingDate | string\|null  | no       |                                |
| commentBody    | string\|null  | no       |                                |
| upvotes        | int\|null     | no       |                                |
| dislikes       | int\|null     | no       |                                |
| downvotes      | int\|null     | no       |                                |
| replies        | list[PostComment] | no   | recursive                      |

## UserPost (`scrape_user_posts` → list item)

| Field          | Type          | Required | Notes                          |
| -------------- | ------------- | -------- | ------------------------------ |
| authorId       | string\|null  | no       |                                |
| author         | string\|null  | no       |                                |
| authorProfile  | string\|null  | no       |                                |
| postId         | string\|null  | no       |                                |
| postLink       | string\|null  | no       |                                |
| postTitle      | string\|null  | no       |                                |
| postSubreddit  | string\|null  | no       | with `r/` prefix               |
| publishingDate | string\|null  | no       | ISO timestamp                  |
| commentCount   | int\|null     | no       |                                |
| postScore      | int\|null     | no       |                                |
| attachmentType | string\|null  | no       |                                |
| attachmentLink | string\|null  | no       |                                |

## UserComment (`scrape_user_comments` → list item)

| Field                | Type          | Required | Notes                          |
| -------------------- | ------------- | -------- | ------------------------------ |
| authorId             | string\|null  | no       |                                |
| author               | string\|null  | no       |                                |
| authorProfile        | string\|null  | no       |                                |
| commentId            | string\|null  | no       |                                |
| commentLink          | string\|null  | no       |                                |
| commentBody          | string        | yes      | joined paragraph text          |
| attachedCommentLinks | list[string]  | no       |                                |
| publishingDate       | string\|null  | no       |                                |
| dislikes             | int\|null     | no       |                                |
| upvotes              | int\|null     | no       |                                |
| downvotes            | int\|null     | no       |                                |
| replyTo              | object        | no       | parent post info (4 fields)    |
