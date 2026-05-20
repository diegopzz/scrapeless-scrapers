// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { scrapeProduct, scrapeSearch } from "./digikey.mjs";

const SAMPLE_PRODUCT_URL =
  process.env.DIGIKEY_SAMPLE_PRODUCT_URL ??
  "https://www.digikey.com/en/products/detail/texas-instruments/LM358N/277042";
const SAMPLE_QUERY = process.env.DIGIKEY_SAMPLE_QUERY ?? "LM358";

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const ProductSchema = z.object({
  digikeyPartNumber: z.string().min(1),
  manufacturerPartNumber: z.string().min(1),
  manufacturer: z.string().min(1),
  title: z.string().min(1),
  description: z.string().nullable(),
  detailedDescription: z.string().nullable(),
  datasheetUrl: z.string().nullable(),
  productUrl: z.string().min(1),
  imageUrl: z.string().nullable(),
  media: z.array(z.string()),
  breadcrumb: z.array(z.object({ label: z.string().nullable(), url: z.string().nullable() })),
  attributes: z.array(z.object({ label: z.string().nullable(), value: z.string().nullable() })),
  pricing: z.array(z.object({
    breakQuantity: z.string().nullable(),
    unitPrice: z.string().nullable(),
    extendedPrice: z.string().nullable(),
  })),
  stock: z.object({}).passthrough(),
  isActive: z.boolean(),
  isUnavailable: z.boolean(),
}).passthrough();

const SearchSchema = z.object({
  id: z.string(),
  categoryName: z.string().min(1),
  parentCategory: z.string().nullable(),
  productCount: z.string(),
  categoryUrl: z.string().min(1),
  imageUrl: z.string().nullable(),
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
