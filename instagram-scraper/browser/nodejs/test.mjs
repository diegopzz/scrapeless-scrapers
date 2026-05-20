// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.
// Public data only — matches import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { scrapePost, scrapePostComments, scrapeUser, scrapeUserPosts } from "./instagram.mjs";

const SAMPLE_USERNAME = process.env.INSTAGRAM_SAMPLE_USERNAME ?? "google";
const SAMPLE_POST = process.env.INSTAGRAM_SAMPLE_POST ?? "https://www.instagram.com/p/Cs9iEotsiGY/";

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const UserSchema = z
  .object({
    name: z.string().min(1),
    username: z.string().min(1),
    id: z.string().min(1),
    followers: z.number().int().nonnegative(),
    follows: z.number().int().nonnegative(),
    is_private: z.boolean(),
    is_verified: z.boolean(),
    profile_image: z.string(),
    video_count: z.number().int().nonnegative(),
    image_count: z.number().int().nonnegative(),
  })
  .passthrough();

const PostSchema = z
  .object({
    id: z.string().min(1),
    shortcode: z.string().min(1),
    src: z.string(),
    likes: z.number().int().nonnegative(),
    taken_at: z.number().int(),
    is_video: z.boolean(),
    comments_count: z.number().int().nonnegative(),
    comments_disabled: z.boolean(),
  })
  .passthrough();

const UserPostSchema = z
  .object({
    id: z.string().min(1),
    shortcode: z.string().min(1),
    taken_at: z.number().int(),
    comment_count: z.number().int().nonnegative(),
    like_count: z.number().int().nonnegative(),
  })
  .passthrough();

const PostCommentSchema = z
  .object({
    id: z.string().min(1),
    text: z.string(),
    created_at: z.number().int(),
    owner: z.string().min(1),
    likes: z.number().int().nonnegative(),
    replies_count: z.number().int().nonnegative(),
  })
  .passthrough();

test("user schema", async () => {
  const user = await scrapeUser(SAMPLE_USERNAME);
  UserSchema.parse(user);
});

test("post schema", async () => {
  const post = await scrapePost(SAMPLE_POST);
  PostSchema.parse(post);
});

test("user_posts schema", async () => {
  const items = [];
  for await (const p of scrapeUserPosts(SAMPLE_USERNAME, 12, 1)) items.push(p);
  assert.ok(items.length >= 1);
  for (const item of items) UserPostSchema.parse(item);
});

test("post_comments schema", async () => {
  const post = await scrapePost(SAMPLE_POST);
  const comments = await scrapePostComments(post.id, 10);
  for (const c of comments) PostCommentSchema.parse(c);
});
