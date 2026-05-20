// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { scrapeProduct, scrapeSearch } from "./1688.mjs";

const SAMPLE_ID = process.env.SCRAPELESS_1688_SAMPLE_ID ?? "611499776800";
const SAMPLE_QUERY = process.env.SCRAPELESS_1688_SAMPLE_QUERY ?? "phone case";

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const ProductSchema = z.object({
  id: z.string().min(1),
  url: z.string().min(1),
  title: z.string(),
  price: z.string().nullable(),
  priceRange: z.string().nullable(),
  moq: z.string().nullable(),
  images: z.array(z.string()),
  seller: z.string().nullable(),
  sellerUrl: z.string().nullable(),
  location: z.string().nullable(),
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
  seller: z.string().nullable(),
  location: z.string().nullable(),
}).passthrough();

test("product schema", async () => {
  const product = await scrapeProduct(SAMPLE_ID);
  ProductSchema.parse(product);
  assert.equal(product.id, SAMPLE_ID);
});

test("search schema", async () => {
  const results = await scrapeSearch(SAMPLE_QUERY, 1);
  assert.ok(Array.isArray(results));
  for (const r of results) SearchSchema.parse(r);
});
