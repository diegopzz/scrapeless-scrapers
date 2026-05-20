// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { scrapeDestination, scrapeSearch } from "./trivago.mjs";

const SAMPLE_DESTINATION_URL = process.env.TRIVAGO_SAMPLE_DESTINATION_URL
  ?? "https://www.trivago.com/en-US/odr/hotels-new-york-city-new-york-united-states-of-america?search=200-2755";

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const SearchSchema = z.object({
  position: z.number(),
  name: z.string().min(1),
  url: z.string(),
  address: z.string().nullable(),
  image: z.string().nullable(),
  description: z.string().nullable(),
  priceRange: z.string().nullable(),
  ratingValue: z.number().nullable(),
  reviewCount: z.number().nullable(),
  bestRating: z.number().nullable(),
  worstRating: z.number().nullable(),
}).passthrough();

const DestinationSchema = z.object({
  url: z.string().min(1),
  name: z.string(),
  breadcrumbs: z.array(z.string()),
  totalHotels: z.number().nullable(),
  faq: z.array(z.any()),
  topHotels: z.array(z.any()),
}).passthrough();

test("search schema", async () => {
  const results = await scrapeSearch(SAMPLE_DESTINATION_URL, 1);
  assert.ok(results.length >= 1, `expected >=1 results, got ${results.length}`);
  for (const r of results) SearchSchema.parse(r);
});

test("destination schema", async () => {
  const dest = await scrapeDestination(SAMPLE_DESTINATION_URL);
  DestinationSchema.parse(dest);
});
