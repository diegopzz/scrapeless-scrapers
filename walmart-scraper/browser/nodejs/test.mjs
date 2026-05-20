// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { scrapeProducts, scrapeSearch } from "./walmart.mjs";

const SAMPLE_PRODUCT_URLS = process.env.WALMART_SAMPLE_PRODUCT_URLS
  ? process.env.WALMART_SAMPLE_PRODUCT_URLS.split(",").map((s) => s.trim()).filter(Boolean)
  : ["https://www.walmart.com/ip/1736740710"];
const SAMPLE_QUERY = process.env.WALMART_SAMPLE_QUERY ?? "laptop";

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const ProductWrapperSchema = z.object({
  product: z.record(z.any()),
  reviews: z.record(z.any()).nullable().optional(),
}).passthrough();

const SearchItemSchema = z.object({
  id: z.string().optional(),
  name: z.string().optional(),
}).passthrough();

test("products schema", async () => {
  const products = await scrapeProducts(SAMPLE_PRODUCT_URLS);
  assert.ok(products.length >= 1);
  for (const p of products) {
    if (p.error) continue;
    ProductWrapperSchema.parse(p);
  }
});

test("search schema", async () => {
  const results = await scrapeSearch(SAMPLE_QUERY, "best_seller", 1);
  assert.ok(results.length >= 1, `expected >=1 results, got ${results.length}`);
  for (const r of results) SearchItemSchema.parse(r);
});
