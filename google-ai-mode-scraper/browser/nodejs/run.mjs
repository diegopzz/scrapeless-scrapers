// Run the GoogleAiMode scrape function live and optionally write results/*.json.
//
// Usage:
//   SCRAPELESS_API_KEY=sk_... node run.mjs
//   SCRAPELESS_API_KEY=sk_... SAVE_TEST_RESULTS=true node run.mjs

import { scrapeAiResponse } from "./google-ai-mode.mjs";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SAMPLE_QUERY = process.env.GOOGLE_AI_MODE_SAMPLE_QUERY ?? "best health trackers under $200";
const HERE = path.dirname(fileURLToPath(import.meta.url));
const RESULTS_DIR = path.resolve(HERE, "results");

function saveOrPrint(name, payload) {
  const json = JSON.stringify(payload, null, 2);
  if ((process.env.SAVE_TEST_RESULTS ?? "").toLowerCase() === "true") {
    fs.mkdirSync(RESULTS_DIR, { recursive: true });
    const out = path.join(RESULTS_DIR, `${name}.json`);
    fs.writeFileSync(out, json, "utf-8");
    console.error(`wrote ${out}`);
  } else {
    console.log(json);
  }
}

console.error(`== ai_response '${SAMPLE_QUERY}' ==`);
saveOrPrint("airesponse", await scrapeAiResponse(SAMPLE_QUERY));
