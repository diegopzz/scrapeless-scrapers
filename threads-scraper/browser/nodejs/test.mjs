// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.
// Public data only — matches import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { scrapeProfile, scrapeThread } from "./threads.mjs";

const SAMPLE_THREAD = process.env.THREADS_SAMPLE_THREAD ?? "https://www.threads.net/t/C8CTu0iswgv";
const SAMPLE_PROFILE = process.env.THREADS_SAMPLE_PROFILE ?? "https://www.threads.net/@natgeo";

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const ThreadSchema = z
  .object({
    id: z.string().min(1),
    pk: z.string().min(1),
    code: z.string().min(1),
    username: z.string().min(1),
    user_pic: z.string(),
    user_verified: z.boolean(),
    user_pk: z.string().min(1),
    user_id: z.string().min(1),
    reply_count: z.number().int().nonnegative(),
    like_count: z.number().int().nonnegative(),
    image_count: z.number().int().nonnegative(),
    url: z.string(),
    published_on: z.number().int(),
  })
  .passthrough();

const ProfileSchema = z
  .object({
    is_private: z.boolean(),
    is_verified: z.boolean(),
    profile_pic: z.string(),
    username: z.string().min(1),
    full_name: z.string(),
    followers: z.number().int().nonnegative(),
    url: z.string(),
  })
  .passthrough();

test("thread schema", async () => {
  const result = await scrapeThread(SAMPLE_THREAD);
  assert.ok(result.thread, "expected a parent thread");
  ThreadSchema.parse(result.thread);
});

test("profile schema", async () => {
  const result = await scrapeProfile(SAMPLE_PROFILE);
  ProfileSchema.parse(result.user);
});
