// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import {
  findAliexpressProducts,
  scrapeProduct,
  scrapeProductReviews,
  scrapeSearch,
} from "./aliexpress.mjs";

const SAMPLE_SEARCH_URL = process.env.ALIEXPRESS_SAMPLE_SEARCH_URL
  ?? "https://www.aliexpress.com/w/wholesale-drills.html?catId=0&SearchText=drills";
const SAMPLE_PRODUCT_URL = process.env.ALIEXPRESS_SAMPLE_PRODUCT_URL
  ?? "https://www.aliexpress.com/item/3256807619226115.html";
const SAMPLE_REVIEW_PID = process.env.ALIEXPRESS_SAMPLE_REVIEW_PRODUCT_ID ?? "1005006717259012";
const SAMPLE_CATEGORY_URL = process.env.ALIEXPRESS_SAMPLE_CATEGORY_URL
  ?? "https://www.aliexpress.com/category/5090301/cellphones.html";

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const ProductSchema = z.object({
  info: z.record(z.any()),
  pricing: z.object({
    priceCurrency: z.string(),
    price: z.number().nullable(),
    originalPrice: z.union([z.number(), z.string()]),
    discount: z.string(),
  }).passthrough(),
  specifications: z.array(z.any()),
  delivery: z.string().nullable(),
  faqs: z.array(z.any()),
}).passthrough();

const ReviewsSchema = z.object({
  reviews: z.array(z.any()),
  evaluation_stats: z.record(z.any()),
}).passthrough();

test("search", async () => {
  const results = await scrapeSearch(SAMPLE_SEARCH_URL, 1);
  assert.ok(Array.isArray(results));
  assert.ok(results.length >= 1);
});

test("product schema", async () => {
  const product = await scrapeProduct(SAMPLE_PRODUCT_URL);
  ProductSchema.parse(product);
});

test("reviews schema", async () => {
  const data = await scrapeProductReviews(SAMPLE_REVIEW_PID, 1);
  ReviewsSchema.parse(data);
});

test("category", async () => {
  const products = await findAliexpressProducts(SAMPLE_CATEGORY_URL, 1);
  assert.ok(Array.isArray(products));
});
