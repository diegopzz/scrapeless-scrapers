# YouTube data model

YouTube targets are scraped via the embedded `ytInitialData` / `ytInitialPlayerResponse` JSON and the internal `youtubei/v1` endpoints (POSTed from inside the live browser page so cookies + visitor data are real).

## Video

Returned by `scrape_video(ids)` — one wrapper object per video page. The wrapper has three top-level keys: `video`, `channel`, and `commentContinuationToken` (the latter feeds `scrape_comments`).

| Field                    | Type             | Required | Notes                                                       |
| ------------------------ | ---------------- | -------- | ----------------------------------------------------------- |
| video                    | object           | yes      | See `video` shape below                                     |
| channel                  | object           | yes      | See `channel` shape below                                   |
| commentContinuationToken | string \| null   | no       | Opaque token used to seed `scrape_comments`                 |

Nested `video` shape (free-form object — keys below are advisory, not enforced by the validator):

| Field           | Type             | Notes                                                          |
| --------------- | ---------------- | -------------------------------------------------------------- |
| videoId         | string           | From `ytInitialPlayerResponse.videoDetails.videoId`            |
| title           | string           | From `videoDetails.title`                                      |
| publishingDate  | string \| null   | `ytInitialData ... dateText.simpleText`                        |
| lengthSeconds   | integer \| null  | Parsed from `videoDetails.lengthSeconds`                       |
| keywords        | array of strings | From `videoDetails.keywords`                                   |
| description     | string \| null   | `videoDetails.shortDescription`                                |
| thumbnail       | array of objects | `videoDetails.thumbnail.thumbnails` (url/width/height)         |
| stats.viewCount    | integer \| null | Parsed from `videoDetails.viewCount`                          |
| stats.likeCount    | integer \| null | Parsed from the `LIKE` buttonViewModel title                  |
| stats.commentCount | integer \| null | From `contextualInfo.runs[0].text`                            |

Nested `channel` shape (free-form object — keys below are advisory, not enforced by the validator):

| Field            | Type             | Notes                                                       |
| ---------------- | ---------------- | ----------------------------------------------------------- |
| name             | string \| null   | `videoDetails.author`                                       |
| identifierId     | string \| null   | `videoDetails.channelId`                                    |
| id               | string \| null   | Slash-stripped `@handle` from `canonicalBaseUrl`            |
| verified         | boolean          | True iff a Verified `metadataBadge` is present              |
| channelUrl       | string \| null   | `https://www.youtube.com{canonicalBaseUrl}`                 |
| subscriberCount  | string \| null   | `subscriberCountText.simpleText` (raw)                      |
| thumbnails       | array \| null    | `engagementPanelSectionListRenderer..channelThumbnail.thumbnails` |

## Comment

Returned by `scrape_comments(video_id, max_scrape_pages)` — one entry per comment.

| Field                  | Type             | Required | Notes                                                |
| ---------------------- | ---------------- | -------- | ---------------------------------------------------- |
| comment.id             | string           | yes      | `commentEntityPayload.properties.commentId`          |
| comment.text           | string           | yes      | `properties.content.content`                         |
| comment.publishedTime  | string           | yes      | `properties.publishedTime`                           |
| author.id              | string           | yes      | `author.channelId`                                   |
| author.displayName     | string           | yes      | `author.displayName`                                 |
| author.avatarThumbnail | string           | yes      | `author.avatarThumbnailUrl`                          |
| author.isVerified      | boolean          | yes      | `author.isVerified`                                  |
| author.isCurrentUser   | boolean          | yes      | (the upstream reference mirror: same source as `isVerified`)       |
| author.isCreator       | boolean          | yes      | (the upstream reference mirror: same source as `isVerified`)       |
| stats.likeCount        | string \| null   | no       | `toolbar.likeCountLiked`                             |
| stats.replyCount       | string \| null   | no       | `toolbar.replyCount`                                 |

## Channel

Returned by `scrape_channel(channel_ids)` — one object per channel-handle page, parsed from the `aboutChannelViewModel` block.

