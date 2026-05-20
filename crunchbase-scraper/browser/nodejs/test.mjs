// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { scrapeCompany, scrapePerson } from "./crunchbase.mjs";

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const SAMPLE_COMPANY_URL = process.env.CRUNCHBASE_SAMPLE_COMPANY_URL ??
  "https://www.crunchbase.com/organization/tesla-motors/people";
const SAMPLE_PERSON_URL = process.env.CRUNCHBASE_SAMPLE_PERSON_URL ??
  "https://www.crunchbase.com/person/elon-musk";

const CompanySchema = z.object({
  organization: z.record(z.any()),
  employees: z.array(z.any()),
}).passthrough();

test("company schema", async () => {
  const result = await scrapeCompany(SAMPLE_COMPANY_URL);
  CompanySchema.parse(result);
});

test("person schema", async () => {
  const result = await scrapePerson(SAMPLE_PERSON_URL);
  assert.equal(typeof result, "object");
});
