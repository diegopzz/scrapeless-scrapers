// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { scrapeProperty, scrapeSearch } from "./realtorcom.mjs";

const DEFAULT_PROPERTY_URL =
  "https://www.realtor.com/realestateandhomes-detail/12355-Attlee-Dr_Houston_TX_77077_M70330-35605";
const DEFAULT_STATE = "CA";
const DEFAULT_CITY = "San-Francisco";

const PROPERTY_URL = process.env.REALTORCOM_PROPERTY_URL ?? DEFAULT_PROPERTY_URL;
const STATE = process.env.REALTORCOM_STATE ?? DEFAULT_STATE;
const CITY = process.env.REALTORCOM_CITY ?? DEFAULT_CITY;

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const PropertySchema = z.object({
  id: z.string().nullish(),
  url: z.string().nullish(),
  status: z.string().nullish(),
  list_price: z.number().nullish(),
}).passthrough();

const SearchResultSchema = z.object({
  property_id: z.string(),
}).passthrough();

test("property schema", async () => {
  const data = await scrapeProperty(PROPERTY_URL);
  assert.equal(typeof data, "object");
  PropertySchema.parse(data);
});

test("search schema", async () => {
  const results = await scrapeSearch(STATE, CITY, 1);
  assert.ok(results.length >= 1);
  for (const r of results.slice(0, 5)) SearchResultSchema.parse(r);
});
