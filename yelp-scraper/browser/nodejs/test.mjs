// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { scrapePages, scrapeReviews, scrapeSearch } from "./yelp.mjs";

const SAMPLE_URL = process.env.YELP_SAMPLE_URL ?? "https://www.yelp.com/biz/vons-1000-spirits-seattle-4";
const SAMPLE_KEYWORD = process.env.YELP_SAMPLE_KEYWORD ?? "plumbers";
const SAMPLE_LOCATION = process.env.YELP_SAMPLE_LOCATION ?? "Seattle, WA";

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const BusinessSchema = z.object({
  name: z.string().min(1),
  website: z.string(),
  phone: z.string(),
  address: z.string(),
  logo: z.string(),
  claim_status: z.string(),
  open_hours: z.record(z.string()),
}).passthrough();

const ReviewSchema = z.object({
  encid: z.string().min(1),
  text: z.object({ full: z.string().nullable(), language: z.string().nullable() }).passthrough(),
  rating: z.number().int().min(1).max(5),
  feedback: z.object({}).passthrough(),
  author: z.object({}).passthrough(),
  business: z.object({}).passthrough(),
  createdAt: z.string(),
}).passthrough();

const SearchSchema = z.object({
  bizId: z.string().min(1),
  searchResultBusiness: z.object({}).passthrough(),
}).passthrough();

test("business pages schema", async () => {
  const pages = await scrapePages([SAMPLE_URL]);
  assert.equal(pages.length, 1);
  BusinessSchema.parse(pages[0]);
});

test("reviews schema", async () => {
  const reviews = await scrapeReviews(SAMPLE_URL, 10);
  assert.ok(reviews.length >= 1, `expected >=1 reviews, got ${reviews.length}`);
  for (const r of reviews) ReviewSchema.parse(r);
});

test("search schema", async () => {
  const results = await scrapeSearch(SAMPLE_KEYWORD, SAMPLE_LOCATION, 1);
  assert.ok(results.length >= 1, `expected >=1 results, got ${results.length}`);
  for (const r of results) SearchSchema.parse(r);
});
