// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { scrapeProduct, scrapeSearch } from "./alibaba.mjs";

const SAMPLE_PRODUCT_URL =
  process.env.ALIBABA_SAMPLE_PRODUCT_URL ??
  "https://www.alibaba.com/product-detail/Wholesale-Wireless-Bluetooth-Earphones-In-Ear_1601229834677.html";
const SAMPLE_QUERY = process.env.ALIBABA_SAMPLE_QUERY ?? "phone case";

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const ProductSchema = z.object({
  id: z.string(),
  url: z.string().min(1),
  title: z.string(),
  price: z.string().nullable(),
  priceRange: z.string().nullable(),
  moq: z.string().nullable(),
  images: z.array(z.string()),
  supplier: z.string().nullable(),
  supplierUrl: z.string().nullable(),
  supplierYears: z.string().nullable(),
  location: z.string().nullable(),
  rating: z.string().nullable(),
  description: z.string().nullable(),
  categories: z.array(z.string()),
}).passthrough();

const SearchSchema = z.object({
  id: z.string().min(1),
  title: z.string(),
  url: z.string().min(1),
  image: z.string().nullable(),
  price: z.string().nullable(),
  moq: z.string().nullable(),
  supplier: z.string().nullable(),
  location: z.string().nullable(),
}).passthrough();

test("product schema", async () => {
  const product = await scrapeProduct(SAMPLE_PRODUCT_URL);
  ProductSchema.parse(product);
});

test("search schema", async () => {
  const results = await scrapeSearch(SAMPLE_QUERY, 1);
  assert.ok(Array.isArray(results));
  for (const r of results) SearchSchema.parse(r);
});
