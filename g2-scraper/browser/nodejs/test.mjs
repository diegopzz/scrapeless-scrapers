// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { scrapeAlternatives, scrapeReviews, scrapeSearch } from "./g2.mjs";

const SAMPLE_SEARCH_URL = process.env.G2_SAMPLE_SEARCH_URL ?? "https://www.g2.com/search?query=Infrastructure";
const SAMPLE_REVIEW_URL = process.env.G2_SAMPLE_REVIEW_URL ?? "https://www.g2.com/products/digitalocean/reviews";
const SAMPLE_PRODUCT = process.env.G2_SAMPLE_PRODUCT ?? "digitalocean";

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const SearchSchema = z.object({
  name: z.string().min(1),
  link: z.string().min(1),
  image: z.string().nullable(),
  rate: z.number().nullable(),
  reviewsNumber: z.number().nullable(),
  description: z.string().nullable(),
  categories: z.array(z.string()),
}).passthrough();

const ReviewSchema = z.object({
  author: z.object({
    authorName: z.string().nullable(),
    authorProfile: z.string().nullable(),
    authorPosition: z.string().nullable(),
    authorCompanySize: z.string().nullable(),
  }).passthrough(),
  review: z.object({
    reviewTags: z.array(z.string()),
    reviewData: z.string().nullable(),
    reviewRate: z.number().nullable(),
    reviewTitle: z.string().nullable(),
    reviewLikes: z.string(),
    reviewDislikes: z.string(),
  }).passthrough(),
}).passthrough();

const AlternativeSchema = z.object({
  name: z.string().min(1),
  link: z.string().nullable(),
  ranking: z.number().nullable(),
  numberOfReviews: z.number().nullable(),
  rate: z.number().nullable(),
  description: z.string().nullable(),
}).passthrough();

test("search schema", async () => {
  const results = await scrapeSearch(SAMPLE_SEARCH_URL, 1);
  assert.ok(results.length >= 1, `expected >=1 results, got ${results.length}`);
  for (const r of results) SearchSchema.parse(r);
});

test("reviews schema", async () => {
  const reviews = await scrapeReviews(SAMPLE_REVIEW_URL, 1);
  assert.ok(reviews.length >= 1, `expected >=1 reviews, got ${reviews.length}`);
  for (const r of reviews) ReviewSchema.parse(r);
});

test("alternatives schema", async () => {
  const alts = await scrapeAlternatives(SAMPLE_PRODUCT);
  assert.ok(alts.length >= 1, `expected >=1 alternatives, got ${alts.length}`);
  for (const a of alts) AlternativeSchema.parse(a);
});
