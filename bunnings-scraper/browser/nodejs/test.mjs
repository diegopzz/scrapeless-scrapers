// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { scrapeProduct, scrapeSearch } from "./bunnings.mjs";

const SAMPLE_PRODUCT_URL =
  process.env.BUNNINGS_SAMPLE_PRODUCT_URL ??
  "https://www.bunnings.com.au/ozito-pxc-18v-cordless-drill-driver-kit-pxddk-250c_p0299323";
const SAMPLE_QUERY = process.env.BUNNINGS_SAMPLE_QUERY ?? "cordless drill";

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const ProductSchema = z.object({
  sku: z.string().min(1),
  name: z.string().min(1),
  brand: z.string().nullable(),
  brandLogo: z.string().nullable(),
  description: z.string().nullable(),
  category: z.string().nullable(),
  image: z.string().nullable(),
  price: z.string().nullable(),
  priceCurrency: z.string().nullable(),
  url: z.string().min(1),
  warranty: z.string().nullable(),
  breadcrumb: z.array(z.object({
    name: z.string().nullable(),
    url: z.string().nullable(),
    position: z.number().nullable(),
  })),
}).passthrough();

const SearchSchema = z.object({
  sku: z.string(),
  title: z.string().min(1),
  url: z.string().min(1),
  price: z.string().nullable(),
  image: z.string().nullable(),
  rating: z.string().nullable(),
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
