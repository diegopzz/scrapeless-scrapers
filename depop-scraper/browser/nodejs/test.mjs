// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { scrapeProduct, scrapeSearch, scrapeShop } from "./depop.mjs";

const SAMPLE_PRODUCT_URL =
  process.env.DEPOP_SAMPLE_PRODUCT_URL ??
  "https://www.depop.com/products/gasbiegzr-levis-jeans-size-25-light-7515/";
const SAMPLE_QUERY = process.env.DEPOP_SAMPLE_QUERY ?? "levi jeans";
const SAMPLE_SHOP = process.env.DEPOP_SAMPLE_SHOP ?? "depopofficial";

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const ProductSchema = z.object({
  id: z.string(),
  url: z.string().min(1),
  title: z.string(),
  price: z.string().nullable(),
  currency: z.string().nullable(),
  brand: z.string().nullable(),
  condition: z.string().nullable(),
  size: z.string().nullable(),
  color: z.string().nullable(),
  description: z.string().nullable(),
  images: z.array(z.string()),
  seller: z.string().nullable(),
  sellerUrl: z.string().nullable(),
  hashtags: z.array(z.string()),
  sold: z.boolean(),
}).passthrough();

const SearchSchema = z.object({
  id: z.string().min(1),
  title: z.string(),
  url: z.string().min(1),
  image: z.string().nullable(),
  price: z.string().nullable(),
  originalPrice: z.string().nullable(),
  seller: z.string().nullable(),
  size: z.string().nullable(),
}).passthrough();

const ShopSchema = z.object({
  username: z.string().min(1),
  url: z.string().min(1),
  displayName: z.string().nullable(),
  bio: z.string().nullable(),
  avatar: z.string().nullable(),
  location: z.string().nullable(),
  followers: z.number().int().nullable(),
  following: z.number().int().nullable(),
  reviews: z.number().int().nullable(),
  rating: z.number().nullable(),
  listings: z.array(z.any()),
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

test("shop schema", async () => {
  const shop = await scrapeShop(SAMPLE_SHOP);
  ShopSchema.parse(shop);
});
