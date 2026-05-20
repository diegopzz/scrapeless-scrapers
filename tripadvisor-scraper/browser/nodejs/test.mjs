// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { scrapeHotel, scrapeLocationData, scrapeSearch } from "./tripadvisor.mjs";

const SAMPLE_QUERY = process.env.TRIPADVISOR_SAMPLE_QUERY ?? "Malta";
const SAMPLE_SEARCH_URL = process.env.TRIPADVISOR_SAMPLE_SEARCH_URL ??
  "https://www.tripadvisor.com/Hotels-g60763-oa30-New_York_City_New_York-Hotels.html";
const SAMPLE_HOTEL_URL = process.env.TRIPADVISOR_SAMPLE_HOTEL_URL ??
  "https://www.tripadvisor.com/Hotel_Review-g190327-d264936-Reviews-1926_Hotel_Spa-Sliema_Island_of_Malta.html";

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const LocationSchema = z.object({
  localizedName: z.string().min(1),
  url: z.string(),
}).passthrough();

const SearchSchema = z.object({
  url: z.string().min(1),
  name: z.string().nullable(),
}).passthrough();

const ReviewSchema = z.object({
  title: z.string().nullable(),
  text: z.string().nullable(),
  rate: z.number().nullable(),
  tripDate: z.string().nullable(),
  tripType: z.string().nullable(),
}).passthrough();

const HotelSchema = z.object({
  basic_data: z.object({}).passthrough(),
  description: z.string().nullable(),
  featues: z.array(z.string()),
  reviews: z.array(ReviewSchema),
}).passthrough();

test("location autocomplete schema", async () => {
  const results = await scrapeLocationData(SAMPLE_QUERY);
  assert.ok(results.length >= 1, `expected >=1 location results, got ${results.length}`);
  for (const r of results) LocationSchema.parse(r);
});

test("search schema", async () => {
  const results = await scrapeSearch(SAMPLE_SEARCH_URL, 1);
  assert.ok(results.length >= 1, `expected >=1 search results, got ${results.length}`);
  for (const r of results) SearchSchema.parse(r);
});

test("hotel schema", async () => {
  const hotel = await scrapeHotel(SAMPLE_HOTEL_URL, 1);
  HotelSchema.parse(hotel);
});
