// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { scrapeShare } from "./grok.mjs";

const SAMPLE_SHARE_URL =
  process.env.GROK_SAMPLE_URL ??
  "https://grok.com/share/bGVnYWN5_d6991719-5568-4608-b613-609cbd3f2842";

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const GrokMessageSchema = z.object({
  role: z.enum(["user", "assistant"]),
  content: z.string().min(1),
}).passthrough();

const SharedConversationSchema = z.object({
  url: z.string().min(1),
  title: z.string(),
  messages: z.array(GrokMessageSchema),
}).passthrough();

test("share schema", async () => {
  const result = await scrapeShare(SAMPLE_SHARE_URL);
  SharedConversationSchema.parse(result);
  assert.ok(result.messages.length >= 1, "must have at least one message");
  assert.ok(
    result.messages.some((m) => m.role === "user"),
    "must have at least one user message",
  );
  assert.ok(
    result.messages.some((m) => m.role === "assistant"),
    "must have at least one assistant message",
  );
});
