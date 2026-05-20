// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.
// Public data only — matches import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import {
  scrapeChannel,
  scrapeComments,
  scrapePosts,
  scrapeProfiles,
  scrapeSearch,
} from "./tiktok.mjs";

const SAMPLE_POST = process.env.TIKTOK_SAMPLE_POST ?? "https://www.tiktok.com/@oddanimalspecimens/video/7198206283571285294";
const SAMPLE_PROFILE = process.env.TIKTOK_SAMPLE_PROFILE ?? "https://www.tiktok.com/@oddanimalspecimens";
const SAMPLE_QUERY = process.env.TIKTOK_SAMPLE_QUERY ?? "whales";

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const PostSchema = z.object({
  id: z.string().min(1),
  desc: z.string(),
  createTime: z.number().int(),
  video: z.object({}).passthrough(),
  author: z.object({}).passthrough(),
  stats: z.object({}).passthrough(),
}).passthrough();

const CommentSchema = z.object({
  text: z.string(),
  digg_count: z.number().int().nonnegative(),
  reply_comment_total: z.number().int().nonnegative(),
  create_time: z.number().int(),
  cid: z.string().min(1),
  nickname: z.string(),
  unique_id: z.string(),
  aweme_id: z.string(),
}).passthrough();

const SearchSchema = z.object({
  id: z.string().min(1),
  desc: z.string(),
  createTime: z.number().int(),
  type: z.number().int(),
}).passthrough();

const ChannelSchema = z.object({
  id: z.string().min(1),
  desc: z.string(),
  createTime: z.number().int(),
  stats: z.object({}).passthrough(),
}).passthrough();

test("posts schema", async () => {
  const posts = await scrapePosts([SAMPLE_POST]);
  assert.equal(posts.length, 1);
  PostSchema.parse(posts[0]);
});

test("comments schema", async () => {
  const comments = await scrapeComments(SAMPLE_POST);
  for (const c of comments) CommentSchema.parse(c);
});

test("profiles schema", async () => {
  const profiles = await scrapeProfiles([SAMPLE_PROFILE]);
  assert.equal(profiles.length, 1);
  assert.ok(profiles[0].user);
  assert.ok(profiles[0].stats);
});

test("search schema", async () => {
  const results = await scrapeSearch(SAMPLE_QUERY);
  for (const r of results) SearchSchema.parse(r);
});

test("channel schema", async () => {
  const items = await scrapeChannel(SAMPLE_PROFILE);
  for (const item of items) ChannelSchema.parse(item);
});
