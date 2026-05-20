// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { scrapeProducts, scrapeSearch } from "./goat.mjs";

const SAMPLE_PRODUCT_URLS = (
  process.env.GOAT_SAMPLE_PRODUCT_URLS ??
  "https://www.goat.com/sneakers/air-jordan-3-retro-white-cement-reimagined-dn3707-100"
).split(",").map((u) => u.trim()).filter(Boolean);
const SAMPLE_QUERY = process.env.GOAT_SAMPLE_QUERY ?? "pumar dark";

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

// const ProductSchema = z.object({
  id: z.number().int(),
  name: z.string(),
  brandName: z.string(),
  sku: z.string(),
  slug: z.string(),
}).passthrough();

const SearchSchema = z.object({
  id: z.string(),
}).passthrough();

test("products schema", async () => {
  const products = await scrapeProducts(SAMPLE_PRODUCT_URLS);
  assert.ok(products.length >= 1);
  for (const p of products) ProductSchema.parse(p);
});

test("search schema", async () => {
  const results = await scrapeSearch(SAMPLE_QUERY, 1);
  assert.ok(results.length >= 1, `expected >=1 results, got ${results.length}`);
  for (const r of results) SearchSchema.parse(r);
});
