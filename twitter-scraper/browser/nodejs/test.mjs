// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.
// Public data only — matches import { test } from "node:test";
import { z } from "zod";
import { scrapeProfile, scrapeTweet } from "./twitter.mjs";

const SAMPLE_TWEET = process.env.TWITTER_SAMPLE_TWEET ?? "https://x.com/robinhanson/status/1872047986873885082";
const SAMPLE_PROFILE = process.env.TWITTER_SAMPLE_PROFILE ?? "https://x.com/robinhanson/";

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const TweetSchema = z
  .object({
    id: z.string().min(1),
    user_id: z.string().min(1),
    conversation_id: z.string().min(1),
    text: z.string(),
    created_at: z.string().min(1),
    favorite_count: z.number().int().nonnegative(),
    reply_count: z.number().int().nonnegative(),
    retweet_count: z.number().int().nonnegative(),
    quote_count: z.number().int().nonnegative(),
    is_quote: z.boolean(),
    is_retweet: z.boolean(),
    language: z.string(),
  })
  .passthrough();

const ProfileSchema = z
  .object({
    id: z.string().min(1),
    rest_id: z.string().min(1),
    verified: z.boolean(),
    screen_name: z.string().min(1),
    name: z.string().min(1),
  })
  .passthrough();

test("tweet schema", async () => {
  const tweet = await scrapeTweet(SAMPLE_TWEET);
  TweetSchema.parse(tweet);
});

test("profile schema", async () => {
  const profile = await scrapeProfile(SAMPLE_PROFILE);
  ProfileSchema.parse(profile);
});
