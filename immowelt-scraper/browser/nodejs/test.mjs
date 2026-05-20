// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { scrapeProperties, scrapeSearch } from "./immowelt.mjs";

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const SearchEntrySchema = z.record(z.unknown());
const PropertySchema = z.object({
  sections: z.unknown(),
  id: z.unknown(),
  brand: z.unknown().optional(),
  tags: z.unknown().optional(),
  contactSections: z.unknown().optional(),
}).passthrough();

const SAMPLE_SEARCH = "https://www.immowelt.de/classified-search?distributionTypes=Buy&estateTypes=Apartment&locations=AD08DE6345";
const SAMPLE_PROPERTIES = ["https://www.immowelt.de/expose/k2ag632"];

test("search shape", async () => {
  const results = await scrapeSearch(SAMPLE_SEARCH, 1);
  assert.ok(results.length >= 1);
  for (const r of results) SearchEntrySchema.parse(r);
});

test("properties shape", async () => {
  const results = await scrapeProperties(SAMPLE_PROPERTIES);
  assert.ok(results.length >= 1);
  for (const r of results) PropertySchema.parse(r);
});
