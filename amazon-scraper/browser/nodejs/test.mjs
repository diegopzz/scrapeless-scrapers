// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { scrapeProduct, scrapeReviews, scrapeSearch } from "./amazon.mjs";

const SAMPLE_SEARCH_URL = process.env.AMAZON_SAMPLE_SEARCH_URL ?? "https://www.amazon.com/s?k=kindle";
const SAMPLE_PRODUCT_URL = process.env.AMAZON_SAMPLE_PRODUCT_URL
  ?? "https://www.amazon.com/PlayStation-5-Console-CFI-1215A01X/dp/B0BCNKKZ91/";

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const SearchSchema = z.object({
  url: z.string().min(1),
  title: z.string().nullable(),
  price: z.string().nullable(),
  real_price: z.string().nullable(),
  rating: z.number().nullable(),
  rating_count: z.number().nullable(),
}).passthrough();

const ProductSchema = z.object({
  name: z.string().min(1),
  asin: z.string().min(1),
  style: z.string().nullable().optional(),
  description: z.string().nullable().optional(),
  stars: z.string().nullable().optional(),
  rating_count: z.string().nullable().optional(),
  features: z.array(z.string()),
  images: z.array(z.string()),
  info_table: z.record(z.any()),
}).passthrough();

const ReviewSchema = z.object({
  title: z.string().nullable(),
  text: z.string().nullable(),
  location_and_date: z.string().nullable(),
  verified: z.boolean(),
  rating: z.number().nullable(),
}).passthrough();

test("search schema", async () => {
  const results = await scrapeSearch(SAMPLE_SEARCH_URL, 1);
  assert.ok(results.length >= 1, `expected >=1 results, got ${results.length}`);
  for (const r of results) SearchSchema.parse(r);
});

test("product schema", async () => {
  const variants = await scrapeProduct(SAMPLE_PRODUCT_URL);
  assert.ok(variants.length >= 1);
  for (const v of variants) ProductSchema.parse(v);
});

test("reviews schema", async () => {
  const reviews = await scrapeReviews(SAMPLE_PRODUCT_URL);
  for (const r of reviews) ReviewSchema.parse(r);
});
