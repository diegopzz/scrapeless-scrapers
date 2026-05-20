// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { scrapeProduct, scrapeSearch, scrapeShop } from "./etsy.mjs";

const SAMPLE_SEARCH_URL =
  process.env.ETSY_SAMPLE_SEARCH_URL ?? "https://www.etsy.com/search?q=wood+laptop+stand";
const SAMPLE_PRODUCT_URLS = (
  process.env.ETSY_SAMPLE_PRODUCT_URLS ?? "https://www.etsy.com/listing/1552627931"
).split(",").map((u) => u.trim()).filter(Boolean);
const SAMPLE_SHOP_URLS = (
  process.env.ETSY_SAMPLE_SHOP_URLS ?? "https://www.etsy.com/shop/FalkelDesign"
).split(",").map((u) => u.trim()).filter(Boolean);

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

// const SearchSchema = z.object({
  productLink: z.string(),
  productTitle: z.string(),
  productImage: z.string(),
  seller: z.string().nullable(),
  listingType: z.string(),
  productRate: z.number().nullable(),
  numberOfReviews: z.number().int().nullable(),
  freeShipping: z.string(),
  productPrice: z.number(),
  priceCurrency: z.string(),
  originalPrice: z.string().nullable(),
  discount: z.string(),
}).passthrough();

const ProductSchema = z.object({
  "@type": z.string().optional(),
  "@context": z.string().optional(),
  url: z.string().optional(),
  name: z.string().optional(),
}).passthrough();

const ShopSchema = z.object({
  "@type": z.string().optional(),
  url: z.string(),
  itemListElement: z.array(z.any()).optional(),
}).passthrough();

test("search schema", async () => {
  const results = await scrapeSearch(SAMPLE_SEARCH_URL, 1);
  assert.ok(results.length >= 1, `expected >=1 results, got ${results.length}`);
  for (const r of results) SearchSchema.parse(r);
});

test("product schema", async () => {
  const products = await scrapeProduct(SAMPLE_PRODUCT_URLS);
  assert.ok(products.length >= 1);
  for (const p of products) ProductSchema.parse(p);
});

test("shop schema", async () => {
  const shops = await scrapeShop(SAMPLE_SHOP_URLS);
  assert.ok(shops.length >= 1);
  for (const s of shops) ShopSchema.parse(s);
});
