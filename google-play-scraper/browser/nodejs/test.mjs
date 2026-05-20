// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { scrapeApp } from "./google-play.mjs";

const SAMPLE_ID = process.env.GOOGLE_PLAY_SAMPLE_ID ?? "com.spotify.music";

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const AppSchema = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
  developer: z.string(),
  rating: z.number().nullable(),
  rating_count: z.number().int().nullable(),
  price: z.string(),
  installs: z.string(),
  description: z.string(),
  categories: z.array(z.string()),
  latest_update: z.string(),
  screenshots: z.array(z.string()),
  icon: z.string(),
  url: z.string().min(1),
}).passthrough();

test("app schema", async () => {
  const app = await scrapeApp(SAMPLE_ID);
  AppSchema.parse(app);
  assert.equal(app.id, SAMPLE_ID);
});
