// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { scrapeSearch } from "./perplexity.mjs";

const SAMPLE_PROMPT = process.env.PERPLEXITY_SAMPLE_PROMPT ?? "top 3 smartphones in 2025";

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const CitationSchema = z.object({
  url: z.string().min(1),
  domain: z.string(),
  title: z.string(),
}).passthrough();

const SearchSchema = z.object({
  query: z.string().min(1),
  url: z.string().min(1),
  answer_text: z.string(),
  citations: z.array(CitationSchema),
}).passthrough();

test("search schema", async () => {
  const result = await scrapeSearch(SAMPLE_PROMPT);
  SearchSchema.parse(result);
});
