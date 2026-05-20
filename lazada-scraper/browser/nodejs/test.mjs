// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { scrapeProduct, scrapeSearch } from "./lazada.mjs";

const SAMPLE_PRODUCT_URL =
  process.env.LAZADA_SAMPLE_PRODUCT_URL ??
  "https://www.lazada.sg/products/pdp-i3529149697.html";
const SAMPLE_QUERY = process.env.LAZADA_SAMPLE_QUERY ?? "iphone case";

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const ProductSchema = z.object({
  id: z.string(),
  url: z.string().min(1),
  title: z.string(),
  brand: z.string().nullable(),
  price: z.string().nullable(),
  originalPrice: z.string().nullable(),
  discount: z.string().nullable(),
  currency: z.string().nullable(),
  rating: z.number().nullable(),
  reviews: z.number().int().nullable(),
  images: z.array(z.string()),
  seller: z.string().nullable(),
  sellerUrl: z.string().nullable(),
  availability: z.string().nullable(),
  description: z.string().nullable(),
  categories: z.array(z.string()),
}).passthrough();

const SearchSchema = z.object({
  id: z.string().min(1),
  title: z.string(),
  url: z.string().min(1),
  image: z.string().nullable(),
  price: z.string().nullable(),
  originalPrice: z.string().nullable(),
  discount: z.string().nullable(),
  rating: z.number().nullable(),
  reviews: z.number().int().nullable(),
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
