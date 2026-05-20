// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { scrapeHotel, scrapeHotelReviews, scrapeSearch, searchLocationSuggestions } from "./bookingcom.mjs";

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const LocationSchema = z.object({
  dest_id: z.string().min(1),
  dest_type: z.string(),
  value: z.string(),
}).passthrough();

const SearchResultSchema = z.object({
  displayName: z.object({ text: z.string().min(1) }).passthrough(),
  basicPropertyData: z.object({}).passthrough(),
  location: z.object({}).passthrough(),
  policies: z.object({ showFreeCancellation: z.boolean() }).passthrough(),
}).passthrough();

const HotelSchema = z.object({
  url: z.string().min(1),
  id: z.string().nullable(),
  title: z.string().nullable(),
  description: z.string(),
  address: z.string().nullable(),
  images: z.array(z.string()),
  lat: z.string(),
  lng: z.string(),
  features: z.record(z.array(z.string())),
  price: z.array(z.any()),
}).passthrough();

const today = new Date();
const fmt = (d) => d.toISOString().slice(0, 10);
const SAMPLE_QUERY = "Malta";
const SAMPLE_CHECKIN = fmt(new Date(today.getTime() + 7 * 86400000));
const SAMPLE_CHECKOUT = fmt(new Date(today.getTime() + 14 * 86400000));
const SAMPLE_HOTEL_URL = "https://www.booking.com/hotel/gb/gardencourthotel.en-gb.html";

test("location suggestions schema", async () => {
  const data = await searchLocationSuggestions(SAMPLE_QUERY);
  assert.ok(Array.isArray(data?.results));
  assert.ok(data.results.length >= 1);
  LocationSchema.parse(data.results[0]);
});

test("search schema", async () => {
  const results = await scrapeSearch(SAMPLE_QUERY, SAMPLE_CHECKIN, SAMPLE_CHECKOUT, 1, 1);
  assert.ok(Array.isArray(results));
  if (results.length) SearchResultSchema.parse(results[0]);
});

test("hotel schema", async () => {
  const hotel = await scrapeHotel(SAMPLE_HOTEL_URL, SAMPLE_CHECKIN, 7);
  HotelSchema.parse(hotel);
});

test("hotel reviews schema", async () => {
  const reviews = await scrapeHotelReviews(SAMPLE_HOTEL_URL, 1);
  assert.ok(Array.isArray(reviews));
});
