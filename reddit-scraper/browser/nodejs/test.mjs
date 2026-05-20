// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { scrapePost, scrapeSubreddit, scrapeUserComments, scrapeUserPosts } from "./reddit.mjs";

const SAMPLE_SUBREDDIT = process.env.REDDIT_SAMPLE_SUBREDDIT ?? "wallstreetbets";
const SAMPLE_POST_URL = process.env.REDDIT_SAMPLE_POST_URL ?? "https://www.reddit.com/r/wallstreetbets/comments/1c4vwlp/what_are_your_moves_tomorrow_april_16_2024/";
const SAMPLE_USERNAME = process.env.REDDIT_SAMPLE_USERNAME ?? "the upstream reference";

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const SubredditInfoSchema = z.object({
  id: z.string().min(1),
  url: z.string(),
  description: z.string().nullable(),
  rank: z.string().nullable(),
  members: z.number().int().nullable(),
}).passthrough();

const SubredditPostSchema = z.object({
  title: z.string().nullable(),
  link: z.string().nullable(),
  postId: z.string().nullable(),
}).passthrough();

const PostInfoSchema = z.object({
  subreddit: z.string(),
  postTitle: z.string().nullable(),
  postLink: z.string().nullable(),
}).passthrough();

const UserPostSchema = z.object({
  postId: z.string().nullable(),
  postLink: z.string().nullable(),
}).passthrough();

const UserCommentSchema = z.object({
  commentBody: z.string(),
  replyTo: z.object({}).passthrough(),
}).passthrough();

test("subreddit schema", async () => {
  const sub = await scrapeSubreddit(SAMPLE_SUBREDDIT, 1);
  SubredditInfoSchema.parse(sub.info);
  assert.ok(sub.posts.length >= 1);
  for (const p of sub.posts) SubredditPostSchema.parse(p);
});

test("post schema", async () => {
  const post = await scrapePost(SAMPLE_POST_URL, "top");
  PostInfoSchema.parse(post.info);
});

test("user_posts schema", async () => {
  const posts = await scrapeUserPosts(SAMPLE_USERNAME, "top", 1);
  for (const p of posts) UserPostSchema.parse(p);
});

test("user_comments schema", async () => {
  const comments = await scrapeUserComments(SAMPLE_USERNAME, "top", 1);
  for (const c of comments) UserCommentSchema.parse(c);
});
