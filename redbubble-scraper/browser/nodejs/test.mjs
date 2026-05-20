// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { scrapeProduct, scrapeSearch } from "./redbubble.mjs";

const DEFAULT_PRODUCT_URLS = [
  "https://www.redbubble.com/i/sticker/Everything-s-good-cat-by-blah707/43977882/7sgk",
];
const DEFAULT_QUERY = "cat";

const SAMPLE_PRODUCT_URLS = process.env.REDBUBBLE_SAMPLE_PRODUCT_URLS
  ? process.env.REDBUBBLE_SAMPLE_PRODUCT_URLS.split(",").map((s) => s.trim())
  : DEFAULT_PRODUCT_URLS;
const SAMPLE_QUERY = process.env.REDBUBBLE_SAMPLE_QUERY ?? DEFAULT_QUERY;

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const ProductSchema = z.object({
  id: z.string().min(1),
  url: z.string().min(1),
  name: z.string(),
  description: z.string().nullable(),
  medium: z.string().nullable(),
  artist: z.string().nullable(),
  price: z.number().nullable(),
  priceCurrency: z.string().nullable(),
  availability: z.string().nullable(),
  images: z.array(z.string()),
  rating: z.number().nullable(),
  reviewCount: z.number().nullable(),
}).passthrough();

const SearchSchema = z.object({
  id: z.string(),
  url: z.string(),
  name: z.string(),
  artist: z.string().nullable(),
  medium: z.string().nullable(),
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
  const results = await scrapeSearch(SAMPLE_QUERY, 1);
  assert.ok(Array.isArray(results) && results.length >= 1, `expected >=1 results, got ${results.length}`);
  for (const r of results) SearchSchema.parse(r);
});
