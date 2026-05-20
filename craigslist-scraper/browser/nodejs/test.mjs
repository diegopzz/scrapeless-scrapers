// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { scrapeListing, scrapeSearch } from "./craigslist.mjs";

const SAMPLE_CITY = process.env.CRAIGSLIST_SAMPLE_CITY ?? "newyork";
const SAMPLE_CATEGORY = process.env.CRAIGSLIST_SAMPLE_CATEGORY ?? "sss";
const SAMPLE_QUERY = process.env.CRAIGSLIST_SAMPLE_QUERY ?? "bicycle";

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const SearchSchema = z.object({
  id: z.string().min(1),
  title: z.string().min(1),
  url: z.string().min(1),
  price: z.string().nullable(),
  location: z.string().nullable(),
  postedAt: z.string().nullable(),
  image: z.string().nullable(),
}).passthrough();

const ListingSchema = z.object({
  id: z.string().min(1),
  url: z.string().min(1),
  title: z.string().min(1),
  price: z.string().nullable(),
  location: z.string().nullable(),
  postedAt: z.string().nullable(),
  description: z.string(),
  attributes: z.array(z.string()),
  images: z.array(z.string()),
  latitude: z.string().nullable(),
  longitude: z.string().nullable(),
  section: z.string().nullable(),
  category: z.string().nullable(),
}).passthrough();

test("search schema", async () => {
  const results = await scrapeSearch(SAMPLE_CITY, SAMPLE_CATEGORY, SAMPLE_QUERY, 1);
  assert.ok(results.length >= 1, `expected >=1 results, got ${results.length}`);
  for (const r of results) SearchSchema.parse(r);
});

test("listing schema", async () => {
  const results = await scrapeSearch(SAMPLE_CITY, SAMPLE_CATEGORY, SAMPLE_QUERY, 1);
  assert.ok(results.length >= 1, "no search results to derive a listing URL from");
  const listing = await scrapeListing(results[0].url);
  ListingSchema.parse(listing);
  assert.equal(listing.url, results[0].url);
});
