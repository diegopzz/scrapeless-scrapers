// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { scrapeProduct, scrapeSearch } from "./zara.mjs";

const DEFAULT_PRODUCT_URLS = [
  "https://www.zara.com/us/en/zw-collection-fitted-plaid-jacket-p02784381.html",
];
const DEFAULT_SEARCH_URL = "https://www.zara.com/us/en/woman-blazers-l1055.html";

const SAMPLE_PRODUCT_URLS = process.env.ZARA_SAMPLE_PRODUCT_URLS
  ? process.env.ZARA_SAMPLE_PRODUCT_URLS.split(",").map((s) => s.trim())
  : DEFAULT_PRODUCT_URLS;
const SAMPLE_SEARCH_URL = process.env.ZARA_SAMPLE_SEARCH_URL ?? DEFAULT_SEARCH_URL;

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const ProductSchema = z.object({
  id: z.string().min(1),
  url: z.string().min(1),
  name: z.string(),
  brand: z.string(),
  description: z.string().nullable(),
  price: z.number().nullable(),
  priceCurrency: z.string().nullable(),
  availability: z.string().nullable(),
  images: z.array(z.string()),
  color: z.string().nullable(),
  category: z.string().nullable(),
}).passthrough();

const SearchSchema = z.object({
  id: z.string(),
  url: z.string(),
  name: z.string(),
  image: z.string().nullable(),
  price: z.number().nullable(),
  priceCurrency: z.string().nullable(),
}).passthrough();

test("product schema", async () => {
  const products = await scrapeProduct(SAMPLE_PRODUCT_URLS);
  assert.ok(Array.isArray(products) && products.length >= 1);
  for (const p of products) ProductSchema.parse(p);
});

test("search schema", async () => {
  const results = await scrapeSearch(SAMPLE_SEARCH_URL, 1);
  assert.ok(Array.isArray(results));
  for (const r of results) SearchSchema.parse(r);
});
