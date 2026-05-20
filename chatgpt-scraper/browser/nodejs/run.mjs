// Run ChatGPT scrape functions live and optionally write results/*.json.
//
// Usage:
//   SCRAPELESS_API_KEY=sk_... node run.mjs
//   SCRAPELESS_API_KEY=sk_... SAVE_TEST_RESULTS=true node run.mjs

import { scrapeConversation, scrapeConversations } from "./chatgpt.mjs";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const RESULTS_DIR = path.resolve(HERE, "results");

function saveOrPrint(name, payload, ext = "json") {
  const text = ext === "json"
    ? JSON.stringify(payload, null, 2)
    : (typeof payload === "string" ? payload : JSON.stringify(payload));
  if ((process.env.SAVE_TEST_RESULTS ?? "").toLowerCase() === "true") {
    fs.mkdirSync(RESULTS_DIR, { recursive: true });
    const out = path.join(RESULTS_DIR, `${name}.${ext}`);
    fs.writeFileSync(out, text, "utf-8");
    console.error(`wrote ${out}`);
  } else {
    console.log(text);
  }
}

const SAMPLE_PROMPT = "What's the capital of France? with Brief History of the city.";
const SAMPLE_MULTI = [
  "what is the best web scraping service in 2026?",
  "Base on the previous answer, what is the best web scraping service you expext in 2027",
  "summarize the previous answer in 200 words",
];

console.error("== conversation ==");
saveOrPrint("conversation", await scrapeConversation(SAMPLE_PROMPT), "md");

console.error("== conversations ==");
saveOrPrint("conversations", await scrapeConversations(SAMPLE_MULTI));
