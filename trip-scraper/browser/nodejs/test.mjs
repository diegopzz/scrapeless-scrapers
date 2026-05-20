// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { scrapeHotel, scrapeSearch } from "./trip.mjs";

const SAMPLE_CITY = process.env.TRIP_SAMPLE_CITY_ID ?? "53";
const SAMPLE_CHECKIN = process.env.TRIP_SAMPLE_CHECKIN ?? "2026/06/15";
const SAMPLE_CHECKOUT = process.env.TRIP_SAMPLE_CHECKOUT ?? "2026/06/16";

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const SearchSchema = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
  url: z.string().min(1),
  score: z.string().nullable(),
  reviewWord: z.string().nullable(),
  reviewCount: z.number().nullable(),
  price: z.string().nullable(),
  totalPrice: z.string().nullable(),
  tags: z.array(z.string()),
  location: z.string().nullable(),
  image: z.string().nullable(),
}).passthrough();

const HotelSchema = z.object({
  id: z.string().min(1),
  url: z.string().min(1),
  name: z.string().min(1),
  address: z.string().nullable(),
  score: z.string().nullable(),
  reviewCount: z.number().nullable(),
  description: z.string(),
  amenities: z.array(z.string()),
  images: z.array(z.string()),
  price: z.string().nullable(),
}).passthrough();

test("search schema", async () => {
  const results = await scrapeSearch(SAMPLE_CITY, SAMPLE_CHECKIN, SAMPLE_CHECKOUT, 1);
  assert.ok(results.length >= 1, `expected >=1 results, got ${results.length}`);
  for (const r of results) SearchSchema.parse(r);
});

test("hotel schema", async () => {
  const results = await scrapeSearch(SAMPLE_CITY, SAMPLE_CHECKIN, SAMPLE_CHECKOUT, 1);
  assert.ok(results.length >= 1, "no search results to derive a hotel id from");
  const hotel = await scrapeHotel(results[0].id, SAMPLE_CHECKIN, SAMPLE_CHECKOUT);
  HotelSchema.parse(hotel);
});