| Field           | Type             | Required | Notes                                                  |
| --------------- | ---------------- | -------- | ------------------------------------------------------ |
| description     | string \| null   | no       | `aboutChannelViewModel.description`                    |
| url             | string \| null   | no       | `displayCanonicalChannelUrl`                           |
| subscriberCount | string \| null   | no       | `subscriberCountText`                                  |
| videoCount      | string \| null   | no       | `videoCountText`                                       |
| viewCount       | string \| null   | no       | `viewCountText`                                        |
| joinedDate      | string \| null   | no       | `joinedDateText.content`                               |
| country         | string \| null   | no       | `country`                                              |
| links           | array of objects | yes      | Each has `title`, `url`, `favicon`                     |

## ChannelVideo

Returned by `scrape_channel_videos(channel_id, sort_by, max_scrape_pages)`.

| Field          | Type             | Required | Notes                                              |
| -------------- | ---------------- | -------- | -------------------------------------------------- |
| videoId        | string           | yes      | `videoRenderer.videoId`                            |
| title          | string           | yes      | `title.runs[0].text`                               |
| description    | string \| null   | no       | `descriptionSnippet.runs[0].text`                  |
| publishedTime  | string \| null   | no       | `publishedTimeText.simpleText`                     |
| lengthText     | string \| null   | no       | `lengthText.simpleText`                            |
| viewCount      | string \| null   | no       | `viewCountText.simpleText`                         |
| thumbnails     | array of objects | yes      | `thumbnail.thumbnails`                             |
| url            | string           | yes      | `https://youtu.be/{videoId}`                       |

## SearchResult

Returned by `scrape_search(search_query, max_scrape_pages, search_params)`. `search_params` accepts the opaque YouTube filter token (video-only = `"EgQIAxAB"`).

| Field             | Type             | Required | Notes                                                          |
| ----------------- | ---------------- | -------- | -------------------------------------------------------------- |
| id                | string           | yes      | `videoRenderer.videoId`                                        |
| title             | string           | yes      | `title.runs[0].text`                                           |
| description       | string \| null   | no       | `detailedMetadataSnippets[0].snippetText.runs[0].text`         |
| publishedTime     | string \| null   | no       | `publishedTimeText.simpleText`                                 |
| videoLength       | string \| null   | no       | `lengthText.simpleText`                                        |
| viewCount         | string \| null   | no       | `viewCountText.simpleText`                                     |
| videoBadges       | array \| null    | no       | `badges[].metadataBadgeRenderer.label`                         |
| channelBadges     | array \| null    | no       | `ownerBadges[].metadataBadgeRenderer.accessibilityData.label`  |
| videoThumbnails   | array of objects | yes      | `thumbnail.thumbnails`                                         |
| channelThumbnails | array \| null    | no       | `channelThumbnailSupportedRenderers...thumbnail.thumbnails`    |
| url               | string           | yes      | `https://youtu.be/{id}`                                        |

## Short

Returned by `scrape_shorts(ids)` — one object per shorts page, taken directly from `ytInitialPlayerResponse.videoDetails`. Shape matches the upstream reference verbatim:

| Field             | Type             | Required | Notes                                                          |
| ----------------- | ---------------- | -------- | -------------------------------------------------------------- |
| videoId           | string           | yes      | `videoDetails.videoId`                                         |
| title             | string           | yes      | `videoDetails.title`                                           |
| lengthSeconds     | string           | yes      | `videoDetails.lengthSeconds` (raw, not converted for shorts)   |
| keywords          | array of strings | no       | `videoDetails.keywords`                                        |
| channelId         | string           | yes      | `videoDetails.channelId`                                       |
| isOwnerViewing    | boolean          | no       | `videoDetails.isOwnerViewing`                                  |
| shortDescription  | string           | no       | `videoDetails.shortDescription`                                |
| isCrawlable       | boolean          | no       | `videoDetails.isCrawlable`                                     |
| thumbnail         | array of objects | yes      | `videoDetails.thumbnail.thumbnails` (flattened)                |
| viewCount         | string           | yes      | `videoDetails.viewCount`                                       |
| author            | string           | yes      | `videoDetails.author`                                          |
| isLiveContent     | boolean          | no       | `videoDetails.isLiveContent`                                   |
