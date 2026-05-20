// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { scrapeProducts, scrapeSearch } from "./vestiairecollective.mjs";

const SAMPLE_PRODUCT_URLS = (
  process.env.VESTIAIRE_SAMPLE_PRODUCT_URLS ??
  "https://us.vestiairecollective.com/men-accessories/watches/patek-philippe/gold-yellow-gold-patek-philippe-watch-51820408.shtml"
).split(",").map((u) => u.trim()).filter(Boolean);
const SAMPLE_SEARCH_URL =
  process.env.VESTIAIRE_SAMPLE_SEARCH_URL ?? "https://www.vestiairecollective.com/search/?q=louis+vuitton";

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

// const ProductSchema = z.object({
  id: z.string(),
  name: z.string(),
}).passthrough();

const SearchSchema = z.object({
  id: z.number().int(),
}).passthrough();

test("products schema", async () => {
  const products = await scrapeProducts(SAMPLE_PRODUCT_URLS);
  assert.ok(products.length >= 1);
  for (const p of products) ProductSchema.parse(p);
});

test("search schema", async () => {
  const results = await scrapeSearch(SAMPLE_SEARCH_URL, 1);
  assert.ok(results.length >= 1, `expected >=1 results, got ${results.length}`);
  for (const r of results) SearchSchema.parse(r);
});
