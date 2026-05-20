// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { scrapeProducts, scrapeSearch } from "./nordstorm.mjs";

const SAMPLE_URL =
  process.env.NORDSTORM_SAMPLE_URL ??
  "https://www.nordstrom.com/s/nike-air-max-90-sneaker-men/6549520";
const SAMPLE_SEARCH =
  process.env.NORDSTORM_SAMPLE_SEARCH ??
  "https://www.nordstrom.com/sr?origin=keywordsearch&keyword=indigo";

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const ProductSchema = z.object({
  id: z.any(),
  title: z.string().min(1),
  type: z.any().nullable().optional(),
  typeParent: z.any().nullable().optional(),
  ageGroups: z.any().nullable().optional(),
  reviewAverageRating: z.any().nullable().optional(),
  numberOfReviews: z.any().nullable().optional(),
  brand: z.any().nullable().optional(),
  description: z.any().nullable().optional(),
  features: z.any().nullable().optional(),
  gender: z.any().nullable().optional(),
  isAvailable: z.any().nullable().optional(),
  media: z.array(z.any()),
  variants: z.record(z.any()),
}).passthrough();

const SearchProductSchema = z.object({
  id: z.any(),
}).passthrough();

test("products schema", async () => {
  const products = await scrapeProducts([SAMPLE_URL]);
  assert.ok(products.length >= 1, `expected >=1 products, got ${products.length}`);
  for (const p of products) ProductSchema.parse(p);
});

test("search schema", async () => {
  const results = await scrapeSearch(SAMPLE_SEARCH, 1);
  assert.ok(results.length >= 1, `expected >=1 results, got ${results.length}`);
  for (const r of results) SearchProductSchema.parse(r);
});
