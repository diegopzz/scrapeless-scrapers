// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import {
  scrapeChannel,
  scrapeChannelVideos,
  scrapeComments,
  scrapeSearch,
  scrapeShorts,
  scrapeVideo,
} from "./youtube.mjs";

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const VideoSchema = z.object({
  video: z.object({
    videoId: z.string().min(1),
    title: z.string().min(1),
    publishingDate: z.string().nullable(),
    lengthSeconds: z.number().int().nullable(),
    keywords: z.array(z.string()).nullable(),
    description: z.string().nullable(),
    thumbnail: z.array(z.any()).nullable(),
    stats: z.object({
      viewCount: z.number().int().nullable(),
      likeCount: z.number().int().nullable(),
      commentCount: z.number().int().nullable(),
    }),
  }),
  channel: z.object({
    name: z.string().nullable(),
    identifierId: z.string().nullable(),
    id: z.string().nullable(),
    verified: z.boolean(),
    channelUrl: z.string().nullable(),
    subscriberCount: z.string().nullable(),
    thumbnails: z.array(z.any()).nullable(),
  }),
  commentContinuationToken: z.string().nullable(),
}).passthrough();

const CommentSchema = z.object({
  comment: z.object({
    id: z.string().min(1),
    text: z.string(),
    publishedTime: z.string(),
  }),
  author: z.object({
    id: z.string(),
    displayName: z.string(),
    avatarThumbnail: z.string(),
    isVerified: z.boolean(),
    isCurrentUser: z.boolean(),
    isCreator: z.boolean(),
  }),
  stats: z.object({
    likeCount: z.string().nullable(),
    replyCount: z.string().nullable(),
  }),
}).passthrough();

const ChannelSchema = z.object({
  description: z.string().nullable(),
  url: z.string().nullable(),
  subscriberCount: z.string().nullable(),
  videoCount: z.string().nullable(),
  viewCount: z.string().nullable(),
  joinedDate: z.string().nullable(),
  country: z.string().nullable(),
  links: z.array(z.any()),
}).passthrough();

const ChannelVideoSchema = z.object({
  videoId: z.string().min(1),
  title: z.string().min(1),
  description: z.string().nullable(),
  publishedTime: z.string().nullable(),
  lengthText: z.string().nullable(),
  viewCount: z.string().nullable(),
  thumbnails: z.array(z.any()),
  url: z.string().min(1),
}).passthrough();

const SearchSchema = z.object({
  id: z.string().min(1),
  title: z.string().min(1),
  description: z.string().nullable(),
  publishedTime: z.string().nullable(),
  videoLength: z.string().nullable(),
  viewCount: z.string().nullable(),
  videoBadges: z.array(z.any()).nullable(),
  channelBadges: z.array(z.any()).nullable(),
  videoThumbnails: z.array(z.any()),
  channelThumbnails: z.array(z.any()).nullable(),
  url: z.string().min(1),
}).passthrough();

const ShortSchema = z.object({
  videoId: z.string().min(1),
  title: z.string().min(1),
  lengthSeconds: z.string(),
  channelId: z.string(),
  thumbnail: z.array(z.any()),
  viewCount: z.string(),
  author: z.string(),
}).passthrough();

const SAMPLE_VIDEO_IDS = ["1Y-XvvWlyzk"];
const SAMPLE_COMMENTS_VIDEO = "FgakZw6K1QQ";
const SAMPLE_CHANNEL = "statquest";
const SAMPLE_SEARCH = "python";
const SAMPLE_SEARCH_PARAMS = "EgQIAxAB";
const SAMPLE_SHORT_IDS = ["rZ2qqtNPSBk"];

test("video schema", async () => {
  const results = await scrapeVideo(SAMPLE_VIDEO_IDS);
  assert.ok(results.length >= 1);
  for (const r of results) VideoSchema.parse(r);
});

test("comments schema", async () => {
  const results = await scrapeComments(SAMPLE_COMMENTS_VIDEO, 1);
  assert.ok(Array.isArray(results));
  for (const r of results) CommentSchema.parse(r);
});

test("channel schema", async () => {
  const results = await scrapeChannel([SAMPLE_CHANNEL]);
  assert.ok(results.length >= 1);
  for (const r of results) ChannelSchema.parse(r);
});

test("channel videos schema", async () => {
  const results = await scrapeChannelVideos(SAMPLE_CHANNEL, "Latest", 1);
  assert.ok(Array.isArray(results));
  for (const r of results) ChannelVideoSchema.parse(r);
});

test("search schema", async () => {
  const results = await scrapeSearch(SAMPLE_SEARCH, 1, SAMPLE_SEARCH_PARAMS);
  assert.ok(results.length >= 1);
  for (const r of results) SearchSchema.parse(r);
});

test("shorts schema", async () => {
  const results = await scrapeShorts(SAMPLE_SHORT_IDS);
  assert.ok(results.length >= 1);
  for (const r of results) ShortSchema.parse(r);
});
