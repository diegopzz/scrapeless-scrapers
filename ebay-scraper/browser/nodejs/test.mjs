// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { scrapeProduct, scrapeSearch } from "./ebay.mjs";

const SAMPLE_SEARCH_URL = process.env.EBAY_SAMPLE_SEARCH_URL
  ?? "https://www.ebay.com/sch/i.html?_from=R40&_nkw=iphone&_sacat=0&_ipg=60";
const SAMPLE_PRODUCT_URL = process.env.EBAY_SAMPLE_PRODUCT_URL ?? "https://www.ebay.com/itm/177439887865";

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const SearchSchema = z.object({
  url: z.string().nullable(),
  title: z.string().nullable(),
  price: z.string().nullable(),
  shipping: z.string().nullable(),
  location: z.string().nullable(),
  subtitles: z.string().nullable(),
  photo: z.string().nullable(),
  rating: z.string().nullable(),
  rating_count: z.number().nullable(),
}).passthrough();

const ProductSchema = z.object({
  url: z.string(),
  id: z.string(),
  price_original: z.string().nullable(),
  price_converted: z.string().nullable(),
  name: z.string().nullable().optional(),
  seller_name: z.string().nullable(),
  seller_url: z.string().nullable(),
  photos: z.array(z.string()),
  description_url: z.string().nullable(),
  features: z.record(z.any()),
  variants: z.array(z.any()),
}).passthrough();

test("search schema", async () => {
  const results = await scrapeSearch(SAMPLE_SEARCH_URL, 1);
  assert.ok(results.length >= 1, `expected >=1 results, got ${results.length}`);
  for (const r of results) SearchSchema.parse(r);
});

test("product schema", async () => {
  const product = await scrapeProduct(SAMPLE_PRODUCT_URL);
  ProductSchema.parse(product);
});
