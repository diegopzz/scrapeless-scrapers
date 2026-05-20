// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { scrapeKeywords, scrapeSearch } from "./bing.mjs";

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const SAMPLE_QUERY = process.env.BING_SAMPLE_QUERY ?? "web scraping emails";

const SearchSchema = z.object({
  position: z.number().int().min(1),
  title: z.string().min(1),
  url: z.string().min(1),
  origin: z.string(),
  domain: z.string(),
  description: z.string(),
  date: z.string(),
}).passthrough();

test("search schema", async () => {
  const results = await scrapeSearch(SAMPLE_QUERY, 1);
  assert.ok(results.length >= 1, `expected >=1 results, got ${results.length}`);
  for (const r of results) SearchSchema.parse(r);
});

test("keywords schema", async () => {
  const result = await scrapeKeywords(SAMPLE_QUERY);
  assert.ok(Array.isArray(result));
  for (const kw of result) assert.equal(typeof kw, "string");
});
