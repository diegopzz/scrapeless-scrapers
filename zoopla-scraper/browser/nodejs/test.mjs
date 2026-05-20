// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { scrapeProperties, scrapeSearch } from "./zoopla.mjs";

const DEFAULT_PROPERTY_URL = "https://www.zoopla.co.uk/new-homes/details/70337559/";
const DEFAULT_LOCATION_SLUG = "london/islington";
const DEFAULT_QUERY_TYPE = "to-rent";

const PROPERTY_URL = process.env.ZOOPLA_PROPERTY_URL ?? DEFAULT_PROPERTY_URL;
const LOCATION_SLUG = process.env.ZOOPLA_LOCATION_SLUG ?? DEFAULT_LOCATION_SLUG;
const QUERY_TYPE = process.env.ZOOPLA_QUERY_TYPE ?? DEFAULT_QUERY_TYPE;

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const PropertySchema = z.object({
  id: z.number().nullish(),
  url: z.string().nullish(),
  title: z.string().nullish(),
  address: z.string().nullish(),
  price: z.object({}).passthrough(),
  coordinates: z.object({}).passthrough(),
  agent: z.object({}).passthrough(),
}).passthrough();

const SearchResultSchema = z.object({
  url: z.string().nullish(),
  priceCurrency: z.string(),
}).passthrough();

test("properties schema", async () => {
  const results = await scrapeProperties([PROPERTY_URL]);
  assert.equal(results.length, 1);
  PropertySchema.parse(results[0]);
});

test("search schema", async () => {
  const results = await scrapeSearch(false, LOCATION_SLUG, 1, QUERY_TYPE);
  assert.ok(results.length >= 1);
  for (const r of results.slice(0, 5)) SearchResultSchema.parse(r);
});
