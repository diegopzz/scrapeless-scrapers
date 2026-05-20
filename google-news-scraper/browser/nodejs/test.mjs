// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { scrapeNews } from "./google-news.mjs";

const SAMPLE_QUERY = process.env.GOOGLE_NEWS_SAMPLE_QUERY ?? "adidas";

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const ArticleSchema = z.object({
  position: z.number().int().min(1),
  title: z.string().min(1),
  url: z.string().min(1),
  source: z.string(),
  time: z.string(),
  thumbnail: z.string(),
}).passthrough();

test("news schema", async () => {
  const results = await scrapeNews(SAMPLE_QUERY);
  assert.ok(results.length >= 1, `expected >=1 articles, got ${results.length}`);
  for (const r of results) ArticleSchema.parse(r);
});
