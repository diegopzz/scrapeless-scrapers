// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { findLocations, scrapeProperties, scrapeSearch } from "./rightmove.mjs";

const DEFAULT_PROPERTY_URL = "https://www.rightmove.co.uk/properties/149360984#/";
const DEFAULT_LOCATION_QUERY = "cornwall";
const DEFAULT_LOCATION_NAME = "Cornwall";

const PROPERTY_URL = process.env.RIGHTMOVE_PROPERTY_URL ?? DEFAULT_PROPERTY_URL;
const LOCATION_QUERY = process.env.RIGHTMOVE_LOCATION_QUERY ?? DEFAULT_LOCATION_QUERY;
const LOCATION_NAME = process.env.RIGHTMOVE_LOCATION_NAME ?? DEFAULT_LOCATION_NAME;

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const PropertySchema = z.object({
  id: z.union([z.number(), z.string()]).nullish(),
  available: z.boolean().nullish(),
  archived: z.boolean().nullish(),
  bedrooms: z.number().nullish(),
  bathrooms: z.number().nullish(),
  type: z.string().nullish(),
  property_type: z.string().nullish(),
  title: z.string().nullish(),
  price: z.string().nullish(),
}).passthrough();

const SearchResultSchema = z.object({
  id: z.union([z.number(), z.string()]),
}).passthrough();

test("properties schema", async () => {
  const results = await scrapeProperties([PROPERTY_URL]);
  assert.equal(results.length, 1);
  PropertySchema.parse(results[0]);
});

test("find_locations + search", async () => {
  const locations = await findLocations(LOCATION_QUERY);
  assert.ok(Array.isArray(locations) && locations.length >= 1);
  const results = await scrapeSearch(LOCATION_NAME, locations[0], false, 24);
  assert.ok(results.length >= 1);
  for (const r of results.slice(0, 5)) SearchResultSchema.parse(r);
});
