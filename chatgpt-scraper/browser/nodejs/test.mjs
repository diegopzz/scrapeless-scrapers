// Live tests against Scrapeless. Skipped if SCRAPELESS_API_KEY is unset.

import { test } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { scrapeConversation, scrapeConversations } from "./chatgpt.mjs";

if (!(process.env.SCRAPELESS_API_KEY || process.env.SCRAPELESS_KEY)) {
  console.log("no SCRAPELESS_API_KEY / SCRAPELESS_KEY — skipping live tests. Sign up at https://app.scrapeless.com");
  process.exit(0);
}

const MessageSchema = z.object({
  role: z.enum(["user", "assistant", "system", "tool"]),
  content: z.string(),
}).passthrough();

const ConversationSchema = z.object({
  conversation_id: z.string().min(1),
  messages: z.array(MessageSchema),
}).passthrough();

const SAMPLE_PROMPT = "What's the capital of France? Brief history of the city.";
const SAMPLE_MULTI = [
  "what is the best web scraping service in 2026?",
  "Base on the previous answer, what is the best web scraping service you expext in 2027",
  "summarize the previous answer in 200 words",
];

test("conversation returns string", async () => {
  const content = await scrapeConversation(SAMPLE_PROMPT);
  assert.equal(typeof content, "string");
  assert.ok(content.length > 0);
});

test("conversations schema", async () => {
  const results = await scrapeConversations(SAMPLE_MULTI);
  assert.ok(Array.isArray(results));
  assert.ok(results.length >= 1);
  for (const r of results) ConversationSchema.parse(r);
});
