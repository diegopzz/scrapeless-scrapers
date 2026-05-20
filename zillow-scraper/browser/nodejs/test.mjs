// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { scrapeProperties, scrapeSearch } from "./zillow.mjs";

const DEFAULT_SEARCH_URL =
  "https://www.zillow.com/san-francisco-ca/?searchQueryState=%7B%22usersSearchTerm%22%3A%22Nebraska%22" +
  "%2C%22mapBounds%22%3A%7B%22north%22%3A37.890669225201904%2C%22east%22%3A-122.26750460986328" +
  "%2C%22south%22%3A37.659734343010626%2C%22west%22%3A-122.59915439013672%7D" +
  "%2C%22isMapVisible%22%3Atrue%2C%22filterState%22%3A%7B%22sort%22%3A%7B%22value%22%3A%22days%22%7D" +
  "%2C%22ah%22%3A%7B%22value%22%3Atrue%7D%7D%2C%22isListVisible%22%3Atrue%2C%22mapZoom%22%3A12" +
  "%2C%22regionSelection%22%3A%5B%7B%22regionId%22%3A20330%2C%22regionType%22%3A6%7D%5D" +
  "%2C%22pagination%22%3A%7B%7D%7D";
const DEFAULT_PROPERTY_URL =
  "https://www.zillow.com/homedetails/661-Lakeview-Ave-San-Francisco-CA-94112/15192198_zpid/";

const SEARCH_URL = process.env.ZILLOW_SEARCH_URL ?? DEFAULT_SEARCH_URL;
const PROPERTY_URL = process.env.ZILLOW_PROPERTY_URL ?? DEFAULT_PROPERTY_URL;

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

// Mirror Zillow's verbatim field names — listResults entry.
const SearchResultSchema = z.object({
  zpid: z.string(),
  detailUrl: z.string(),
  statusType: z.string().nullish(),
  price: z.string().nullish(),
  address: z.string().nullish(),
}).passthrough();

// Mirror Zillow's verbatim field names — property object.
const PropertySchema = z.object({
  zpid: z.number(),
  streetAddress: z.string().nullish(),
  city: z.string().nullish(),
  state: z.string().nullish(),
  zipcode: z.string().nullish(),
  homeStatus: z.string().nullish(),
}).passthrough();

test("search schema", async () => {
  const results = await scrapeSearch(SEARCH_URL, 1);
  assert.ok(results.length >= 1, `expected >=1 results, got ${results.length}`);
  for (const r of results.slice(0, 5)) SearchResultSchema.parse(r);
});

test("property schema", async () => {
  const results = await scrapeProperties([PROPERTY_URL]);
  assert.equal(results.length, 1);
  PropertySchema.parse(results[0]);
});
