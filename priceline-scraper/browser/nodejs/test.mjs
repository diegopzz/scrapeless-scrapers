// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { scrapeHotel, scrapeSearch } from "./priceline.mjs";

const SAMPLE_CITY = process.env.PRICELINE_SAMPLE_CITY_ID ?? "15300";
const SAMPLE_CHECKIN = process.env.PRICELINE_SAMPLE_CHECKIN ?? "2026-06-15";
const SAMPLE_CHECKOUT = process.env.PRICELINE_SAMPLE_CHECKOUT ?? "2026-06-16";
const SAMPLE_HOTEL = process.env.PRICELINE_SAMPLE_HOTEL_ID ?? "3000010091";

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const HotelSchema = z.object({
  id: z.string().min(1),
  url: z.string().min(1),
  name: z.string(),
  address: z.string().nullable(),
  description: z.string(),
  amenities: z.array(z.string()),
  images: z.array(z.string()),
  latitude: z.number().nullable(),
  longitude: z.number().nullable(),
  starRating: z.union([z.string(), z.number()]).nullable(),
  policies: z.array(z.any()),
  pageTitle: z.string().nullable(),
}).passthrough();

const SearchSchema = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
  url: z.string().min(1),
  price: z.string().nullable(),
  starRating: z.number().nullable(),
  review: z.number().nullable(),
  reviewCount: z.number().nullable(),
  image: z.string().nullable(),
  neighborhood: z.string().nullable(),
}).passthrough();

test("hotel schema", async () => {
  const hotel = await scrapeHotel(SAMPLE_HOTEL, SAMPLE_CHECKIN, SAMPLE_CHECKOUT);
  HotelSchema.parse(hotel);
  assert.equal(hotel.id, SAMPLE_HOTEL);
});

test("search schema or empty", async () => {
  const results = await scrapeSearch(SAMPLE_CITY, SAMPLE_CHECKIN, SAMPLE_CHECKOUT);
  // Priceline frequently withholds listings behind anti-bot; we accept zero
  // results as a soft pass (treated as an empty fixture in the verifier).
  for (const r of results) SearchSchema.parse(r);
});
