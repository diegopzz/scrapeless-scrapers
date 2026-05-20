// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { scrapeProperties, scrapeSearch } from "./homegate.mjs";

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const ListingSchema = z.record(z.unknown());
const SearchEntrySchema = z.record(z.unknown());

const SAMPLE_PROPERTIES = ["https://www.homegate.ch/rent/4002086534"];
const SAMPLE_SEARCH = "https://www.homegate.ch/rent/real-estate/city-bern/matching-list";

test("properties shape", async () => {
  const results = await scrapeProperties(SAMPLE_PROPERTIES);
  assert.ok(results.length >= 1);
  for (const r of results) ListingSchema.parse(r);
});

test("search shape", async () => {
  const results = await scrapeSearch(SAMPLE_SEARCH, false, 1);
  assert.ok(Array.isArray(results));
  assert.ok(results.length >= 1);
  for (const r of results) SearchEntrySchema.parse(r);
});
