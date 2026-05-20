// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { scrapeHotel, scrapeSearch } from "./expedia.mjs";

const SAMPLE_DESTINATION = process.env.EXPEDIA_SAMPLE_DESTINATION ?? "New York";
const SAMPLE_CHECKIN = process.env.EXPEDIA_SAMPLE_CHECKIN ?? "2026-06-15";
const SAMPLE_CHECKOUT = process.env.EXPEDIA_SAMPLE_CHECKOUT ?? "2026-06-16";

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const SearchSchema = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
  url: z.string().min(1),
  price: z.string().nullable(),
  review: z.string().nullable(),
  image: z.string().nullable(),
}).passthrough();

const HotelSchema = z.object({
  id: z.string().min(1),
  url: z.string().min(1),
  name: z.string().min(1),
  address: z.string().nullable(),
  description: z.string(),
  amenities: z.array(z.string()),
  images: z.array(z.string()),
  review: z.string().nullable(),
  price: z.string().nullable(),
}).passthrough();

test("search schema", async () => {
  const results = await scrapeSearch(SAMPLE_DESTINATION, SAMPLE_CHECKIN, SAMPLE_CHECKOUT, 1);
  assert.ok(results.length >= 1, `expected >=1 results, got ${results.length}`);
  for (const r of results) SearchSchema.parse(r);
});

test("hotel schema", async () => {
  const results = await scrapeSearch(SAMPLE_DESTINATION, SAMPLE_CHECKIN, SAMPLE_CHECKOUT, 1);
  assert.ok(results.length >= 1, "no search results to derive a hotel URL from");
  const hotel = await scrapeHotel(results[0].url);
  HotelSchema.parse(hotel);
});
