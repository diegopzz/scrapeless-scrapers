// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { scrapeAiResponse } from "./google-ai-mode.mjs";

const SAMPLE_QUERY = process.env.GOOGLE_AI_MODE_SAMPLE_QUERY ?? "best health trackers under $200";

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const CitationSchema = z.object({
  title: z.string(),
  url: z.string(),
  source: z.string(),
}).passthrough();

const LinkSchema = z.object({
  url: z.string(),
  text: z.string(),
}).passthrough();

const AiResponseSchema = z.object({
  query: z.string().min(1),
  url: z.string().min(1),
  response_text: z.string(),
  citations: z.array(CitationSchema),
  links: z.array(LinkSchema),
}).passthrough();

test("ai_response schema", async () => {
  const result = await scrapeAiResponse(SAMPLE_QUERY);
  AiResponseSchema.parse(result);
  assert.equal(result.query, SAMPLE_QUERY);
});
