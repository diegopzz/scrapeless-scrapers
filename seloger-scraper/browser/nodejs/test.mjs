// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { scrapeProperty, scrapeSearch } from "./seloger.mjs";

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const SearchSchema = z.object({
  title: z.string(),
  url: z.string().min(1),
  images: z.array(z.string()),
  price: z.string(),
  price_per_m2: z.string().nullable(),
  property_facts: z.array(z.string()),
  address: z.string(),
  agency: z.string().nullable(),
}).passthrough();

const PropertySchema = z.object({
  classified: z.unknown(),
}).passthrough();

const SAMPLE_SEARCH = "https://www.seloger.com/classified-search?distributionTypes=Buy&estateTypes=Apartment&locations=AD08FR13100";
const SAMPLE_PROPERTIES = ["https://www.seloger.com/annonces/achat/appartement/bordeaux-33/193612259.htm"];

test("search schema", async () => {
  const results = await scrapeSearch(SAMPLE_SEARCH, 1);
  assert.ok(results.length >= 1);
  for (const r of results) SearchSchema.parse(r);
});

test("property schema", async () => {
  const results = await scrapeProperty(SAMPLE_PROPERTIES);
  assert.equal(results.length, 1);
  PropertySchema.parse(results[0]);
});
