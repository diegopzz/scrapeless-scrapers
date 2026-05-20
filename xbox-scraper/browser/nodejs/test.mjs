// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { scrapeProduct, scrapeSearch } from "./xbox.mjs";

const SAMPLE_PRODUCT_URL =
  process.env.XBOX_SAMPLE_PRODUCT_URL ??
  "https://www.xbox.com/en-us/games/store/marvel-rivals/9N8PMW7QMD3D";
const SAMPLE_QUERY = process.env.XBOX_SAMPLE_QUERY ?? "all";

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const VideoSchema = z.object({
  name: z.string().nullable(),
  thumbnailUrl: z.string().nullable(),
  contentUrl: z.string().nullable(),
}).passthrough();

const ProductSchema = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
  description: z.string().nullable(),
  url: z.string().min(1),
  image: z.string().nullable(),
  publisher: z.string().nullable(),
  developer: z.string().nullable(),
  brand: z.string().nullable(),
  genre: z.array(z.string()),
  platforms: z.array(z.string()),
  contentRating: z.string().nullable(),
  releaseDate: z.string().nullable(),
  ratingValue: z.number().nullable(),
  ratingCount: z.number().nullable(),
  price: z.string().nullable(),
  priceCurrency: z.string().nullable(),
  availability: z.string().nullable(),
  isFree: z.boolean().nullable(),
  featureList: z.string().nullable(),
  videos: z.array(VideoSchema),
}).passthrough();

const SearchSchema = z.object({
  id: z.string().min(1),
  slug: z.string().min(1),
  name: z.string().min(1),
  url: z.string().min(1),
  image: z.string().nullable(),
  badge: z.string().nullable(),
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
