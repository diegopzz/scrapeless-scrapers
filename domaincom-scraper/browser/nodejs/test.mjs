// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { scrapeProperties, scrapeSearch } from "./domaincom.mjs";

const SAMPLE_URL =
  process.env.DOMAINCOM_SAMPLE_URL ??
  "https://www.domain.com.au/610-399-bourke-street-melbourne-vic-3000-2018835548";
const SAMPLE_SEARCH =
  process.env.DOMAINCOM_SAMPLE_SEARCH ??
  "https://www.domain.com.au/sale/melbourne-vic-3000/";

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const PropertyListedSchema = z.object({
  url: z.string(),
  listingId: z.any().nullable().optional(),
  suburb: z.any().nullable().optional(),
  postcode: z.any().nullable().optional(),
  agents: z.any().nullable().optional(),
  gallery: z.any().nullable().optional(),
}).passthrough();

const SearchItemSchema = z.object({
  id: z.any().nullable(),
  listingType: z.any().nullable().optional(),
  listingModel: z.any().nullable().optional(),
}).passthrough();

test("properties schema", async () => {
  const properties = await scrapeProperties([SAMPLE_URL]);
  assert.ok(properties.length >= 1, `expected >=1 properties, got ${properties.length}`);
  for (const p of properties) PropertyListedSchema.parse(p);
});

test("search schema", async () => {
  const results = await scrapeSearch(SAMPLE_SEARCH, 1);
  assert.ok(results.length >= 1, `expected >=1 results, got ${results.length}`);
  for (const r of results) SearchItemSchema.parse(r);
});
