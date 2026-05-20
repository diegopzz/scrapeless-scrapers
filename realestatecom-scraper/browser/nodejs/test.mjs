// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { scrapeProperties, scrapeSearch } from "./realestatecom.mjs";

const SAMPLE_URL =
  process.env.REALESTATECOM_SAMPLE_URL ??
  "https://www.realestate.com.au/property-house-vic-tarneit-143160680";
const SAMPLE_SEARCH =
  process.env.REALESTATECOM_SAMPLE_SEARCH ??
  "https://www.realestate.com.au/buy/in-melbourne+-+northern+region,+vic/list-1";

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const PropertySchema = z.object({
  id: z.string().min(1),
  propertyType: z.string().nullable().optional(),
  description: z.string().nullable().optional(),
  propertyLink: z.string().nullable().optional(),
  address: z.any().nullable().optional(),
  propertySizes: z.any().nullable().optional(),
  generalFeatures: z.any().nullable().optional(),
  propertyFeatures: z.array(z.any()).nullable().optional(),
  images: z.array(z.string()).nullable().optional(),
  videos: z.any().nullable().optional(),
  floorplans: z.any().nullable().optional(),
  listingCompany: z.any().nullable().optional(),
  listers: z.any().nullable().optional(),
  auction: z.any().nullable().optional(),
}).passthrough();

test("property schema", async () => {
  const properties = await scrapeProperties([SAMPLE_URL]);
  assert.ok(properties.length >= 1, `expected >=1 properties, got ${properties.length}`);
  for (const p of properties) PropertySchema.parse(p);
});

test("search schema", async () => {
  const results = await scrapeSearch(SAMPLE_SEARCH, 1);
  assert.ok(results.length >= 1, `expected >=1 results, got ${results.length}`);
  for (const r of results) PropertySchema.parse(r);
});
