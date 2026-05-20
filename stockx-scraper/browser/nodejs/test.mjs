// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { scrapeProduct, scrapeSearch } from "./stockx.mjs";

const SAMPLE_PRODUCT_URL =
  process.env.STOCKX_SAMPLE_PRODUCT_URL ?? "https://stockx.com/nike-x-stussy-bucket-hat-black";
const SAMPLE_SEARCH_URL =
  process.env.STOCKX_SAMPLE_SEARCH_URL ?? "https://stockx.com/search?s=nike";

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

// const ProductSchema = z.object({
  id: z.string(),
  title: z.string(),
}).passthrough();

const SearchSchema = z.object({
  id: z.string(),
}).passthrough();

test("product schema", async () => {
  const product = await scrapeProduct(SAMPLE_PRODUCT_URL);
  ProductSchema.parse(product);
});

test("search schema", async () => {
  const results = await scrapeSearch(SAMPLE_SEARCH_URL, 1);
  assert.ok(results.length >= 1, `expected >=1 results, got ${results.length}`);
  for (const r of results) SearchSchema.parse(r);
});
