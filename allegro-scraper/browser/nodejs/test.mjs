// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { scrapeProduct, scrapeSearch } from "./allegro.mjs";

const QUERY = process.env.ALLEGRO_QUERY ?? "iphone";
const PRODUCT_URLS = (process.env.ALLEGRO_PRODUCT_URLS
  ?? "https://allegro.pl/oferta/iphone-15-pro-256gb-natural-titanium-14488061197").split(",");

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const SearchItemSchema = z.object({
  product_id: z.string().nullable().optional(),
  offer_id: z.string().nullable().optional(),
  title: z.string(),
  url: z.string(),
}).passthrough();

const SearchSchema = z.object({
  products: z.array(SearchItemSchema),
  scraped_pages: z.number(),
  products_count: z.number(),
  total_pages: z.number().nullable().optional(),
  total_count: z.number().nullable().optional(),
}).passthrough();

const ProductSchema = z.object({
  title: z.string().min(1),
  price: z.record(z.any()),
  images: z.array(z.string()).optional(),
  rating: z.string().nullable().optional(),
  specifications: z.array(z.any()).optional(),
  seller: z.record(z.any()).optional(),
  reviews: z.array(z.any()).optional(),
  allegro_smart_badge: z.boolean().optional(),
}).passthrough();

test("search schema", async () => {
  const result = await scrapeSearch(QUERY, 1);
  SearchSchema.parse(result);
  assert.ok(result.products_count >= 1);
});

test("product schema", async () => {
  const products = await scrapeProduct(PRODUCT_URLS);
  assert.equal(products.length, PRODUCT_URLS.length);
  for (const p of products) ProductSchema.parse(p);
});
