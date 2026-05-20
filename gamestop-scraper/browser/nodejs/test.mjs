// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { scrapeProduct, scrapeSearch } from "./gamestop.mjs";

const SAMPLE_PRODUCT_URL =
  process.env.GAMESTOP_SAMPLE_PRODUCT_URL ??
  "https://www.gamestop.com/video-games/nintendo-switch/products/tomodachi-life-living-the-dream---nintendo-switch/440814.html";
const SAMPLE_QUERY = process.env.GAMESTOP_SAMPLE_QUERY ?? "zelda";

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const OfferSchema = z.object({
  name: z.string().nullable(),
  sku: z.string().nullable(),
  price: z.string().nullable(),
  priceCurrency: z.string().nullable(),
  availability: z.string().nullable(),
}).passthrough();

const ProductSchema = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
  brand: z.string().nullable(),
  description: z.string().nullable(),
  platform: z.string().nullable(),
  category: z.string().nullable(),
  genre: z.string().nullable(),
  contentRating: z.string().nullable(),
  producer: z.string().nullable(),
  publisher: z.string().nullable(),
  image: z.string().nullable(),
  url: z.string().min(1),
  price: z.string().nullable(),
  priceCurrency: z.string().nullable(),
  availability: z.string().nullable(),
  offers: z.array(OfferSchema),
  breadcrumb: z.array(z.object({
    name: z.string().nullable(),
    url: z.string().nullable(),
    position: z.number().nullable(),
  })),
}).passthrough();

const SearchSchema = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
  url: z.string().min(1),
  price: z.string().nullable(),
  salePrice: z.string().nullable(),
  platform: z.string().nullable(),
  image: z.string().nullable(),
  ratingPercent: z.string().nullable(),
  ratingCount: z.string().nullable(),
  available: z.boolean().nullable(),
  isDigital: z.boolean().nullable(),
}).passthrough();

test("product schema", async () => {
  const product = await scrapeProduct(SAMPLE_PRODUCT_URL);
  ProductSchema.parse(product);
});

test("search schema", async () => {
  const results = await scrapeSearch(SAMPLE_QUERY, 1);
  assert.ok(results.length >= 1, `expected >=1 results, got ${results.length}`);
  for (const r of results) SearchSchema.parse(r);
});
